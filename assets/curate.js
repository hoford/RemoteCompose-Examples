// The curation workbench: one document at a time, tags one click each, next one keypress.
//
// It talks to tools/curate.py, which runs locally. When that API is absent — which is the
// case on the published site — the page stays readable but every control that would write
// is disabled, rather than failing silently when clicked.
//
// Saving is explicit-but-automatic: an edit marks the document dirty and it is flushed on
// navigation, on a short idle timer, and before the page unloads. Curating is a fast
// repetitive job and a Save button in the middle of it is one click per document too many.

const PRESETS = [
    // label shown, tag stored. They differ where the corpus already settled on a spelling:
    // writing "3D" or "Clocks" would create a SECOND facet beside the 57 documents already
    // tagged `3d` and the 25 tagged `clock`, which reads as data loss from the gallery.
    ['#iot', 'iot'],
    ['#graph', 'graph'],
    ['#3D', '3d'],
    ['#Test', 'test'],
    ['#Clocks', 'clock'],
    ['#animated', 'animated'],
    ['#input', 'input'],
    ['#featured', 'featured'],
];

const state = {
    docs: [],          // every document, in corpus order
    view: [],          // the filtered subset being walked
    at: 0,             // index into view
    vocab: {},         // tag -> count across the corpus
    extra: [],         // tags typed this session, not yet in vocab
    dirty: new Set(),  // ids edited but not yet written
    touched: new Set(),// ids edited this session, for the "edited" filter
    live: false,
    handle: null,
    saving: false,
};

