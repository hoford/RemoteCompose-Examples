// The playground: edit JSON, compile it in the browser, play the result.
//
// Nothing here calls a server. json2rc.js is the TypeScript converter - the same one verified
// byte-identical to rcj over the corpus - bundled for the browser, so the page turns JSON into
// wire bytes locally and hands them straight to the player.

const $ = (id) => document.getElementById(id);

const state = {
    bytes: null,       // last successful compile
    handle: null,      // live player
    playing: true,
    name: 'document',
};

// A document that draws something and animates, in the dialect the corpus actually uses:
// root is an object, a canvas carries `commands`, and each command is keyed by its name.
// Verified to compile (279 bytes) and render before being used as the starting point.
const DEFAULT_DOC = {
    "header": {
        "apiLevel": 7,
        "width": 400,
        "height": 400,
        "profiles": 513,
        "contentDescription": "playground"
    },
    "root": {
        "canvas": {
            "modifiers": [
                "fillMaxSize",
                {
                    "background": "#FF10141C"
                }
            ],
            "commands": [
                {
                    "paint": {
                        "color": "#FF2F6BD8",
                        "style": "fill",
                        "antiAlias": true
                    }
                },
                {
                    "drawCircle": {
                        "cx": 200.0,
                        "cy": 200.0,
                        "radius": "110 + sin(continuousSec() * 2) * 45"
                    }
                },
                {
                    "paint": {
                        "color": "#FFE7ECF3",
                        "style": "fill",
                        "textSize": 26.0,
                        "antiAlias": true
                    }
                },
                {
                    "drawTextAnchored": {
                        "text": "edit me",
                        "x": 200.0,
                        "y": 350.0,
                        "panX": 0.0,
                        "panY": 0.0
                    }
                }
            ]
        }
    }
};

// ── compile + play ───────────────────────────────────────────────────────────

function teardown() {
    if (state.handle) {
        // destroy(), not stop(): a browser allows only ~16 live WebGL contexts, and the
        // playground recompiles on every keystroke.
        state.handle.destroy();
        state.handle = null;
    }
}

function fit(w, h) {
    const box = $('stage').getBoundingClientRect();
    const s = Math.min((box.width - 28) / w, (box.height - 28) / h, 1);
    const c = state.handle?.canvas;
    if (!c) return;
    c.style.width = `${Math.round(w * s)}px`;
    c.style.height = `${Math.round(h * s)}px`;
}

async function compile(text) {
    let bytes;
    try {
        bytes = J2RC.convert(text);
    } catch (e) {
        // A converter that guesses is worse than one that refuses, so it throws on anything
        // outside the implemented surface. Surface that rather than silently showing stale
        // output.
        $('err').hidden = false;
        $('err').textContent = `${e.name || 'Error'}: ${e.message}`;
        $('status').textContent = 'not compiled';
        $('status').className = 'pg-status bad';
        return;
    }
    $('err').hidden = true;
    state.bytes = bytes;
    $('status').textContent = `${bytes.length.toLocaleString()} bytes`;
    $('status').className = 'pg-status ok';

    let w = 400, h = 400;
    try {
        const hdr = JSON.parse(text).header || {};
        w = hdr.width || 400; h = hdr.height || 400;
    } catch {}

    teardown();
    state.handle = RC.createPlayer($('player'), { width: w, height: h });
    try {
        await state.handle.loadFromArrayBuffer(
            bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
        fit(w, h);
        $('meta').textContent = `${w} × ${h}`;
        if (!state.playing) state.handle.player.stop();
    } catch (e) {
        $('err').hidden = false;
        $('err').textContent = `compiled, but the player could not load it: ${e.message}`;
    }
}

// ── downloads ────────────────────────────────────────────────────────────────

function save(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadPng() {
    const c = state.handle?.canvas;
    if (!c) return;
    // toDataURL, not toBlob: toBlob's callback is never invoked in some headless contexts,
    // and this path has to work everywhere the page does.
    const url = c.toDataURL('image/png');
    fetch(url).then((r) => r.blob()).then((b) => save(b, `${state.name}.png`));
}

// ── boot ─────────────────────────────────────────────────────────────────────

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
        // Only documents that carry JSON can be loaded into an editor.
        const withJson = shards.flat().filter((r) => r.j).sort((a, b) => a.id.localeCompare(b.id));
        $('example').innerHTML = '<option value="">Load an example…</option>' +
            withJson.map((r) => `<option value="${r.id}">${r.id}</option>`).join('');
    } catch {
        $('example').hidden = true;      // opened without the catalog beside it
    }
}

async function main() {
    let saved = null;
    try { saved = localStorage.getItem('rc-theme'); } catch {}
    setTheme(saved || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
    $('theme-light').onclick = () => setTheme('light');
    $('theme-dark').onclick = () => setTheme('dark');

    $('src').value = JSON.stringify(DEFAULT_DOC, null, 2);
    await compile($('src').value);
    loadExamples();

    let t;
    $('src').addEventListener('input', () => {
        clearTimeout(t);
        t = setTimeout(() => compile($('src').value), 350);
    });

    $('fmt').onclick = () => {
        try {
            $('src').value = JSON.stringify(JSON.parse($('src').value), null, 2);
            compile($('src').value);
        } catch (e) {
            $('err').hidden = false;
            $('err').textContent = `cannot format: ${e.message}`;
        }
    };

    $('play').onclick = () => {
        state.playing = !state.playing;
        $('play').textContent = state.playing ? 'Pause' : 'Play';
        if (!state.handle) return;
        state.playing ? state.handle.player.repaint() : state.handle.player.stop();
        if (state.playing) {
            // repaint() paints one frame; reloading restarts the animation loop.
            compile($('src').value);
        }
    };

    $('dl-png').onclick = downloadPng;
    $('dl-rc').onclick = () => state.bytes &&
        save(new Blob([state.bytes], { type: 'application/octet-stream' }), `${state.name}.rc`);
    $('dl-json').onclick = () =>
        save(new Blob([$('src').value], { type: 'application/json' }), `${state.name}.json`);

    $('example').onchange = async (e) => {
        const id = e.target.value;
        if (!id) return;
        const text = await (await fetch(`docs/${id}/doc.json`)).text();
        state.name = id.split('/').pop();
        $('src').value = text;
        compile(text);
    };

    addEventListener('resize', () => {
        try {
            const hdr = JSON.parse($('src').value).header || {};
            fit(hdr.width || 400, hdr.height || 400);
        } catch {}
    });
}

main();
