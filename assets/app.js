// The gallery: facet filtering, search, sort and a windowed grid.
//
// Query cost stays independent of corpus size. facets.json carries, for every facet value, a
// delta+varint postings list; filtering is set intersection over those lists. Card metadata
// lives in shards fetched only for the rows about to be shown.
//
// Search and sort are the exception: both need every matching record, so they force the shards
// to load. That is bounded - three shards for 1101 documents - and happens once.

import { preview } from './preview.js';

const stripTags = (s) => String(s || '').replace(/#[A-Za-z0-9][\w-]*/g, '').replace(/\s+/g, ' ').trim();
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const S = {
    facets: null, total: 0, shardSize: 500,
    shards: new Map(),
    selected: new Map(),
    mergedByKind: new Map(),
    buttons: null,
    facetApply: [],
    matching: [],
    matchingAsc: [],
    query: '',
    sort: 'added',
    allRecords: null,
};

const grid = () => document.getElementById('grid');

// Facets whose values are properties a document can hold several of at once, so selecting two
// NARROWS. `source` is excluded: a document has exactly one, and intersecting two would always
// return nothing.
const AND_FACETS = new Set(['api', 'flag', 'authoring', 'tag']);
const KIND_LABEL = { source: 'Source', authoring: 'Authored in', flag: 'Features',
                     api: 'API used', tag: 'Hashtags' };
const KIND_ORDER = ['source', 'authoring', 'flag', 'api', 'tag'];
const FACET_VISIBLE = 8;
const QUICK_CHIPS = 11;

// ── postings ─────────────────────────────────────────────────────────────────

function decodePostings(b64) {
    const bin = atob(b64);
    const out = [];
    let cur = 0, shift = 0, prev = 0;
    for (let i = 0; i < bin.length; i++) {
        const byte = bin.charCodeAt(i);
        cur |= (byte & 0x7f) << shift;
        if (byte & 0x80) { shift += 7; continue; }
        prev += cur; out.push(prev); cur = 0; shift = 0;
    }
    return out;
}
const intersect = (a, b) => {
    const out = []; let i = 0, j = 0;
    while (i < a.length && j < b.length) {
        if (a[i] === b[j]) { out.push(a[i]); i++; j++; }
        else if (a[i] < b[j]) i++; else j++;
    }
    return out;
};
const union = (ls) => ls.length === 1 ? ls[0] : [...new Set(ls.flat())].sort((x, y) => x - y);

// ── shards ───────────────────────────────────────────────────────────────────

const shardPromise = new Map();
function shard(n) {
    if (!shardPromise.has(n)) {
        shardPromise.set(n, fetch(`catalog/docs-${String(n).padStart(3, '0')}.json`)
            .then((r) => r.json())
            .then((arr) => { const m = new Map(arr.map((r) => [r.i, r])); S.shards.set(n, m); return m; }));
    }
    return shardPromise.get(n);
}
async function record(i) {
    await shard(Math.floor(i / S.shardSize));
    return (S.shards.get(Math.floor(i / S.shardSize)) || new Map()).get(i);
}
async function allRecords() {
    if (S.allRecords) return S.allRecords;
    const n = Math.ceil(S.total / S.shardSize);
    await Promise.all(Array.from({ length: n }, (_, k) => shard(k)));
    S.allRecords = new Map();
    for (const m of S.shards.values()) for (const [i, r] of m) S.allRecords.set(i, r);
    return S.allRecords;
}

// ── filter / search / sort ───────────────────────────────────────────────────

async function applyFilter() {
    let result = null;
    S.mergedByKind = new Map();
    for (const [kind, values] of S.selected) {
        if (!values.size) continue;
        const lists = [...values].map((v) => decodePostings(S.facets[kind][v].p));
        const merged = AND_FACETS.has(kind) ? lists.reduce((a, b) => intersect(a, b)) : union(lists);
        S.mergedByKind.set(kind, merged);
        result = result === null ? merged : intersect(result, merged);
    }
    if (result === null) result = Array.from({ length: S.total }, (_, i) => i);

    const recs = await allRecords();
    if (S.query) {
        const q = S.query.toLowerCase();
        result = result.filter((i) => {
            const r = recs.get(i);
            return r && (r.id.toLowerCase().includes(q) ||
                         (r.t || '').toLowerCase().includes(q) ||
                         (r.d || '').toLowerCase().includes(q));
        });
    }
    const key = {
        added: (r) => String(r?.at || ''),      // descending, newest ingest first
        name: (r) => (r?.t || r?.id || '').toLowerCase(),
        size: (r) => r?.b || 0,
        ops: (r) => r?.o || 0,
    }[S.sort];
    const desc = S.sort !== 'name';
    result = [...result].sort((a, b) => {
        const ka = key(recs.get(a)), kb = key(recs.get(b));
        if (ka === kb) return a - b;
        return (ka < kb ? -1 : 1) * (desc ? -1 : 1);
    });

    // Two views of the same set. intersect() is a merge join and REQUIRES ascending input, so
    // availability costing must use the ascending set; sorting for display broke it silently,
    // reporting 14 documents authored in json instead of 636.
    S.matchingAsc = [...result].sort((a, b) => a - b);
    S.matching = result;
    renderCounts();
    updateAvailability();
    layout(true);
}

// ── windowed grid ────────────────────────────────────────────────────────────

let CARD_W = 268, CARD_H = 344;
const GAP = 18;
let cols = 1;
const mounted = new Map();

function layout(reset) {
    const g = grid();
    if (reset) {
        for (const { el, cancel } of mounted.values()) { cancel && cancel(); el.remove(); }
        mounted.clear(); g.scrollTop = 0;
    }
    const list = g.classList.contains('list');
    CARD_W = list ? Math.max(320, g.clientWidth - GAP * 2) : 268;
    CARD_H = list ? 116 : 344;
    cols = list ? 1 : Math.max(1, Math.floor((g.clientWidth - GAP) / (CARD_W + GAP)));
    document.getElementById('spacer').style.height =
        `${Math.ceil(S.matching.length / cols) * (CARD_H + GAP)}px`;
    paint();
}

function paint() {
    const g = grid();
    const first = Math.max(0, Math.floor(g.scrollTop / (CARD_H + GAP)) - 1);
    const last = Math.ceil((g.scrollTop + g.clientHeight) / (CARD_H + GAP)) + 1;
    const from = first * cols, to = Math.min(S.matching.length, last * cols);

    for (const [i, m] of mounted) {
        if (i < from || i >= to) { m.cancel && m.cancel(); m.el.remove(); mounted.delete(i); }
    }
    for (let i = from; i < to; i++) {
        if (mounted.has(i)) continue;
        const el = document.createElement('div');
        el.className = 'card';
        el.style.transform =
            `translate(${(i % cols) * (CARD_W + GAP)}px, ${Math.floor(i / cols) * (CARD_H + GAP)}px)`;
        el.style.width = `${CARD_W}px`;
        el.style.height = `${CARD_H}px`;
        el.innerHTML =
            `<div class="thumb"><img alt="">
               <div class="thumb-actions">
                 <button class="act play" title="Play here">▶</button>
                 <a class="act more" title="Open document">···</a>
               </div>
             </div><div class="meta"></div>`;
        g.querySelector('.plane').appendChild(el);
        const entry = { el, cancel: null };
        mounted.set(i, entry);
        hydrate(i, entry);
    }
}

async function hydrate(i, entry) {
    const r = await record(S.matching[i]);
    if (!r || !entry.el.isConnected) return;
    const href = `doc.html?id=${encodeURIComponent(r.id)}`;
    const desc = stripTags(r.d);
    entry.el.title = desc;
    entry.el.querySelector('.more').href = href;
    entry.el.querySelector('.meta').innerHTML =
        `<a class="t" href="${href}">${esc(r.t)}</a>
         <div class="sub">${esc(r.s)}${r.w ? ` · ${r.w}×${r.h}` : ''} · ${(r.b / 1024).toFixed(1)} KB</div>
         ${desc ? `<div class="desc">${esc(desc)}</div>` : ''}
         <div class="chips">${(r.g || []).slice(0, 3).map((t) =>
             `<span class="chip tag">${esc(t)}</span>`).join('')}</div>`;
    entry.cancel = preview(r.id, entry.el.querySelector('img'), 320);
    entry.el.querySelector('.play').onclick = (ev) => { ev.preventDefault(); playInCard(entry, r); };
}

/**
 * Play a document inside its card.
 *
 * A still preview is enough to browse by, but some documents only make sense moving and
 * opening a page for each is a slow way to find that out. The player is destroyed when the
 * card is recycled - the grid reuses nodes aggressively, and a live player left behind holds a
 * WebGL context, of which a browser allows only ~16.
 */
function playInCard(entry, r) {
    const card = entry.el;
    if (card.dataset.playing === '1') return;
    card.dataset.playing = '1';
    const host = document.createElement('div');
    host.className = 'live';
    card.querySelector('.thumb').appendChild(host);
    const w = r.w || 512, h = r.h || 512;
    const handle = RC.createPlayer(host, { width: w, height: h });
    handle.loadFromUrl(`docs/${r.id}/doc.rc`).then(() => {
        const box = card.querySelector('.thumb').getBoundingClientRect();
        const s = Math.min(box.width / w, box.height / h);
        handle.canvas.style.width = `${Math.round(w * s)}px`;
        handle.canvas.style.height = `${Math.round(h * s)}px`;
    }).catch(() => {});
    const prev = entry.cancel;
    entry.cancel = () => { prev && prev(); handle.destroy(); };
}

// ── facets ───────────────────────────────────────────────────────────────────

function renderFacets() {
    const host = document.getElementById('facets');
    host.innerHTML = '';
    S.buttons = new Map();
    S.facetApply = [];

    for (const kind of KIND_ORDER) {
        const vals = S.facets[kind];
        if (!vals || !Object.keys(vals).length) continue;
        const entries = Object.entries(vals).sort((a, b) => b[1].n - a[1].n);

        const sec = document.createElement('section');
        sec.className = 'facet-sec';
        sec.dataset.open = '0';
        sec.innerHTML =
            `<button class="facet-head" aria-expanded="true">
               <span class="fh-name">${KIND_LABEL[kind] || kind}</span>
               <span class="mode">${AND_FACETS.has(kind) ? 'all of' : 'any of'}</span>
               <span class="chev">⌃</span>
             </button>
             <div class="facet-body">
               ${entries.length > FACET_VISIBLE
                    ? `<input class="facet-search" type="search" spellcheck="false"
                              placeholder="Search ${(KIND_LABEL[kind] || kind).toLowerCase()}…">`
                    : ''}
               <div class="facet-values"></div>
             </div>`;
        const wrap = sec.querySelector('.facet-values');
        const reg = new Map();
        S.buttons.set(kind, reg);

        for (const [v, info] of entries) {
            const row = document.createElement('label');
            row.className = 'fv';
            row.innerHTML = `<input type="checkbox"><span class="fv-name">${esc(v)}</span>` +
                            `<span class="n">${info.n}</span>`;
            const cb = row.querySelector('input');
            cb.onchange = () => {
                const set = S.selected.get(kind) || new Set();
                cb.checked ? set.add(v) : set.delete(v);
                S.selected.set(kind, set);
                row.classList.toggle('on', cb.checked);
                syncQuickChip(v, cb.checked);
                applyFilter();
            };
            reg.set(v, { btn: row, box: cb, n: row.querySelector('.n') });
            wrap.appendChild(row);
        }

        let more = null;
        const applyVisibility = () => {
            const q = (sec.querySelector('.facet-search')?.value || '').toLowerCase();
            const open = sec.dataset.open === '1';
            let shown = 0;
            for (const row of wrap.children) {
                const name = row.querySelector('.fv-name').textContent.toLowerCase();
                const matches = !q || name.includes(q);
                const selected = row.classList.contains('on');
                const room = open || q ? true : shown < FACET_VISIBLE;
                // A selected value is always shown, or the active filter becomes invisible.
                row.hidden = !(matches && (room || selected));
                if (!row.hidden) shown++;
            }
            if (more) {
                more.hidden = !!q;
                more.textContent = open ? 'Show fewer' : `Show more (${entries.length})`;
            }
        };
        if (entries.length > FACET_VISIBLE) {
            more = document.createElement('button');
            more.className = 'more';
            more.onclick = () => {
                sec.dataset.open = sec.dataset.open === '1' ? '0' : '1';
                applyVisibility();
            };
            sec.querySelector('.facet-body').appendChild(more);
        }
        sec.querySelector('.facet-search')?.addEventListener('input', applyVisibility);
        sec.querySelector('.facet-head').onclick = () => {
            const body = sec.querySelector('.facet-body');
            body.hidden = !body.hidden;
            sec.classList.toggle('collapsed', body.hidden);
            sec.querySelector('.facet-head').setAttribute('aria-expanded', String(!body.hidden));
        };
        applyVisibility();
        S.facetApply.push(applyVisibility);
        host.appendChild(sec);
    }
}

/** Cost every value against the current selection and disable the dead ends. */
function updateAvailability() {
    if (!S.buttons) return;
    const all = () => Array.from({ length: S.total }, (_, i) => i);
    for (const [kind, entries] of S.buttons) {
        let base;
        if (AND_FACETS.has(kind)) {
            base = S.matchingAsc;
        } else {
            // An OR facet is costed against the OTHER facets only: its values add within their
            // own group, so costing against the live result would grey every unselected source
            // the moment one was picked.
            base = null;
            for (const [k, merged] of S.mergedByKind) {
                if (k !== kind) base = base === null ? merged : intersect(base, merged);
            }
            if (base === null) base = all();
        }
        const selected = S.selected.get(kind) || new Set();
        for (const [value, ui] of entries) {
            if (selected.has(value)) { ui.btn.classList.remove('off'); ui.box.disabled = false; continue; }
            const n = intersect(base, decodePostings(S.facets[kind][value].p)).length;
            ui.n.textContent = n;
            ui.btn.classList.toggle('off', n === 0);
            ui.box.disabled = n === 0;
        }
    }
    S.facetApply.forEach((f) => f());
}

// ── chips, counts ────────────────────────────────────────────────────────────

function syncQuickChip(value, on) {
    document.querySelectorAll('.quick').forEach((b) => {
        if (b.dataset.v === value) b.classList.toggle('on', on);
    });
}

function renderQuickChips() {
    const host = document.getElementById('quickchips');
    const top = Object.entries(S.facets.tag || {})
        .sort((a, b) => b[1].n - a[1].n).slice(0, QUICK_CHIPS);
    host.innerHTML = top.map(([v]) =>
        `<button class="quick" data-v="${esc(v)}">${esc(v)}</button>`).join('');
    host.querySelectorAll('.quick').forEach((b) => {
        b.onclick = () => {
            const v = b.dataset.v;
            const set = S.selected.get('tag') || new Set();
            set.has(v) ? set.delete(v) : set.add(v);
            S.selected.set('tag', set);
            b.classList.toggle('on', set.has(v));
            const ui = S.buttons.get('tag')?.get(v);
            if (ui) { ui.box.checked = set.has(v); ui.btn.classList.toggle('on', set.has(v)); }
            applyFilter();
        };
    });
}

function renderCounts() {
    const active = [...S.selected.entries()].flatMap(([k, s]) => [...s].map((v) => [k, v]));
    document.getElementById('count').innerHTML =
        `<strong>${S.matching.length.toLocaleString()}</strong> of ${S.total.toLocaleString()} documents`;
    document.getElementById('pills').innerHTML =
        active.map(([k, v]) =>
            `<button class="pill" data-k="${k}" data-v="${esc(v)}">${esc(v)}<span>×</span></button>`).join('')
        + (active.length ? `<button class="pill clear">Clear all</button>` : '');
    document.querySelectorAll('.pill[data-k]').forEach((p) => {
        p.onclick = () => toggleOff(p.dataset.k, p.dataset.v);
    });
    document.querySelector('.pill.clear')?.addEventListener('click', clearAll);
    document.getElementById('filters-count').textContent = String(active.length);
    document.getElementById('filters-badge').classList.toggle('on', active.length > 0);
    document.getElementById('side-active').textContent =
        active.length ? `${active.length} active` : 'none active';
    document.getElementById('clear').hidden = !active.length;
}

function toggleOff(kind, value) {
    const set = S.selected.get(kind);
    if (!set) return;
    set.delete(value);
    const ui = S.buttons.get(kind)?.get(value);
    if (ui) { ui.box.checked = false; ui.btn.classList.remove('on'); }
    syncQuickChip(value, false);
    applyFilter();
}

function clearAll() {
    S.selected.clear();
    document.querySelectorAll('.fv.on').forEach((r) => {
        r.classList.remove('on'); r.querySelector('input').checked = false;
    });
    document.querySelectorAll('.quick.on').forEach((b) => b.classList.remove('on'));
    applyFilter();
}

// ── boot ─────────────────────────────────────────────────────────────────────

function setTheme(mode) {
    document.documentElement.dataset.theme = mode;
    try { localStorage.setItem('rc-theme', mode); } catch {}
    document.getElementById('theme-light').classList.toggle('on', mode === 'light');
    document.getElementById('theme-dark').classList.toggle('on', mode === 'dark');
}

async function main() {
    const f = await (await fetch('catalog/facets.json')).json();
    S.facets = f.facets; S.total = f.total; S.shardSize = f.shardSize || 500;
    document.getElementById('q').placeholder = `Search ${S.total.toLocaleString()} documents…`;
    renderFacets();
    renderQuickChips();
    await applyFilter();

    grid().addEventListener('scroll', () => requestAnimationFrame(paint), { passive: true });
    addEventListener('resize', () => layout(false));
    document.getElementById('clear').onclick = clearAll;

    let t;
    document.getElementById('q').addEventListener('input', (e) => {
        clearTimeout(t);
        const v = e.target.value.trim();
        t = setTimeout(() => { S.query = v; applyFilter(); }, 150);
    });
    document.getElementById('sort').onchange = (e) => { S.sort = e.target.value; applyFilter(); };

    const gv = document.getElementById('view-grid'), lv = document.getElementById('view-list');
    const setView = (list) => {
        grid().classList.toggle('list', list);
        gv.classList.toggle('on', !list);
        lv.classList.toggle('on', list);
        layout(true);
    };
    gv.onclick = () => setView(false);
    lv.onclick = () => setView(true);

    let saved = null;
    try { saved = localStorage.getItem('rc-theme'); } catch {}
    setTheme(saved || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
    document.getElementById('theme-light').onclick = () => setTheme('light');
    document.getElementById('theme-dark').onclick = () => setTheme('dark');

    document.getElementById('filters-badge').onclick = () =>
        document.body.classList.toggle('no-sidebar');
}

main();