const $ = (id) => document.getElementById(id);
const normTag = (s) => String(s).trim().replace(/^#/, '').toLowerCase()
    .replace(/[^a-z0-9+_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40);

const api = (path, body) => fetch(path, body
    ? { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body) }
    : undefined).then((r) => r.json());

const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function current() { return state.view[state.at]; }

// ── palette ──────────────────────────────────────────────────────────────────

/** Preset tags first and always, then everything else in use, commonest first. */
function paletteTags() {
    const preset = PRESETS.map(([, t]) => t);
    const rest = [...new Set([...Object.keys(state.vocab), ...state.extra])]
        .filter((t) => !preset.includes(t))
        .sort((a, b) => (state.vocab[b] || 0) - (state.vocab[a] || 0) || a.localeCompare(b));
    return [...preset, ...rest];
}

function labelFor(tag) {
    const hit = PRESETS.find(([, t]) => t === tag);
    return hit ? hit[0] : '#' + tag;
}

function paintTags() {
    const doc = current();
    if (!doc) return;
    const on = new Set(doc.tags);
    const tags = paletteTags();
    $('tags').innerHTML = tags.map((t, i) => {
        const n = state.vocab[t] || 0;
        const key = i < 9 ? `<span class="k">${i + 1}</span>` : '';
        return `<button class="tagchip${on.has(t) ? ' on' : ''}" data-tag="${esc(t)}"
                 title="${esc(t)} — ${n} document${n === 1 ? '' : 's'}">${key}${esc(labelFor(t))}
                 <span class="n">${n}</span></button>`;
    }).join('');
    $('tagcount').textContent = on.size ? `${on.size} selected` : 'none';
}

function toggleTag(tag) {
    const doc = current();
    if (!doc || !state.live) return;
    const i = doc.tags.indexOf(tag);
    if (i >= 0) doc.tags.splice(i, 1); else doc.tags.push(tag);
    doc.tags.sort();
    markDirty(doc.id);
    paintTags();
}

// ── the current document ─────────────────────────────────────────────────────

async function show(i) {
    await flush();
    if (!state.view.length) {
        $('title').textContent = 'Nothing matches this filter';
        $('docid').textContent = '';
        $('pos').textContent = '0 of 0';
        $('tags').innerHTML = '';
        return;
    }
    state.at = Math.max(0, Math.min(state.view.length - 1, i));
    const doc = current();

    $('title').textContent = doc.title;
    $('docid').textContent = doc.id;
    $('desc').value = doc.description;
    $('pos').textContent = `${state.at + 1} of ${state.view.length}`;
    $('openlink').href = `doc.html?id=${encodeURIComponent(doc.id)}`;
    paintTags();
    location.hash = encodeURIComponent(doc.id);

    // One live player, replaced each time: animation is itself a thing being tagged, so a
    // still frame would not let you judge #animated. Destroy before creating — a browser
    // keeps only ~16 WebGL contexts and silently kills the oldest beyond that.
    if (state.handle) { try { state.handle.destroy(); } catch {} state.handle = null; }
    const host = $('player');
    host.innerHTML = '';
    let derived = {};
    try {
        derived = await fetch(`docs/${doc.id}/derived.json`).then((r) => r.json());
    } catch {}
    const w = derived.width || 400, h = derived.height || 400;
    $('dims').textContent = `${w}×${h}${derived.bytes ? ` · ${derived.bytes} B` : ''}`;
    try {
        state.handle = RC.createPlayer(host, { width: w, height: h });
        await state.handle.loadFromUrl(`docs/${doc.id}/doc.rc`);
    } catch {
        host.textContent = 'This document could not be played.';
    }
}

// ── saving ───────────────────────────────────────────────────────────────────

function markDirty(id) {
    state.dirty.add(id);
    state.touched.add(id);
    updateStatus();
    clearTimeout(markDirty.t);
    markDirty.t = setTimeout(flush, 1200);
}

function updateStatus(extra) {
    const bits = [];
    if (state.dirty.size) bits.push(`${state.dirty.size} unsaved`);
    if (state.touched.size) bits.push(`${state.touched.size} edited`);
    if (extra) bits.push(extra);
    $('cstatus').textContent = bits.join(' · ');
    $('commit').disabled = !state.live || state.touched.size === 0;
}

/** Write every dirty document. Called before navigating, on idle, and on unload. */
async function flush() {
    if (!state.live || state.saving || !state.dirty.size) return;
    state.saving = true;
    const ids = [...state.dirty];
    state.dirty.clear();
    try {
        for (const id of ids) {
            const doc = state.docs.find((d) => d.id === id);
            if (!doc) continue;
            const r = await api('/api/save', { id, description: doc.description,
                                               tags: doc.tags });
            if (!r.ok) { state.dirty.add(id); updateStatus(r.error || 'save failed'); }
        }
        recountVocab();
    } finally {
        state.saving = false;
        updateStatus();
    }
}

/** Counts shown on the chips come from the documents in memory, so they move as you tag. */
function recountVocab() {
    const v = {};
    for (const d of state.docs) for (const t of d.tags) v[t] = (v[t] || 0) + 1;
    state.vocab = v;
    paintTags();
}

// ── filtering and navigation ─────────────────────────────────────────────────

function applyFilter() {
    const mode = $('filter').value;
    const keep = {
        all: () => true,
        untagged: (d) => d.tags.length === 0,
        nodesc: (d) => !d.description.trim(),
        touched: (d) => state.touched.has(d.id),
    }[mode] || (() => true);
    const was = current();
    state.view = state.docs.filter(keep);
    const i = was ? state.view.findIndex((d) => d.id === was.id) : 0;
    show(i >= 0 ? i : 0);
}

function go(delta) { show(state.at + delta); }

// ── wiring ───────────────────────────────────────────────────────────────────

async function main() {
    let data = null;
    try {
        data = await api('/api/docs');
        state.live = Array.isArray(data.docs);
    } catch { state.live = false; }

    if (!state.live) {
        // Published copy: read the catalog so the page still shows something, but write
        // nothing. Controls are disabled rather than silently doing nothing.
        $('cbanner').hidden = false;
        try {
            const text = await fetch('catalog/corpus.jsonl').then((r) => r.text());
            state.docs = text.trim().split('\n').map((l) => JSON.parse(l))
                .map((e) => ({ id: e.id, title: e.title, description: e.description || '',
                               tags: e.tags || [] }));
        } catch { state.docs = []; }
        recountVocab();
        for (const el of ['desc', 'newtag', 'commit']) $(el).disabled = true;
    } else {
        state.docs = data.docs;
        state.vocab = data.vocab || {};
    }

    applyFilter();
    const want = decodeURIComponent(location.hash.slice(1));
    if (want) {
        const i = state.view.findIndex((d) => d.id === want);
        if (i >= 0) show(i);
    }
    updateStatus();

    $('prev').onclick = () => go(-1);
    $('next').onclick = () => go(1);
    $('filter').onchange = applyFilter;

    $('desc').addEventListener('input', () => {
        const doc = current();
        if (!doc || !state.live) return;
        doc.description = $('desc').value;
        markDirty(doc.id);
    });

    $('tags').addEventListener('click', (e) => {
        const b = e.target.closest('.tagchip');
        if (b) toggleTag(b.dataset.tag);
    });

    $('newtagform').addEventListener('submit', (e) => {
        e.preventDefault();
        const t = normTag($('newtag').value);
        if (!t) return;
        // A new tag joins the palette for the rest of the session even before any document
        // carries it, so it can be applied to several in a row without retyping.
        if (!state.extra.includes(t) && !(t in state.vocab)) state.extra.push(t);
        const doc = current();
        if (doc && !doc.tags.includes(t)) { doc.tags.push(t); doc.tags.sort(); markDirty(doc.id); }
        $('newtag').value = '';
        paintTags();
    });

    $('jump').addEventListener('change', () => {
        const q = $('jump').value.trim().toLowerCase();
        if (!q) return;
        const i = state.view.findIndex((d) => d.id.toLowerCase().includes(q)
                                           || (d.title || '').toLowerCase().includes(q));
        if (i >= 0) { show(i); $('jump').value = ''; }
    });

    $('commit').onclick = async () => {
        await flush();
        $('commit').disabled = true;
        updateStatus('committing…');
        const r = await api('/api/commit', { message: 'curate: tags and descriptions' });
        if (r.ok) { state.touched.clear(); updateStatus(`committed ${r.commit}`); }
        else updateStatus(r.error || 'commit failed');
    };

    addEventListener('keydown', (e) => {
        const typing = /^(INPUT|TEXTAREA)$/.test(e.target.tagName);
        if (typing && !(e.metaKey || e.ctrlKey)) return;
        if (e.key === 'ArrowLeft') { e.preventDefault(); go(-1); }
        else if (e.key === 'ArrowRight') { e.preventDefault(); go(1); }
        else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); go(1); }
        else if (!typing && /^[1-9]$/.test(e.key)) {
            const t = paletteTags()[Number(e.key) - 1];
            if (t) { e.preventDefault(); toggleTag(t); }
        }
    });

    addEventListener('beforeunload', (e) => {
        if (state.dirty.size) { flush(); e.preventDefault(); e.returnValue = ''; }
    });
}

main();
