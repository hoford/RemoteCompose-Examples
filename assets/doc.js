// Single-document view: a live player above, everything known about the document below.
//
// Unlike the grid, this page leaves the player running - one document animating is the point.

const stripTags = (s) => String(s || '').replace(/#[A-Za-z0-9][\w-]*/g, '').replace(/\s+/g, ' ').trim();

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
 * Show the canvas at the size it is played at, 1:1.
 *
 * player.resize() sets canvas.style.width/height itself to pixels/density, so on a 2x display
 * a 1024-pixel document would be shown at 512 CSS px and the menu would appear to do nothing.
 * The style is therefore set explicitly here: picking 1024 gives a 1024 px player.
 *
 * Nothing is scaled to fit. If the document is larger than the stage the frame scrolls, which
 * is the honest thing to do - a document played at 1024 and squeezed into 586 is not showing
 * you what it looks like at 1024. Documents smaller than the stage are centred in it.
 */
function fitCanvas() {
    if (!handle) return;
    const cw = handle.canvas.width, ch = handle.canvas.height;
    if (!cw || !ch) return;
    handle.canvas.style.width = `${cw}px`;
    handle.canvas.style.height = `${ch}px`;
    document.getElementById('size-note').textContent = `${cw} × ${ch}`;
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
    document.getElementById('desc').textContent = stripTags(entry.description);
    document.getElementById('tags').innerHTML =
        (entry.tags || []).map((t) => `<span class="chip tag">#${esc(t)}</span>`).join('');

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
        ['native dimensions', derived.width
            ? `${derived.width}×${derived.height}`
            : '— (no size declared in the header; the player sizes it from its root layout)'],
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
