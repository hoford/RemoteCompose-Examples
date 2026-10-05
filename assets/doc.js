// Single-document view: a live player above, everything known about the document below.
//
// Unlike the grid, this page leaves the player running - one document animating is the point.

const stripTags = (s) => String(s || '').replace(/#[A-Za-z0-9][\w-]*/g, '').replace(/\s+/g, ' ').trim();

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

import { mountSources } from './source.js';

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

    // ...except on a phone, where 1:1 is not an option. Every document in the corpus is
    // wider than a 390px viewport, so showing it at its played size means the frame scrolls
    // sideways - and the canvas now takes the gesture (touch-action: none), so there is no
    // way to pan to the rest of it. Fitting is the only way to see the document at all.
    //
    // Input still lands correctly: the player maps a pointer through canvas.width /
    // rect.width, so a canvas scaled down by CSS reports the same document coordinates.
    //
    // The scale is printed rather than hidden. The reason the desktop shows 1:1 is that a
    // document squeezed into a smaller box is not showing you what it looks like; that is
    // just as true here, so the reader is told what they are looking at.
    // Keyed on touch, not only on width. `touch-action: none` gives the canvas every
    // gesture, so wherever that applies there must be nothing left to pan to - otherwise a
    // document larger than the frame on a tablet could be neither driven nor scrolled. A
    // mouse desktop matches neither condition and keeps its 1:1 view and its scrollbars.
    const frame = document.querySelector('.frame');
    let scale = 1;
    if (frame && matchMedia('(max-width: 760px), (pointer: coarse)').matches) {
        const availW = frame.clientWidth - 8, availH = frame.clientHeight - 8;
        if (availW > 0 && availH > 0) {
            scale = Math.min(1, availW / cw, availH / ch);
        }
    }
    handle.canvas.style.width = `${Math.round(cw * scale)}px`;
    handle.canvas.style.height = `${Math.round(ch * scale)}px`;
    document.getElementById('size-note').textContent = scale < 1
        ? `${cw} × ${ch} · ${Math.round(scale * 100)}%`
        : `${cw} × ${ch}`;
}

function applySize() {
    const { w, h } = chosenSize(document.getElementById('size').value);
    handle.resize(w, h);
    handle.player.repaint();
    fitCanvas();
}

/**
 * Full-page mode: the stage takes the whole viewport and everything else is hidden.
 *
 * Done with a class rather than the Fullscreen API. The API needs a user gesture, cannot be
 * entered from a link, and drops out of the page entirely - which makes it impossible to land
 * directly in this mode from a URL. A class works from ?full=1, survives reload, and still
 * leaves the real Fullscreen key available to the browser.
 */
function setupFullPage() {
    const btn = document.getElementById('fullpage');
    const set = (on) => {
        document.body.classList.toggle('fullpage', on);
        btn.textContent = on ? '⤡ Exit full page' : '⤢ Full page';
        btn.setAttribute('aria-pressed', String(on));
        const u = new URL(location.href);
        if (on) u.searchParams.set('full', '1'); else u.searchParams.delete('full');
        history.replaceState(null, '', u);
        // The frame changed size, so the canvas has to be re-fitted.
        requestAnimationFrame(fitCanvas);
    };
    btn.onclick = () => set(!document.body.classList.contains('fullpage'));
    addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && document.body.classList.contains('fullpage')) set(false);
        else if (e.key === 'f' && !/input|select|textarea/i.test(e.target.tagName)) {
            set(!document.body.classList.contains('fullpage'));
        }
    });
    if (new URLSearchParams(location.search).get('full') === '1') set(true);
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
    setupFullPage();

    // The compiled document is binary, so it is download-only. Everything it was authored
    // from expands in place.
    const files = [{ name: 'doc.rc', url: `${base}/doc.rc`, kind: 'binary', bytes: derived.bytes }];
    if (derived.hasJson) {
        files.push({ name: 'doc.json', url: `${base}/doc.json`, kind: 'json', bytes: null });
    }
    for (const f of derived.src || []) {
        files.push({ name: f, url: `${base}/src/${f}`, kind: 'code', bytes: null });
    }
    mountSources(document.getElementById('downloads'), files);

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
