// Operation index: which documents use each operation, and which operations have none.

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const EXAMPLES_SHOWN = 6;

let ops = {}, coverage = {};

function render(filter = '') {
    const f = filter.trim().toUpperCase();
    const rows = Object.entries(ops)
        .filter(([name]) => !f || name.includes(f))
        .sort((a, b) => b[1].documents - a[1].documents);

    document.getElementById('oplist').innerHTML = rows.map(([name, o]) => `
        <div class="op-row">
          <div class="op-head">
            <span class="op-name">${esc(name)}</span>
            <span class="op-meta">${o.opcode != null ? `opcode ${o.opcode} · ` : ''}${o.documents} document${o.documents === 1 ? '' : 's'}</span>
          </div>
          <div class="op-examples">
            ${o.examples.slice(0, EXAMPLES_SHOWN).map((id) =>
                `<a href="doc.html?id=${encodeURIComponent(id)}">${esc(id)}</a>`).join('')}
            ${o.examples.length > EXAMPLES_SHOWN
                ? `<span class="dim">+${o.documents - EXAMPLES_SHOWN} more</span>` : ''}
          </div>
        </div>`).join('') || '<p class="dim">No operation matches that.</p>';
}

async function main() {
    [ops, coverage] = await Promise.all([
        fetch('catalog/by-op.json').then((r) => r.json()),
        fetch('catalog/coverage.json').then((r) => r.json()),
    ]);

    const pct = Math.round(coverage.covered / coverage.knownOperations * 100);
    document.getElementById('summary').innerHTML =
        `<strong>${coverage.covered} of ${coverage.knownOperations}</strong> operations have at
         least one example (${pct}%).`;

    render();
    document.getElementById('q').addEventListener('input', (e) => render(e.target.value));

    document.getElementById('uncovered').innerHTML =
        coverage.uncovered.map((n) => `<span class="facet">${esc(n)}</span>`).join('');
    // Stated rather than buried: operations used only by documents the cataloguing decoder
    // cannot read are invisible here, so this list may overstate what is genuinely missing.
    document.getElementById('uncovered-note').textContent =
        `${coverage.uncovered.length} operations. Note that ${coverage.undecodableDocuments} ` +
        `documents in the corpus cannot be decoded by the cataloguing tool, so an operation ` +
        `listed here may still have an example among those.`;
}

main();
