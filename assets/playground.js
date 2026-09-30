// The playground: edit RemoteCompose JSON, compile it in the browser, play the result.
//
// Nothing calls a server. json2rc.js is the TypeScript converter - the one verified
// byte-identical to rcj, which is itself verified against the Java parser - bundled for the
// browser, so the page turns JSON into wire bytes locally and hands them to the player.
//
// The page is also a machine interface. A web AI drives it entirely through URLs, stable DOM
// ids and one JS object; see AGENTS.md. The rule that shapes this file: the human view and
// the machine view run the SAME code path. A separate agent implementation would drift, and
// then an agent would be validating something the person never sees.

const $ = (id) => document.getElementById(id);

// ── lifecycle ────────────────────────────────────────────────────────────────
// Automation must never read a half-initialised page, so every transition is published to
// #agent-output before the work starts, and `ready` is only reached once render has settled.
const STATES = ['idle', 'loading', 'parsing', 'validating', 'compiling', 'rendering',
                'ready', 'error'];

const state = {
    status: 'idle',
    bytes: null,
    handle: null,
    playing: true,
    name: 'document',
    source: 'editor',
    lastPng: null,
    result: {},
    agent: false,
};

// ── diagnostics ──────────────────────────────────────────────────────────────
//
// Codes are this page's own, not an existing RemoteCompose registry - inventing RC1042-style
// numbers that look official would be worse than being plainly local. They are stable and
// documented in AGENTS.md.
const CODE = {
    JSON_SYNTAX: 'PG1001',
    NOT_OBJECT: 'PG1002',
    NO_HEADER: 'PG1010',
    BAD_DIMENSION: 'PG1011',
    NO_ROOT: 'PG1020',
    UNSUPPORTED: 'PG1030',   // the converter refused a construct
    COMPILE: 'PG1031',
    PLAYER: 'PG1040',
    FETCH: 'PG1050',
    DECODE: 'PG1051',
    W_NO_DESCRIPTION: 'PG2001',
    W_LARGE_RADIUS: 'PG2010',
    W_HUGE_DOC: 'PG2011',
    W_EMPTY: 'PG2020',
};

const err = (code, message, extra = {}) => ({ code, message, ...extra });

/**
 * Best-effort JSON path for a command the converter named in its message.
 *
 * The converter reports "canvas command 'pathexpression'" without a location, which is not
 * enough for an agent to fix anything. Walking the document for the first command with that
 * name recovers a usable path. It is a guess when the same command appears more than once,
 * so the result says which occurrence it found.
 */
function locateCommand(doc, name) {
    if (!doc || !name) return null;
    const want = String(name).toLowerCase();
    let found = null;
    const walk = (node, path) => {
        if (found || !node || typeof node !== 'object') return;
        if (Array.isArray(node)) {
            node.forEach((v, i) => walk(v, `${path}[${i}]`));
            return;
        }
        for (const [k, v] of Object.entries(node)) {
            if (found) return;
            const p = path ? `${path}.${k}` : k;
            if (k.toLowerCase() === want ||
                (k === 'type' && String(v).toLowerCase() === want)) {
                found = path || p;
                return;
            }
            walk(v, p);
        }
    };
    walk(doc, '');
    return found;
}

/** Structural checks that run before the converter, so the path is known exactly. */
function structuralErrors(doc) {
    const out = [];
    if (doc === null || typeof doc !== 'object' || Array.isArray(doc)) {
        return [err(CODE.NOT_OBJECT, 'The document must be a JSON object', { path: '' })];
    }
    const h = doc.header;
    if (!h || typeof h !== 'object') {
        out.push(err(CODE.NO_HEADER, 'Missing "header"', { path: 'header' }));
    } else {
        for (const k of ['width', 'height']) {
            const v = h[k];
            if (typeof v !== 'number' || !Number.isFinite(v) || v <= 0) {
                out.push(err(CODE.BAD_DIMENSION, `header.${k} must be a positive number`, {
                    path: `header.${k}`, expected: 'number > 0',
                    actual: v === undefined ? 'undefined' : typeof v,
                }));
            }
        }
    }
    if (doc.root === undefined || doc.root === null) {
        out.push(err(CODE.NO_ROOT, 'Missing "root"', { path: 'root' }));
    }
    return out;
}

