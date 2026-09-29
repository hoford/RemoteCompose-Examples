// Single-document view: a live player plus everything downloadable about the document.
//
// Unlike the grid, this page leaves the player running — one document animating is the point.

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const id = new URLSearchParams(location.search).get('id');

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

    // Size the stage to the document's own aspect, capped so tall documents stay on screen.
    const w = derived.width || 400, h = derived.height || 400;
    const scale = Math.min(520 / w, 620 / h, 1.6);
    const handle = RC.createPlayer(document.getElementById('player'), {
        width: Math.round(w * scale), height: Math.round(h * scale),
    });
    handle.loadFromUrl(`${base}/doc.rc`).catch(() => {
        document.getElementById('player').textContent = 'This document could not be played.';
    });

    const dl = [`<a href="${base}/doc.rc" download>doc.rc</a>`];
    if (derived.hasJson) {
        dl.push(`<a href="${base}/doc.json" download>doc.json</a>`);
    }
    for (const f of derived.src || []) dl.push(`<a href="${base}/src/${f}" download>${esc(f)}</a>`);
    document.getElementById('downloads').innerHTML = dl.join('');

    const kv = [
        ['source', entry.source],
        ['authored in', (entry.authoring || []).join(', ') || '—'],
        ['size', `${derived.bytes} bytes`],
        ['dimensions', `${derived.width}×${derived.height}`],
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
            '<h3>Operations used</h3>' +
            hist.map(([k, n]) => `<div><span>${esc(k)}</span><span>${n}</span></div>`).join('');
    } else if (derived.decoded === false) {
        document.getElementById('ops').innerHTML =
            '<h3>Operations used</h3><div><span>could not be decoded</span><span></span></div>';
    }
}

main();
