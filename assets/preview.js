// Client-side preview generation.
//
// The corpus stores no thumbnails. A card fetches the .rc it needs anyway, plays exactly one
// frame, snapshots the canvas, and hands the WebGL context back. The image is then cached in
// IndexedDB, so a second visit costs nothing at all.
//
// Two constraints drive the shape of this file:
//
//  * A browser allows only ~16 live WebGL contexts and silently kills the oldest beyond that.
//    Every player MUST be destroyed (not merely stopped) once its frame is captured, or a
//    scrolling grid blanks the documents it drew first. RcPlayerHandle.destroy() releases the
//    context; player.stop() does not.
//  * Instantiating a player is expensive. Renders are queued with a small concurrency limit
//    rather than fired per card, or scrolling stutters badly.

const DB_NAME = 'rc-previews';
const STORE = 'png';
// Bump when the player or the capture path changes, so stale images are not served forever.
export const PREVIEW_VERSION = 4;

// Every cache operation is raced against a timeout, and the cache is optional by construction.
//
// This is not defensive padding. indexedDB.open() can hang with no success, error OR blocked
// event ever firing - headless Chrome does exactly this, and private-browsing modes and
// storage-denied contexts behave similarly. Awaiting it unguarded means no preview is ever
// drawn and the grid stays empty with nothing in the console to explain why.
const CACHE_TIMEOUT_MS = 1500;

function withTimeout(promise, ms, fallback = null) {
    return Promise.race([
        promise,
        new Promise((res) => setTimeout(() => res(fallback), ms)),
    ]);
}

let dbp = null;
function db() {
    if (dbp) return dbp;
    dbp = withTimeout(new Promise((res) => {
        let r;
        try { r = indexedDB.open(DB_NAME, 1); } catch { return res(null); }
        r.onupgradeneeded = () => r.result.createObjectStore(STORE);
        r.onsuccess = () => res(r.result);
        r.onerror = () => res(null);
        r.onblocked = () => res(null);
    }), CACHE_TIMEOUT_MS);
    return dbp;
}

async function cacheGet(key) {
    const d = await db();
    if (!d) return null;
    return withTimeout(new Promise((res) => {
        try {
            const tx = d.transaction(STORE, 'readonly').objectStore(STORE).get(key);
            tx.onsuccess = () => res(tx.result || null);
            tx.onerror = () => res(null);
        } catch { res(null); }
    }), CACHE_TIMEOUT_MS);
}

async function cachePut(key, blob) {
    const d = await db();
    if (!d) return;         // no cache available: previews still render, just never persist
    try {
        d.transaction(STORE, 'readwrite').objectStore(STORE).put(blob, key);
    } catch { /* quota: previews regenerate, so losing the cache is survivable */ }
}

export async function clearPreviewCache() {
    const d = await db();
    if (d) d.transaction(STORE, 'readwrite').objectStore(STORE).clear();
}

// ── Render queue ──────────────────────────────────────────────────────────────

const MAX_CONCURRENT = 4;
let active = 0;
const pending = [];

function pump() {
    while (active < MAX_CONCURRENT && pending.length) {
        const job = pending.shift();
        if (job.cancelled) continue;
        active++;
        job.run().finally(() => { active--; pump(); });
    }
}

function enqueue(run) {
    const job = { run, cancelled: false };
    pending.push(job);
    pump();
    return () => { job.cancelled = true; };
}

// ── Capture ───────────────────────────────────────────────────────────────────

let stage = null;
function stageEl() {
    if (stage) return stage;
    stage = document.createElement('div');
    // Off-screen rather than display:none - a hidden canvas can be skipped by the compositor
    // and read back blank.
    stage.style.cssText = 'position:fixed;left:-10000px;top:0;width:1px;height:1px;overflow:hidden';
    document.body.appendChild(stage);
    return stage;
}

async function capture(rcUrl, w, h) {
    const host = document.createElement('div');
    stageEl().appendChild(host);
    let handle = null;
    try {
        handle = RC.createPlayer(host, { width: w, height: h });
        await handle.loadFromArrayBuffer(await (await fetch(rcUrl)).arrayBuffer());
        handle.player.repaint();
        // Shader programs compile asynchronously; the first frame of a shader document is blank
        // without a beat here. Cheap insurance for non-shader documents too.
        await new Promise((r) => setTimeout(r, 32));
        handle.player.repaint();
        // toDataURL, not toBlob. toBlob's callback is never invoked in headless Chrome - the
        // capture simply hangs forever with no error - which makes the whole grid untestable.
        // toDataURL encodes synchronously and has no callback to drop. WebP is worth asking
        // for: measured 4.8 KB against PNG's 50 KB for the same frame, and browsers that
        // cannot encode it silently hand back PNG, which is still correct.
        const dataUrl = handle.canvas.toDataURL('image/webp');
        if (!dataUrl.startsWith('data:image/')) return null;
        return await (await fetch(dataUrl)).blob();
    } finally {
        // Unconditional: on any error path the context must still be handed back.
        if (handle) handle.destroy();
        host.remove();
    }
}

/**
 * Put a still preview of `id` into `imgEl`. Returns a cancel function.
 */
export function preview(id, imgEl, size = 320) {
    const key = `${id}|${size}|${PREVIEW_VERSION}`;
    let cancelled = false;
    let dequeue = () => {};

    (async () => {
        const hit = await cacheGet(key);
        if (cancelled) return;
        if (hit) { imgEl.src = URL.createObjectURL(hit); imgEl.dataset.state = 'cached'; return; }

        dequeue = enqueue(async () => {
            if (cancelled) return;
            try {
                const blob = await capture(`docs/${id}/doc.rc`, size, size);
                if (cancelled || !blob) return;
                imgEl.src = URL.createObjectURL(blob);
                imgEl.dataset.state = 'rendered';
                cachePut(key, blob);
            } catch (e) {
                imgEl.dataset.state = 'error';
                imgEl.alt = `could not render ${id}`;
            }
        });
    })();

    return () => { cancelled = true; dequeue(); };
}