function warningsFor(doc, stats) {
    const out = [];
    const h = (doc && doc.header) || {};
    if (!h.contentDescription) {
        out.push(err(CODE.W_NO_DESCRIPTION,
            'No header.contentDescription; the document carries no accessible name',
            { path: 'header.contentDescription' }));
    }
    const w = Number(h.width) || 0, ht = Number(h.height) || 0;
    if (w > 4096 || ht > 4096) {
        out.push(err(CODE.W_HUGE_DOC, `Unusually large document (${w}×${ht})`,
            { path: 'header' }));
    }
    if (stats && stats.total === 0) {
        out.push(err(CODE.W_EMPTY, 'The document contains no drawing commands', { path: 'root' }));
    }
    // A radius far larger than the page usually means a unit mistake, and the document still
    // compiles and renders - just as a flat colour - so nothing else would report it.
    const limit = Math.max(w, ht) * 4;
    if (limit > 0) {
        const walk = (node, path) => {
            if (!node || typeof node !== 'object') return;
            if (Array.isArray(node)) return node.forEach((v, i) => walk(v, `${path}[${i}]`));
            for (const [k, v] of Object.entries(node)) {
                const p = path ? `${path}.${k}` : k;
                if (k === 'radius' && typeof v === 'number' && v > limit) {
                    out.push(err(CODE.W_LARGE_RADIUS,
                        `Radius ${v} is far larger than the document (${w}×${ht})`, { path: p }));
                }
                walk(v, p);
            }
        };
        walk(doc, '');
    }
    return out;
}

// ── inspect ──────────────────────────────────────────────────────────────────

const FEATURE_TESTS = [
    ['expressions', (k, v) => typeof v === 'string' && /[-+*/()]|\b(sin|cos|tan|min|max|clamp|sqrt|abs)\s*\(/.test(v)],
    ['animation', (k, v) => typeof v === 'string' && /continuousSec|timeIn|animat/i.test(v)],
    ['transforms', (k) => /^matrix|^rotate$|^scale$|^translate$/i.test(k)],
    ['text', (k) => /^drawtext/i.test(k) || k === 'text'],
    ['paths', (k) => /^path|^drawpath$/i.test(k)],
    ['shaders', (k, v) => /shader/i.test(k) || (typeof v === 'string' && /half4\s+main|gl_FragColor/.test(v))],
    ['particles', (k) => /particle/i.test(k)],
    ['3d', (k) => /3d$/i.test(k)],
];

// Keys that are structure rather than drawing, so they are not counted as operations.
const NOT_AN_OP = new Set(['header', 'root', 'modifiers', 'commands', 'content', 'type',
                           'variables', 'resources', 'bitmaps', 'shaders']);

/** Operation histogram and feature list, read from the JSON rather than the compiled bytes. */
function inspectDoc(doc) {
    const ops = {};
    const features = new Set();
    const walk = (node) => {
        if (!node || typeof node !== 'object') return;
        if (Array.isArray(node)) return node.forEach(walk);
        for (const [k, v] of Object.entries(node)) {
            for (const [name, test] of FEATURE_TESTS) {
                try { if (test(k, v)) features.add(name); } catch {}
            }
            // Both dialects: {"drawCircle": {...}} and {"type": "drawCircle", ...}.
            if (k === 'type' && typeof v === 'string') {
                ops[v] = (ops[v] || 0) + 1;
            } else if (!NOT_AN_OP.has(k) && v && typeof v === 'object' && !Array.isArray(v)
                       && /^[a-z]/.test(k)) {
                ops[k] = (ops[k] || 0) + 1;
            }
            walk(v);
        }
    };
    walk(doc);
    const total = Object.values(ops).reduce((a, b) => a + b, 0);
    return { operations: ops, total, features: [...features].sort() };
}

// ── encoding ─────────────────────────────────────────────────────────────────

const b64urlToBytes = (s) => {
    const b64 = s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4);
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
};
const bytesToB64url = (bytes) => {
    let s = '';
    for (const b of bytes) s += String.fromCharCode(b);
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};

