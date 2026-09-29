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
    mergedByKind: new Map(),  // facet kind -> its own merged postings
    buttons: null,            // facet kind -> value -> {btn, n}
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
    S.mergedByKind = new Map();
    for (const [kind, values] of S.selected) {
        if (!values.size) continue;
        const lists = [...values].map((v) => decodePostings(S.facets[kind][v].p));
        const merged = AND_FACETS.has(kind)
            ? lists.reduce((a, b) => intersect(a, b))
            : union(lists);
        S.mergedByKind.set(kind, merged);
        result = result === null ? merged : intersect(result, merged);
    }
    if (result === null) {
        result = Array.from({ length: S.total }, (_, i) => i);
    }
    S.matching = result;
    renderCounts();
    updateAvailability();
    layout(true);
}

/**
 * Show how many documents each value would actually yield, and disable the dead ends.
 *
 * With AND inside a facet it is easy to pick a combination nothing satisfies - shaders and
 * particles share no document here - and an empty grid does not say whether that is a bug or
 * the honest answer. Each value is therefore costed against the current selection and greyed
 * when it would give nothing.
 *
 * The base differs by facet kind. For an AND facet a new value narrows what is already
 * matched, so it is costed against the live result. For an OR facet (source) a new value ADDS
 * to its own group, so it is costed against the constraints from the OTHER facets only -
 * costing it against the live result would make every unselected source look empty as soon as
 * one was chosen.
 */
function updateAvailability() {
    if (!S.buttons) return;
    const all = () => Array.from({ length: S.total }, (_, i) => i);

    for (const [kind, entries] of S.buttons) {
        let base;
        if (AND_FACETS.has(kind)) {
            base = S.matching;
        } else {
            base = null;
            for (const [k, merged] of S.mergedByKind) {
                if (k === kind) continue;
                base = base === null ? merged : intersect(base, merged);
            }
            if (base === null) base = all();
        }
        const selected = S.selected.get(kind) || new Set();
        for (const [value, ui] of entries) {
            if (selected.has(value)) {          // never disable what is selected, or it cannot be undone
                ui.btn.classList.remove('off');
                ui.n.textContent = S.facets[kind][value].n;
                continue;
            }
            const n = intersect(base, decodePostings(S.facets[kind][value].p)).length;
            ui.n.textContent = n;
            ui.btn.classList.toggle('off', n === 0);
        }
    }
    (S.facetApply || []).forEach((f) => f());
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

const CARD_W = 232, CARD_H = 330, GAP = 16;
const FACET_VISIBLE = 12;   // values shown before a facet collapses behind 'show all'
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
    // The full description goes in title= as well as the clamped line, so a truncated one is
    // still readable on hover without opening the document.
    entry.el.title = stripTags(r.d);
    entry.el.querySelector('.meta').innerHTML =
        `<div class="t">${esc(r.t)}</div>
         <div class="sub">${esc(r.s)}${r.w ? ` · ${r.w}×${r.h}` : ''} · ${(r.b / 1024).toFixed(1)} KB</div>
         ${r.d ? `<div class="desc">${esc(stripTags(r.d))}</div>` : ''}
         <div class="chips">${(r.g || []).map((t) => `<span class="chip tag">#${esc(t)}</span>`).join('')}${
             r.f.map((f) => `<span class="chip">${esc(f)}</span>`).join('')}</div>`;
    entry.cancel = preview(r.id, entry.el.querySelector('img'), 320);
}

const stripTags = (s) => String(s || '').replace(/#[A-Za-z0-9][\w-]*/g, '').replace(/\s+/g, ' ').trim();

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ── facet UI ─────────────────────────────────────────────────────────────────

const KIND_LABEL = { source: 'Source', api: 'API used', flag: 'Features',
                     authoring: 'Authored in', tag: 'Hashtags' };

function renderFacets() {
    const host = document.getElementById('facets');
    host.innerHTML = '';
    S.buttons = new Map();
    // Compact, high-signal facets first. Hashtags last because its vocabulary is the one that
    // grows: with 30 values it occupied 413px at the top of the sidebar and pushed "Authored
    // in" to y=969 in an 895px column, i.e. off-screen entirely unless you thought to scroll.
    for (const kind of ['source', 'authoring', 'flag', 'api', 'tag']) {
        const vals = S.facets[kind];
        if (!vals || !Object.keys(vals).length) continue;
        const sec = document.createElement('section');
        const mode = AND_FACETS.has(kind) ? 'all of' : 'any of';
        sec.innerHTML =
            `<h3>${KIND_LABEL[kind] || kind}<span class="mode">${mode}</span></h3>`;
        const wrap = document.createElement('div');
        wrap.className = 'facet-values';
        const reg = new Map();
        S.buttons.set(kind, reg);
        const entries = Object.entries(vals).sort((a, b) => b[1].n - a[1].n);
        for (const [v, info] of entries) {
            const b = document.createElement('button');
            b.className = 'facet';
            b.innerHTML = `${esc(v)} <span class="n">${info.n}</span>`;
            reg.set(v, { btn: b, n: b.querySelector('.n') });
            b.onclick = () => {
                if (b.classList.contains('off')) return;
                const set = S.selected.get(kind) || new Set();
                set.has(v) ? set.delete(v) : set.add(v);
                S.selected.set(kind, set);
                b.classList.toggle('on', set.has(v));
                applyFilter();
            };
            wrap.appendChild(b);
        }
        sec.appendChild(wrap);
        // Long facets are capped so no single section can bury the ones below it. The cap is
        // on display only - a hidden value still filters once revealed, and a selected value
        // is always shown so the current filter is never invisible.
        if (entries.length > FACET_VISIBLE) {
            const more = document.createElement('button');
            more.className = 'more';
            const apply = () => {
                const open = more.dataset.open === '1';
                [...wrap.children].forEach((b, i) => {
                    b.hidden = !open && i >= FACET_VISIBLE && !b.classList.contains('on');
                });
                more.textContent = open
                    ? 'show fewer' : `show all ${entries.length}`;
            };
            more.onclick = () => { more.dataset.open = more.dataset.open === '1' ? '0' : '1'; apply(); };
            more.dataset.open = '0';
            apply();
            sec.appendChild(more);
            S.facetApply = S.facetApply || [];
            S.facetApply.push(apply);
        }
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
