// Single-document view: a live player above, everything known about the document below.
//
// Unlike the grid, this page leaves the player running - one document animating is the point.

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const id = new URLSearchParams(location.search).get('id');

let handle = null;
let native = { w: 400, h: 400 };

/** The size the document is PLAYED at, for the current menu selection. */
function chosenSize(value) {
    switch (value) {
        case '2x':   return { w: native.w * 2, h: native.h * 2 };
        case '4x':   return { w: native.w * 4, h: native.h * 4 };
        case '320':  return { w: 320, h: 320 };
        case '512':  return { w: 512, h: 512 };
        case '1024': return { w: 1024, h: 1024 };
        default:     return { w: native.w, h: native.h };
    }
}

/**
 * Scale the canvas down to fit the stage without distorting it.
 *
 * player.resize() sets canvas.style.width/height itself, to the full pixel size divided by
 * density. A 1024x1024 document would therefore overflow the stage. Overriding the style here
 * keeps the document PLAYING at the chosen resolution - which is the point of the menu, since
 * resize() re-flows layout and re-evaluates componentWidth/Height - while DISPLAYING it at
 * whatever fits.
 */
function fitCanvas() {
    if (!handle) return;
    const frame = document.querySelector('.frame');
    const cw = handle.canvas.width, ch = handle.canvas.height;
    if (!cw || !ch) return;
    const availW = frame.clientWidth - 24;
    const availH = frame.clientHeight - 24;
    // Deliberately NOT capped at 1: the stage is two thirds of the page and the document is
    // meant to fill it, so a small document is scaled up to fit. The menu controls the
    // resolution it is PLAYED at; this only controls how large it is shown. Pick 2x or 1024
    // if the upscale looks soft - that re-renders rather than stretching.
    const scale = Math.min(availW / cw, availH / ch);
    handle.canvas.style.width = `${Math.round(cw * scale)}px`;
    handle.canvas.style.height = `${Math.round(ch * scale)}px`;
    const note = document.getElementById('size-note');
    note.textContent = Math.abs(scale - 1) < 0.01
        ? `${cw}×${ch}`
        : `${cw}×${ch}, shown at ${Math.round(scale * 100)}%`;
}

function applySize() {
    const { w, h } = chosenSize(document.getElementById('size').value);
    handle.resize(w, h);
    handle.player.repaint();
    fitCanvas();
}

async function main() {
    if (!id) { document.getElementById('title').textContent = 'No document specified'; return; }
    const base = `docs/${id}`;

    const [entry, derived] = await Promise.all([
        fetch(`${base}/entry.json`).then((r) => r.json()).catch(() => ({})),
        fetch(`${base}/derived.json`).then((r) => r.json()).catch(() => ({})),
    ]);

    document.title = `${entry.title || id} — RemoteCompose Examples`;
    document.getElementById('title').textContent = entry.title || id;
    document.getElementById('docid').textContent = id;
    document.getElementById('desc').textContent = entry.description || '';

    native = { w: derived.width || 400, h: derived.height || 400 };

    handle = RC.createPlayer(document.getElementById('player'), { width: native.w, height: native.h });
    try {
        await handle.loadFromUrl(`${base}/doc.rc`);
        applySize();
    } catch {
        document.getElementById('player').textContent = 'This document could not be played.';
    }

    document.getElementById('size').addEventListener('change', applySize);
    addEventListener('resize', fitCanvas);

    const dl = [`<a href="${base}/doc.rc" download>doc.rc</a>`];
    if (derived.hasJson) dl.push(`<a href="${base}/doc.json" download>doc.json</a>`);
    for (const f of derived.src || []) dl.push(`<a href="${base}/src/${f}" download>${esc(f)}</a>`);
    document.getElementById('downloads').innerHTML = dl.join('');

    const kv = [
        ['source', entry.source],
        ['authored in', (entry.authoring || []).join(', ') || '—'],
        ['size', `${derived.bytes} bytes`],
        ['native dimensions', `${derived.width}×${derived.height}`],
        ['operations', `${derived.ops} (${derived.distinctOps} distinct)`],
        ['APIs', (derived.apis || []).join(', ') || '—'],
        ['features', (derived.flags || []).join(', ') || '—'],
        ['origin', entry.provenance],
    ];
    document.getElementById('kv').innerHTML = kv
        .filter(([, v]) => v)
        .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('');

    const hist = Object.entries(derived.histogram || {}).sort((a, b) => b[1] - a[1]);
    if (hist.length) {
        document.getElementById('ops').innerHTML =
            '<h3>Operations used</h3><div class="ops-grid">' +
            hist.map(([k, n]) => `<div><span>${esc(k)}</span><span>${n}</span></div>`).join('') +
            '</div>';
    } else if (derived.decoded === false) {
        document.getElementById('ops').innerHTML =
            '<h3>Operations used</h3><p class="dim">This document could not be decoded by the ' +
            'cataloguing tool, so no operation breakdown is available. It still plays correctly.</p>';
    }
}

main();