/**
 * Decode a #doc= fragment.
 *
 * Three encodings are accepted, sniffed rather than flagged so a caller cannot pick the wrong
 * one: gzipped-then-base64url (magic 1f 8b), plain base64url, and URI-encoded JSON. Raw JSON
 * is accepted too, since a hand-written URL often contains it.
 */
async function decodeDoc(raw) {
    const s = raw.trim();
    if (!s) throw new Error('empty document fragment');
    if (s.startsWith('{')) return decodeURIComponent(s);
    let bytes = null;
    try { bytes = b64urlToBytes(s); } catch { bytes = null; }
    if (bytes && bytes.length > 2 && bytes[0] === 0x1f && bytes[1] === 0x8b) {
        if (typeof DecompressionStream !== 'function') {
            throw new Error('gzipped document, but this browser has no DecompressionStream');
        }
        const ds = new DecompressionStream('gzip');
        const stream = new Blob([bytes]).stream().pipeThrough(ds);
        return await new Response(stream).text();
    }
    if (bytes) {
        const text = new TextDecoder().decode(bytes);
        if (text.trimStart().startsWith('{')) return text;
    }
    const uri = decodeURIComponent(s);
    if (uri.trimStart().startsWith('{')) return uri;
    throw new Error('fragment is not base64url, gzip+base64url, or URI-encoded JSON');
}

// ── DOM plumbing ─────────────────────────────────────────────────────────────

/**
 * Publish a lifecycle transition.
 *
 * `error` means the document could not be OBTAINED or decoded - a fetch that failed, a
 * fragment that would not decode. A document that loads but does not validate still reaches
 * `ready` with `valid: false`, because the pipeline ran to completion and the answer is the
 * error list. Reporting those as `error` would leave a reader unable to tell "I could not
 * look at your document" from "I looked, and here is what is wrong with it".
 */
function setState(status, extra = {}) {
    state.status = status;
    // `status` last. Spreading it first let the previous value in state.result overwrite it,
    // so the field never advanced past the first transition - an agent polling for "ready"
    // would have waited forever on a page that had already finished.
    state.result = { ...state.result, ...extra, status };
    // `valid` is kept on error rather than deleted, so a reader can always branch on it
    // without first checking which keys exist.
    if (state.result.valid === undefined) state.result.valid = false;
    $('document-state').textContent = status;
    publish();
}

function publish() {
    $('agent-output').textContent = JSON.stringify(state.result, null, 2);
}

function setStatusText(text, ok) {
    for (const id of ['document-status', 'editor-status']) {
        $(id).textContent = text;
        $(id).className = id === 'editor-status' ? `pg-status ${ok ? 'ok' : 'bad'}` : '';
    }
}

/** Last transition: fill in the fields §10 asks for, then publish. */
function finish(status, extra = {}) {
    updateDownloads();
    setState(status, {
        source: state.source,
        downloads: {
            json: !!$('download-json').href && !$('download-json').href.endsWith('#'),
            rc: !!state.bytes,
            png: !!state.lastPng,
        },
        ...extra,
    });
}

/**
 * Point the download anchors at real object URLs.
 *
 * They are <a download> rather than buttons so the contract can be satisfied by reading the
 * DOM: a reader that cannot run scripts still sees three working links.
 */
