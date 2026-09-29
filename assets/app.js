// The gallery: facet filtering and a windowed grid.
//
// Query cost is independent of corpus size. facets.json carries, for every facet value, a
// delta+varint postings list of the documents that have it; filtering is set intersection over
// those lists. Card metadata lives in shards that are fetched only when a card is about to be
// shown, so scrolling costs what is on screen rather than what is in the corpus.

import { preview } from './preview.js';

const S = {
    facets: null,
    total: 0,
    shardSize: 500,
    shards: new Map(),        // shard index -> array of card records
    selected: new Map(),      // facet kind -> Set of selected values
    matching: [],             // doc indices passing the filter, ascending
    query: '',
};

const grid = () => document.getElementById('grid');

// ── postings ─────────────────────────────────────────────────────────────────

function decodePostings(b64) {
    const bin = atob(b64);
    const out = [];
    let cur = 0, shift = 0, prev = 0;
    for (let i = 0; i < bin.length; i++) {
        const byte = bin.charCodeAt(i);
        cur |= (byte & 0x7f) << shift;
        if (byte & 0x80) { shift += 7; continue; }
        prev += cur;
        out.push(prev);
        cur = 0; shift = 0;
    }
    return out;
}

function intersect(a, b) {
    const out = [];
    let i = 0, j = 0;
    while (i < a.length && j < b.length) {
        if (a[i] === b[j]) { out.push(a[i]); i++; j++; }
        else if (a[i] < b[j]) i++;
        else j++;
    }
    return out;
}

function union(lists) {
    if (lists.length === 1) return lists[0];
    const seen = new Set();
    for (const l of lists) for (const v of l) seen.add(v);
    return [...seen].sort((x, y) => x - y);
}

// Facets whose values are properties a document can hold several of at once. Selecting two
// of these NARROWS: "uses drawCircle AND drawPath". `source` is deliberately excluded - a
// document has exactly one, so intersecting two sources would always return nothing.
const AND_FACETS = new Set(['api', 'flag', 'authoring', 'tag']);

function applyFilter() {
    let result = null;
    for (const [kind, values] of S.selected) {
        if (!values.size) continue;
        const lists = [...values].map((v) => decodePostings(S.facets[kind][v].p));
        const merged = AND_FACETS.has(kind)
            ? lists.reduce((a, b) => intersect(a, b))
            : union(lists);
        result = result === null ? merged : intersect(result, merged);
    }
    if (result === null) {
        result = Array.from({ length: S.total }, (_, i) => i);
    }
    S.matching = result;
    renderCounts();
    layout(true);
}

// ── shards ───────────────────────────────────────────────────────────────────

async function shard(n) {
    if (S.shards.has(n)) return S.shards.get(n);
    const p = fetch(`catalog/docs-${String(n).padStart(3, '0')}.json`)
        .then((r) => r.json())
        .then((arr) => { const m = new Map(arr.map((r) => [r.i, r])); S.shards.set(n, m); return m; });
    S.shards.set(n, p);
    return p;
}

async function record(idx) {
    const m = await shard(Math.floor(idx / S.shardSize));
    return m.get(idx);
}

// ── windowed grid ────────────────────────────────────────────────────────────

const CARD_W = 232, CARD_H = 286, GAP = 16;
let cols = 1, mounted = new Map();   // idx -> {el, cancel}

function layout(reset) {
    const g = grid();
    if (reset) {
        for (const { el, cancel } of mounted.values()) { cancel && cancel(); el.remove(); }
        mounted.clear();
        g.scrollTop = 0;
    }
    const width = g.clientWidth;
    cols = Math.max(1, Math.floor((width + GAP) / (CARD_W + GAP)));
    const rows = Math.ceil(S.matching.length / cols);
    document.getElementById('spacer').style.height = `${rows * (CARD_H + GAP)}px`;
    paint();
}

