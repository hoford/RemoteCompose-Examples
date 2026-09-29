// Inline source viewers for the document page.
//
// Each file the document was authored from gets a row: name, size, a download button, and a
// toggle that expands the content in place. Content is fetched on first expand rather than
// with the page, because a single document can carry 80 KB of JSON and most visits never open
// it.
//
// JSON is rendered as a collapsible tree instead of a wall of text. Objects and arrays past
// the top level start closed, and long arrays render a bounded window, because a document's
// JSON runs to thousands of nodes and building all of them costs more than it is worth.

const COLLAPSE_BELOW_DEPTH = 1;   // depth 0 and 1 open; deeper starts closed
const ARRAY_WINDOW = 100;         // children rendered before "N more"

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function fmtSize(n) {
    return n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB`;
}

// ── JSON tree ────────────────────────────────────────────────────────────────

function summaryOf(v) {
    if (Array.isArray(v)) return `[] ${v.length} item${v.length === 1 ? '' : 's'}`;
    const n = Object.keys(v).length;
    return `{} ${n} key${n === 1 ? '' : 's'}`;
}

function scalar(v) {
    if (typeof v === 'string') return `<span class="j-str">"${esc(v)}"</span>`;
    if (v === null) return `<span class="j-null">null</span>`;
    if (typeof v === 'number') return `<span class="j-num">${v}</span>`;
    if (typeof v === 'boolean') return `<span class="j-bool">${v}</span>`;
    return esc(String(v));
}

function jsonNode(key, value, depth) {
    const label = key === null ? '' : `<span class="j-key">${esc(key)}</span>: `;
    if (value === null || typeof value !== 'object') {
        return `<div class="j-leaf">${label}${scalar(value)}</div>`;
    }
    const entries = Array.isArray(value)
        ? value.map((v, i) => [String(i), v])
        : Object.entries(value);
    const shown = entries.slice(0, ARRAY_WINDOW);
    const rest = entries.length - shown.length;
    const open = depth <= COLLAPSE_BELOW_DEPTH ? ' open' : '';
    return `<details class="j-node"${open}>` +
        `<summary>${label}<span class="j-meta">${summaryOf(value)}</span></summary>` +
        `<div class="j-children">` +
        shown.map(([k, v]) => jsonNode(k, v, depth + 1)).join('') +
        (rest > 0 ? `<div class="j-more">… ${rest} more</div>` : '') +
        `</div></details>`;
}

// ── rows ─────────────────────────────────────────────────────────────────────

function codeBlock(text) {
    // Line numbers come from a CSS counter, so the numbers stay unselectable and copying the
    // block yields just the source.
    return '<pre class="code">' +
        text.split('\n').map((l) => `<span class="line">${esc(l) || ' '}</span>`).join('') +
        '</pre>';
}

async function expand(row, url, kind) {
    const body = row.querySelector('.source-body');
    if (row.dataset.loaded === '1') return;
    body.innerHTML = '<div class="dim">loading…</div>';
    try {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`${r.status}`);
        const text = await r.text();
        if (kind === 'json') {
            try {
                body.innerHTML = `<div class="j-root">${jsonNode(null, JSON.parse(text), 0)}</div>`;
            } catch {
                body.innerHTML = codeBlock(text);   // malformed JSON is still worth reading
            }
        } else {
            body.innerHTML = codeBlock(text);
        }
        row.dataset.loaded = '1';
    } catch (e) {
        body.innerHTML = `<div class="dim">could not load this file (${esc(e.message)})</div>`;
    }
}

/**
 * Render the source list into `host`.
 * `files` is [{name, url, kind, bytes}] - kind: 'json' | 'code' | 'binary'.
 */
export function mountSources(host, files) {
    host.innerHTML = files.map((f) => `
        <div class="source" data-kind="${f.kind}">
          <div class="source-head">
            ${f.kind === 'binary'
                ? `<span class="source-name binary">${esc(f.name)}</span>`
                : `<button class="source-toggle" aria-expanded="false">${esc(f.name)}</button>`}
            ${f.bytes != null ? `<span class="source-size">${fmtSize(f.bytes)}</span>` : ''}
            <a class="source-dl" href="${f.url}" download>download</a>
          </div>
          <div class="source-body" hidden></div>
        </div>`).join('');

    host.querySelectorAll('.source').forEach((row, i) => {
        const f = files[i];
        const btn = row.querySelector('.source-toggle');
        if (!btn) return;
        btn.onclick = () => {
            const body = row.querySelector('.source-body');
            const open = body.hidden;
            body.hidden = !open;
            btn.setAttribute('aria-expanded', String(open));
            row.classList.toggle('open', open);
            if (open) expand(row, f.url, f.kind);
        };
    });
}