function updateDownloads() {
    const put = (id, blob, name) => {
        const a = $(id);
        if (a.dataset.url) URL.revokeObjectURL(a.dataset.url);
        if (!blob) { a.removeAttribute('href'); a.dataset.url = ''; return; }
        const url = URL.createObjectURL(blob);
        a.href = url; a.dataset.url = url; a.download = name;
    };
    put('download-json', new Blob([$('document-editor').value], { type: 'application/json' }),
        `${state.name}.json`);
    put('download-rc', state.bytes
        ? new Blob([state.bytes], { type: 'application/octet-stream' }) : null,
        `${state.name}.rc`);
    if (state.lastPng) {
        $('download-png').href = state.lastPng;
        $('download-png').download = `${state.name}.png`;
    } else {
        $('download-png').removeAttribute('href');
    }
}

function showDiagnostics(errors, warnings) {
    const fmt = (list) => list.map((e) =>
        `${e.code}  ${e.path ? e.path + ' — ' : ''}${e.message}`).join('\n');
    // Written as text even when empty. Hiding them would put the agent interface behind a
    // display rule, which is the one thing the contract rules out.
    $('validation-errors').textContent = errors.length ? fmt(errors) : '(no errors)';
    $('validation-warnings').textContent = warnings.length ? fmt(warnings) : '(no warnings)';
}

function fit(w, h) {
    const box = $('stage').getBoundingClientRect();
    const c = state.handle && state.handle.canvas;
    if (!c || !box.width) return;
    const s = Math.min((box.width - 28) / w, (box.height - 28) / h, 1);
    c.style.width = `${Math.round(w * s)}px`;
    c.style.height = `${Math.round(h * s)}px`;
}

function teardown() {
    if (state.handle) {
        // destroy(), not stop(): a browser allows only ~16 live WebGL contexts and this page
        // recompiles on every keystroke.
        state.handle.destroy();
        state.handle = null;
    }
}

/** PNG of what the player is showing, as a data URL. */
function snapshot() {
    const c = state.handle && state.handle.canvas;
    if (!c) return null;
    try {
        // toDataURL, not toBlob: toBlob's callback is never invoked in some headless
        // contexts, and an agent inspecting this page is often exactly that.
        return c.toDataURL('image/png');
    } catch {
        return null;
    }
}

// ── the one pipeline ─────────────────────────────────────────────────────────

/**
 * Parse, validate, compile and (optionally) render. Everything - the human editor, the URL
 * loaders and the JS API - goes through here.
 */
