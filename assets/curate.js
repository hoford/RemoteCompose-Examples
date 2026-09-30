// The curation page: the explore gallery plus a star on each card and a commit button.
//
// It talks to tools/curate.py, which runs locally. When that API is absent - which is the
// case on the published site - the page stays useful but read-only rather than showing
// controls that cannot work.

import { init, refresh } from './gallery.js';

const state = { featured: new Set(), dirty: new Set(), onlyFeatured: false, live: false };

const api = (path, body) => fetch(path, body
    ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }
    : undefined).then((r) => r.json());

function setStatus(msg) { document.getElementById('cstatus').textContent = msg; }

function updateCounts() {
    setStatus(`${state.featured.size} featured` +
              (state.dirty.size ? ` · ${state.dirty.size} unsaved` : ''));
    const b = document.getElementById('commit');
    if (b) b.disabled = !state.live || state.dirty.size === 0;
}

async function toggle(id, el) {
    if (!state.live) return;
    const on = !state.featured.has(id);
    on ? state.featured.add(id) : state.featured.delete(id);
    state.dirty.add(id);
    paintStar(el, on);
    updateCounts();
    const r = await api('/api/toggle', { id, on });
    if (!r.ok) setStatus(`could not save ${id}`);
}

/**
 * Is this document featured?
 *
 * Live, the API's set is authoritative because it reflects unsaved toggles. Without the API -
 * the published copy - the catalog's own tag is the only truth there is, and reading the live
 * set instead made "Featured only" return nothing on a site that does have featured documents.
 */
function isFeatured(rec) {
    return state.live ? state.featured.has(rec.id) : (rec.g || []).includes('featured');
}

function paintStar(el, on) {
    // The highlight is set whether or not a star exists: read-only has no star button, and
    // returning early there left featured documents visually indistinguishable.
    el.classList.toggle('is-featured', on);
    const s = el.querySelector('.act.star');
    if (!s) return;
    s.textContent = on ? '★' : '☆';
    s.classList.toggle('on', on);
}

async function main() {
    // Is the local API there? Everything else follows from the answer.
    try {
        const r = await api('/api/list');
        state.featured = new Set(r.featured);
        state.live = true;
    } catch {
        state.live = false;
    }

    if (!state.live) {
        document.getElementById('cbanner').hidden = false;
        document.getElementById('commit').hidden = true;
    }

    await init({
        cardActions: () => state.live ? '<button class="act star" title="Toggle featured">☆</button>' : '',
        onCard: (el, r) => {
            paintStar(el, isFeatured(r));
            const s = el.querySelector('.act.star');
            if (s) s.onclick = (ev) => { ev.preventDefault(); toggle(r.id, el); };
        },
        extraFilter: (rec) => !state.onlyFeatured || isFeatured(rec),
    });
    updateCounts();

    document.getElementById('only').onclick = (e) => {
        state.onlyFeatured = !state.onlyFeatured;
        e.target.classList.toggle('on', state.onlyFeatured);
        refresh();
    };

    const b = document.getElementById('commit');
    b.onclick = async () => {
        b.disabled = true;
        const was = b.textContent;
        b.textContent = 'Committing…';
        const r = await api('/api/commit', {});
        b.textContent = was;
        if (r.ok) {
            state.dirty.clear();
            setStatus(`committed ${r.commit} — ${r.featured} featured`);
        } else {
            setStatus(`failed: ${r.error}`);
        }
        updateCounts();
    };
}

main();