function paint() {
    const g = grid();
    const top = g.scrollTop, height = g.clientHeight;
    const firstRow = Math.max(0, Math.floor(top / (CARD_H + GAP)) - 1);
    const lastRow = Math.ceil((top + height) / (CARD_H + GAP)) + 1;
    const from = firstRow * cols;
    const to = Math.min(S.matching.length, lastRow * cols);

    for (const [idx, m] of mounted) {
        if (idx < from || idx >= to) { m.cancel && m.cancel(); m.el.remove(); mounted.delete(idx); }
    }
    for (let i = from; i < to; i++) {
        if (mounted.has(i)) continue;
        const el = document.createElement('a');
        el.className = 'card';
        el.style.transform =
            `translate(${(i % cols) * (CARD_W + GAP)}px, ${Math.floor(i / cols) * (CARD_H + GAP)}px)`;
        el.innerHTML = '<div class="thumb"><img alt=""></div><div class="meta"></div>';
        grid().querySelector('.plane').appendChild(el);
        const entry = { el, cancel: null };
        mounted.set(i, entry);
        hydrate(i, entry);
    }
}

async function hydrate(i, entry) {
    const docIdx = S.matching[i];
    const r = await record(docIdx);
    if (!r || !entry.el.isConnected) return;
    entry.el.href = `doc.html?id=${encodeURIComponent(r.id)}`;
    entry.el.querySelector('.meta').innerHTML =
        `<div class="t">${esc(r.t)}</div>
         <div class="sub">${esc(r.s)}${r.w ? ` · ${r.w}×${r.h}` : ''} · ${(r.b / 1024).toFixed(1)} KB</div>
         <div class="chips">${r.f.map((f) => `<span class="chip">${esc(f)}</span>`).join('')}</div>`;
    entry.cancel = preview(r.id, entry.el.querySelector('img'), 320);
}

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ── facet UI ─────────────────────────────────────────────────────────────────

const KIND_LABEL = { source: 'Source', api: 'API used', flag: 'Features', authoring: 'Authored in' };

function renderFacets() {
    const host = document.getElementById('facets');
    host.innerHTML = '';
    for (const kind of ['api', 'flag', 'source', 'authoring']) {
        const vals = S.facets[kind];
        if (!vals || !Object.keys(vals).length) continue;
        const sec = document.createElement('section');
        const mode = AND_FACETS.has(kind) ? 'all of' : 'any of';
        sec.innerHTML =
            `<h3>${KIND_LABEL[kind] || kind}<span class="mode">${mode}</span></h3>`;
        const wrap = document.createElement('div');
        wrap.className = 'facet-values';
        for (const [v, info] of Object.entries(vals).sort((a, b) => b[1].n - a[1].n)) {
            const b = document.createElement('button');
            b.className = 'facet';
            b.innerHTML = `${esc(v)} <span class="n">${info.n}</span>`;
            b.onclick = () => {
                const set = S.selected.get(kind) || new Set();
                set.has(v) ? set.delete(v) : set.add(v);
                S.selected.set(kind, set);
                b.classList.toggle('on', set.has(v));
                applyFilter();
            };
            wrap.appendChild(b);
        }
        sec.appendChild(wrap);
        host.appendChild(sec);
    }
}

function renderCounts() {
    const any = [...S.selected.values()].some((s) => s.size);
    document.getElementById('count').textContent =
        `${S.matching.length} of ${S.total} documents`;
    document.getElementById('clear').hidden = !any;
}

// ── boot ─────────────────────────────────────────────────────────────────────

async function main() {
    const f = await (await fetch('catalog/facets.json')).json();
    S.facets = f.facets;
    S.total = f.total;
    S.shardSize = f.shardSize || 500;
    renderFacets();
    applyFilter();

    grid().addEventListener('scroll', () => requestAnimationFrame(paint), { passive: true });
    addEventListener('resize', () => layout(false));
    document.getElementById('clear').onclick = () => {
        S.selected.clear();
        document.querySelectorAll('.facet.on').forEach((b) => b.classList.remove('on'));
        applyFilter();
    };
}

main();