async function process(text, { render = true, emit = true } = {}) {
    state.result = {};
    setState('parsing');

    let doc = null;
    try {
        doc = JSON.parse(text);
    } catch (e) {
        const errors = [err(CODE.JSON_SYNTAX, e.message, { path: '' })];
        showDiagnostics(errors, []);
        finish('ready', { valid: false, stage: 'parse', errors, warnings: [],
                          rendered: false, previewAvailable: false });
        setStatusText('invalid JSON', false);
        if (emit) done();
        return state.result;
    }

    setState('validating');
    const errors = structuralErrors(doc);
    const stats = inspectDoc(doc);
    const warnings = errors.length ? [] : warningsFor(doc, stats);

    const h = (doc && doc.header) || {};
    const w = Number(h.width) || 0, ht = Number(h.height) || 0;
    $('document-width').textContent = w || '–';
    $('document-height').textContent = ht || '–';
    $('operation-count').textContent = stats.total;

    // Compiling IS validation: the converter refuses anything outside the implemented
    // surface rather than guessing, so a successful compile is the strongest statement this
    // page can make about a document.
    let bytes = null;
    if (!errors.length) {
        setState('compiling');
        try {
            bytes = J2RC.convert(text);
            state.bytes = bytes;
        } catch (e) {
            const name = (String(e.message).match(/'([^']+)'/) || [])[1];
            errors.push(err(
                e.name === 'NotImplementedComponent' ? CODE.UNSUPPORTED : CODE.COMPILE,
                e.message,
                { path: locateCommand(doc, name) || '', operation: name || undefined }));
        }
    }

    const valid = errors.length === 0;
    showDiagnostics(errors, warnings);
    setStatusText(valid ? `${bytes.length.toLocaleString()} bytes`
                        : `${errors.length} error(s)`, valid);

    Object.assign(state.result, {
        valid, errors, warnings,
        width: w || null, height: ht || null,
        operationCount: stats.total,
        operations: stats.operations,
        features: stats.features,
        bytes: bytes ? bytes.length : null,
    });

    if (!valid) {
        finish('ready', { stage: 'validate', rendered: false, previewAvailable: false });
        $('render-status').textContent = 'not rendered';
        $('player-status').textContent = 'not rendered';
        if (emit) done();
        return state.result;
    }

    if (!render) {
        finish('ready', { rendered: false, previewAvailable: false });
        if (emit) done();
        return state.result;
    }

    setState('rendering');
    teardown();
    state.handle = RC.createPlayer($('player'), { width: w, height: ht });
    try {
        await state.handle.loadFromArrayBuffer(
            bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
        fit(w, ht);
            $('render-status').textContent = `${w} × ${ht}`;
        $('player-status').textContent = `${w} × ${ht}`;
        if (!state.playing) state.handle.player.stop();
    } catch (e) {
        const errs = [err(CODE.PLAYER, `compiled, but the player could not load it: ${e.message}`)];
        showDiagnostics(errs, warnings);
        finish('ready', { stage: 'render', valid: false, errors: errs,
                          rendered: false, previewAvailable: false });
        if (emit) done();
        return state.result;
    }

    // One frame of settle: shader programs compile asynchronously, and a snapshot taken
    // before that is blank - which an agent would read as a broken document.
    await new Promise((r) => setTimeout(r, 60));
    const png = snapshot();
    state.lastPng = png || null;
    if (png) {
        $('preview-image').src = png;
        state.result.previewImage = `#preview-image (${png.length} chars, image/png)`;
    }
    finish('ready', { rendered: true, previewAvailable: !!png });
    if (emit) done();
    return state.result;
}

/** Completion signal, after load, validation, render and #agent-output are all current. */
function done() {
    publish();
    window.dispatchEvent(new CustomEvent('remotecompose-ready', { detail: state.result }));
}

// ── downloads ────────────────────────────────────────────────────────────────

function save(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ── URL contract ─────────────────────────────────────────────────────────────

async function fromUrl() {
    const q = new URLSearchParams(location.search);
    const hash = new URLSearchParams(location.hash.replace(/^#/, ''));
    const action = (q.get('action') || 'render').toLowerCase();
    const render = action !== 'validate' && action !== 'inspect';

    if (q.get('test') === '1') {
        state.source = 'test';
        state.name = 'agent-test';
        const text = JSON.stringify(TEST_DOC, null, 2);
        $('document-editor').value = text;
        const r = await process(text, { render: true, emit: false });
        // "pass" means the whole interface worked, not merely that the document compiled:
        // it must also have rendered and produced a preview an agent can look at.
        const pass = r.valid && r.rendered && r.previewAvailable;
        setState('ready', { test: 'agent-interface', result: pass ? 'pass' : 'fail' });
        done();
        return true;
    }

    const src = q.get('src');
    const docParam = hash.get('doc') || q.get('doc');

    if (docParam) {
        state.source = 'inline';
        setState('loading');
        let text;
        try {
            text = await decodeDoc(docParam);
        } catch (e) {
            const errors = [err(CODE.DECODE, e.message)];
            showDiagnostics(errors, []);
            setState('error', { stage: 'load', errors, warnings: [], valid: false,
                                source: state.source, rendered: false,
                                previewAvailable: false });
            done();
            return true;
        }
        $('document-editor').value = text;
        await process(text, { render });
        return true;
    }

    if (src) {
        state.source = 'src';
        setState('loading');
        let text;
        try {
            const r = await fetch(src, { mode: 'cors' });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            text = await r.text();
        } catch (e) {
            // A cross-origin refusal and an offline host are indistinguishable from script,
            // so the type says both rather than guessing one.
            const errors = [err(CODE.FETCH,
                'The document could not be loaded. The source may not permit cross-origin ' +
                `access, or may be unreachable. (${e.message})`,
                { path: 'src' })];
            showDiagnostics(errors, []);
            setState('error', {
                stage: 'load', errorType: 'cors_or_network', source: state.source,
                sourceUrl: src, errors, warnings: [], valid: false,
                rendered: false, previewAvailable: false,
            });
            done();
            return true;
        }
        $('document-editor').value = text;
        state.name = (src.split('/').pop() || 'document').replace(/\.json$/i, '');
        await process(text, { render });
        return true;
    }
    return false;
}

// ── public API ───────────────────────────────────────────────────────────────
//
// Deliberately delegates to `process`, the same function the editor uses. A separate
// implementation would drift, and an agent would end up validating something the page does
// not actually show.
const asText = (json) => typeof json === 'string' ? json : JSON.stringify(json);

window.RemoteComposePlayground = {
    version: 1,
    get status() { return state.status; },
    get result() { return state.result; },

    async load(json) {
        $('document-editor').value = asText(json);
        return await process($('document-editor').value, { render: true });
    },
    async validate(json) {
        const r = await process(asText(json), { render: false });
        return { valid: !!r.valid, errors: r.errors || [], warnings: r.warnings || [] };
    },
    async render(json) { return await process(asText(json), { render: true }); },
    async compile(json) {
        const r = await process(asText(json), { render: false });
        if (!r.valid) throw new Error(`document is not valid: ${(r.errors || []).length} error(s)`);
        return state.bytes;                       // Uint8Array
    },
    async inspect(json) {
        const r = await process(asText(json), { render: false });
        return {
            valid: !!r.valid, width: r.width, height: r.height,
            operationCount: r.operationCount, operations: r.operations,
            features: r.features, errors: r.errors || [], warnings: r.warnings || [],
        };
    },
    previewPng() { return snapshot(); },
    /** A URL carrying the current document inline, needing no server and no CORS. */
    shareUrl(json) {
        const text = asText(json ?? $('document-editor').value);
        const b = bytesToB64url(new TextEncoder().encode(text));
        return `${location.origin}${location.pathname}#doc=${b}`;
    },
};

// ── boot ─────────────────────────────────────────────────────────────────────

/**
 * The ?test=1 document.
 *
 * Deterministic on purpose: no clock, no randomness, no network, no external font. It has to
 * give the same bytes and the same pixels on every run, or a failing self-test would not tell
 * a caller whether the interface or the document was at fault. Exercises parsing, validation,
 * two drawing operations, text, rendering and preview extraction.
 */
const TEST_DOC = {
    header: { apiLevel: 7, width: 200, height: 120, profiles: 513,
              contentDescription: 'RemoteCompose AI Test' },
    root: { canvas: { modifiers: ['fillMaxSize', { background: '#FF10141C' }], commands: [
        { paint: { color: '#FF2F6BD8', style: 'fill', antiAlias: true } },
        { drawCircle: { cx: 40.0, cy: 60.0, radius: 22.0 } },
        { paint: { color: '#FFE7ECF3', style: 'fill', textSize: 18.0, antiAlias: true } },
        { drawTextAnchored: { text: 'RemoteCompose AI Test',
                              x: 100.0, y: 104.0, panX: 0.0, panY: 0.0 } },
    ] } },
};

const DEFAULT_DOC = {
    header: { apiLevel: 7, width: 400, height: 400, profiles: 513,
              contentDescription: 'playground' },
    root: { canvas: { modifiers: ['fillMaxSize', { background: '#FF10141C' }], commands: [
        { paint: { color: '#FF2F6BD8', style: 'fill', antiAlias: true } },
        { drawCircle: { cx: 200.0, cy: 200.0,
                        radius: '110 + sin(continuousSec() * 2) * 45' } },
        { paint: { color: '#FFE7ECF3', style: 'fill', textSize: 26.0, antiAlias: true } },
        { drawTextAnchored: { text: 'edit me', x: 200.0, y: 350.0, panX: 0.0, panY: 0.0 } },
    ] } },
};

function setTheme(mode) {
    document.documentElement.dataset.theme = mode;
    try { localStorage.setItem('rc-theme', mode); } catch {}
    $('theme-light').classList.toggle('on', mode === 'light');
    $('theme-dark').classList.toggle('on', mode === 'dark');
}

async function loadExamples() {
    try {
        const f = await (await fetch('catalog/facets.json')).json();
        const n = Math.ceil(f.total / (f.shardSize || 500));
        const shards = await Promise.all(Array.from({ length: n }, (_, k) =>
            fetch(`catalog/docs-${String(k).padStart(3, '0')}.json`).then((r) => r.json())));
        const withJson = shards.flat().filter((r) => r.j).sort((a, b) => a.id.localeCompare(b.id));
        $('example').innerHTML = '<option value="">Load an example…</option>' +
            withJson.map((r) => `<option value="${r.id}">${r.id}</option>`).join('');
    } catch {
        $('example').hidden = true;          // opened without the catalog beside it
    }
}

async function main() {
    const q = new URLSearchParams(location.search);
    state.agent = q.get('agent') === '1';
    document.body.classList.toggle('agent-mode', state.agent);

    let saved = null;
    try { saved = localStorage.getItem('rc-theme'); } catch {}
    setTheme(saved || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
    $('theme-light').onclick = () => setTheme('light');
    $('theme-dark').onclick = () => setTheme('dark');

    let t;
    $('document-editor').addEventListener('input', () => {
        clearTimeout(t);
        t = setTimeout(() => { state.source = 'editor'; process($('document-editor').value); }, 350);
    });
    $('fmt').onclick = () => {
        try {
            $('document-editor').value =
                JSON.stringify(JSON.parse($('document-editor').value), null, 2);
            process($('document-editor').value);
        } catch { /* the error is already shown by process() */ }
    };
    $('share').onclick = async () => {
        const url = window.RemoteComposePlayground.shareUrl();
        try { await navigator.clipboard.writeText(url); $('share').textContent = 'Copied'; }
        catch { prompt('Link', url); }
        setTimeout(() => ($('share').textContent = 'Copy link'), 1500);
    };
    $('play').onclick = () => {
        state.playing = !state.playing;
        $('play').textContent = state.playing ? 'Pause' : 'Play';
        if (!state.handle) return;
        if (state.playing) process($('document-editor').value);
        else state.handle.player.stop();
    };
    // The buttons click the anchors rather than repeating the download logic, so the human
    // path and the agent-visible links can never produce different files.
    for (const [btn, link] of [['btn-png', 'download-png'], ['btn-rc', 'download-rc'],
                               ['btn-json', 'download-json']]) {
        $(btn).onclick = () => { updateDownloads(); $(link).click(); };
    }
    $('example').onchange = async (e) => {
        const id = e.target.value;
        if (!id) return;
        const text = await (await fetch(`docs/${id}/doc.json`)).text();
        state.name = id.split('/').pop();
        $('document-editor').value = text;
        process(text);
    };
    addEventListener('resize', () => {
        const w = Number($('document-width').textContent) || 400;
        const h = Number($('document-height').textContent) || 400;
        fit(w, h);
    });
    addEventListener('hashchange', () => fromUrl());

    loadExamples();
    // A URL-supplied document wins over the sample, so an agent never races the default.
    if (!(await fromUrl())) {
        $('document-editor').value = JSON.stringify(DEFAULT_DOC, null, 2);
        await process($('document-editor').value);
    }
}

main();
