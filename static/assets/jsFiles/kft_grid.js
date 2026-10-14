/* KFT data grid (approved design: design_preview/index.html#s=grid).
 *
 * One component for every list / report page. Two ways to use it:
 *
 * 1) Enhance a table the server already rendered (rows keep their links, buttons and event handlers):
 *      KFTGrid.fromTable(document.getElementById('users-table'), { storageKey: 'users', exportName: 'Volunteers' });
 *    Column options come from attributes on each <th>:
 *      data-type="number|money|date"  numeric/date sorting (+ right-aligned numbers)
 *      data-sum                      show a total for this column in the footer row
 *      data-sort="false"             not sortable          data-export="false"   left out of exports/search
 *      data-hide="false"             always visible        data-hidden           hidden until the user shows it
 *      data-filter                   adds a drop-down filter built from the column's values
 *      data-filter-options="A|B"     fixed filter options, always listed (values found in the rows are added after)
 *      class="act"                   row actions column (pinned to the right, never exported)
 *    A <td data-order="..."> value is used for sorting instead of the cell text (e.g. ISO dates).
 *
 * 2) Data mode, for pages that load JSON (only the visible page is drawn, so large reports stay fast):
 *      const grid = KFTGrid.create(mountEl, { columns: [{ key, label, type, sum, render, value, exportValue }], ... });
 *      grid.setRows(records);
 *
 * Shared options: storageKey (remembers columns, density, page size), exportName, pageSize, searchPlaceholder,
 * emptyText, title / subtitle / headActions (optional card header), panel (element shown by a "Filters" button).
 * onView(rows) is called after every search / filter / sort / data change with the filtered rows.
 * Methods: setRows(rows), setLoading(bool), setChips([{label, remove}]), refresh().
 */
(function () {
  const esc = (v) => String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } },
  };
  const num = (t) => {
    if (t === null || t === undefined || t === '') return null;
    if (typeof t === 'number') return t;
    const n = parseFloat(String(t).replace(/[^0-9.\-]/g, ''));
    return isNaN(n) ? null : n;
  };
  const dateVal = (t) => {
    if (!t) return null;
    let d = Date.parse(String(t));                                      // ISO / standard formats
    if (isNaN(d)) d = Date.parse(String(t).replace(/\//g, ' '));        // "Aug/31/2025" style used in the app
    return isNaN(d) ? null : d;
  };
  const fmtMoney = (n) => (n === null || n === undefined || isNaN(n)) ? '' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 });
  let seq = 0;

  function Grid(opts) {
    this.o = Object.assign({ pageSize: 25, sizes: [10, 25, 50, 100], searchPlaceholder: 'Search\u2026', emptyText: 'No records to show',
                             noMatchText: 'No records match your search or filters', exportName: 'Export' }, opts);
    this.id = 'dg' + (++seq);
    this.key = this.o.storageKey ? 'kft-grid-' + this.o.storageKey : null;
    const saved = this.key ? store.get(this.key, {}) : {};
    this.hidden = new Set(saved.hidden || this.o.columns.filter((c) => c.hidden).map((c) => c.key));
    this.compact = !!saved.compact;
    this.size = saved.size || this.o.pageSize;
    this.page = 1;
    this.sort = this.o.sort || null;            // { key, dir: 'asc'|'desc' }
    this.search = '';
    this.filters = {};                           // column key -> selected value
    this.extChips = [];
    this.rows = [];
    this.view = [];
    this.build();
  }

  Grid.prototype.save = function () {
    if (this.key) store.set(this.key, { hidden: [...this.hidden], compact: this.compact, size: this.size });
  };

  Grid.prototype.build = function () {
    const o = this.o;
    const root = document.createElement('div');
    root.className = 'dg';
    root.id = this.id;
    const filterSelects = o.columns.filter((c) => c.filter).map((c) =>
      `<select class="form-select" data-filter="${esc(c.key)}" aria-label="${esc(c.label)}"><option value="">All ${esc(c.filterLabel || c.label.toLowerCase())}</option></select>`).join('');
    root.innerHTML = `
      ${o.title ? `<div class="dg-head"><div><h3>${esc(o.title)}</h3>${o.subtitle ? `<div class="sub">${esc(o.subtitle)}</div>` : ''}</div><div class="d-flex gap-2 flex-wrap dg-head-actions"></div></div>` : ''}
      <div class="dg-toolbar">
        <div class="dg-search"><i class="bi bi-search"></i><input type="search" class="form-control" placeholder="${esc(o.searchPlaceholder)}" aria-label="Search"></div>
        ${filterSelects}
        ${o.panel ? '<button type="button" class="btn btn-secondary dg-panel-btn"><i class="bi bi-funnel me-1"></i>Filters</button>' : ''}
        <span class="spacer"></span>
        <div class="dg-seg" role="group" aria-label="Row density"><button type="button" data-d="0">Comfortable</button><button type="button" data-d="1">Compact</button></div>
        <div class="dg-menu-wrap"><button type="button" class="btn btn-secondary dg-cols-btn" aria-haspopup="true"><i class="bi bi-layout-three-columns me-1"></i>Columns</button><div class="dg-menu dg-cols"></div></div>
        <div class="dg-menu-wrap"><button type="button" class="btn btn-secondary dg-exp-btn" aria-haspopup="true"><i class="bi bi-download me-1"></i>Export</button>
          <div class="dg-menu dg-exp">
            <button type="button" data-x="csv"><i class="bi bi-filetype-csv"></i>CSV</button>
            ${window.XLSX ? '<button type="button" data-x="xlsx"><i class="bi bi-file-earmark-excel"></i>Excel</button>' : ''}
            <button type="button" data-x="print"><i class="bi bi-printer"></i>Print</button>
          </div></div>
      </div>
      <div class="dg-chips"></div>
      <div class="dg-scroll"></div>
      <div class="dg-foot">
        <div>Rows per page <select class="form-select ms-1">${o.sizes.map((s) => `<option value="${s}">${s}</option>`).join('')}</select></div>
        <div class="dg-info"></div>
        <ul class="pagination pagination-sm"></ul>
      </div>`;
    this.el = root;
    this.q = (s) => root.querySelector(s);
    if (o.headActions && this.q('.dg-head-actions')) this.q('.dg-head-actions').append(...[].concat(o.headActions));
    if (o.panel) {
      o.panel.classList.add('dg-panel');
      root.insertBefore(o.panel, this.q('.dg-chips'));
      this.q('.dg-panel-btn').addEventListener('click', () => { o.panel.hidden = !o.panel.hidden; });
    }

    // table
    let table = o.table;
    if (!table) { table = document.createElement('table'); table.innerHTML = '<thead></thead><tbody></tbody>'; }
    table.className = 'dgt' + (this.compact ? ' compact' : '');
    table.removeAttribute('style');
    if (!table.tFoot) table.createTFoot();
    this.table = table;
    this.q('.dg-scroll').appendChild(table);
    this.hideStyle = document.createElement('style');
    root.appendChild(this.hideStyle);

    // events
    let t;
    this.q('.dg-search input').addEventListener('input', (e) => { clearTimeout(t); t = setTimeout(() => { this.search = e.target.value.trim(); this.page = 1; this.refresh(); }, 150); });
    root.querySelectorAll('[data-filter]').forEach((sel) => sel.addEventListener('change', () => {
      this.filters[sel.dataset.filter] = sel.value; this.page = 1; this.refresh();
    }));
    root.querySelectorAll('.dg-seg button').forEach((b) => b.addEventListener('click', () => {
      this.compact = b.dataset.d === '1'; this.table.classList.toggle('compact', this.compact); this.paintSeg(); this.save();
    }));
    this.paintSeg();
    const menus = [['.dg-cols-btn', '.dg-cols'], ['.dg-exp-btn', '.dg-exp']];
    menus.forEach(([btn, menu]) => this.q(btn).addEventListener('click', (e) => {
      e.stopPropagation();
      menus.forEach(([, m]) => { if (m !== menu) this.q(m).classList.remove('open'); });
      if (menu === '.dg-cols') this.paintColumnsMenu();
      this.q(menu).classList.toggle('open');
    }));
    document.addEventListener('click', (e) => { if (!root.contains(e.target) || !e.target.closest('.dg-menu')) menus.forEach(([, m]) => this.q(m).classList.remove('open')); });
    this.q('.dg-cols').addEventListener('change', (e) => {
      const k = e.target.dataset.col; if (!k) return;
      e.target.checked ? this.hidden.delete(k) : this.hidden.add(k);
      this.save(); this.applyHidden(); this.renderFoot();
    });
    this.q('.dg-cols').addEventListener('click', (e) => {
      if (e.target.closest('[data-reset]')) { this.hidden = new Set(this.o.columns.filter((c) => c.hidden).map((c) => c.key)); this.save(); this.applyHidden(); this.paintColumnsMenu(); this.renderFoot(); }
    });
    this.q('.dg-exp').addEventListener('click', (e) => {
      const b = e.target.closest('[data-x]'); if (!b) return;
      this.q('.dg-exp').classList.remove('open');
      ({ csv: () => this.exportCsv(), xlsx: () => this.exportXlsx(), print: () => this.print() })[b.dataset.x]();
    });
    const sizeSel = this.q('.dg-foot select');
    if (!o.sizes.includes(this.size)) sizeSel.insertAdjacentHTML('beforeend', `<option value="${this.size}">${this.size}</option>`);
    sizeSel.value = String(this.size);
    sizeSel.addEventListener('change', () => { this.size = Number(sizeSel.value); this.page = 1; this.save(); this.render(); });
    this.q('.pagination').addEventListener('click', (e) => {
      const a = e.target.closest('[data-p]'); if (!a) return;
      e.preventDefault(); this.page = Number(a.dataset.p); this.render();
      this.q('.dg-scroll').scrollTop = 0;
    });
    this.q('.dg-chips').addEventListener('click', (e) => {
      const b = e.target.closest('[data-chip]'); if (!b) return;
      const [kind, k] = b.dataset.chip.split(':');
      if (kind === 's') { this.search = ''; this.q('.dg-search input').value = ''; }
      if (kind === 'f') { this.filters[k] = ''; const s = root.querySelector(`[data-filter="${k}"]`); if (s) s.value = ''; }
      if (kind === 'x') { const c = this.extChips[Number(k)]; if (c && c.remove) c.remove(); return; }
      this.page = 1; this.refresh();
    });
    table.tHead.addEventListener('click', (e) => {
      const th = e.target.closest('th.sortable'); if (!th) return;
      const k = th.dataset.key;
      this.sort = { key: k, dir: this.sort && this.sort.key === k && this.sort.dir === 'asc' ? 'desc' : 'asc' };
      this.page = 1; this.refresh();
    });
  };

  Grid.prototype.paintSeg = function () {
    this.el.querySelectorAll('.dg-seg button').forEach((b) => b.classList.toggle('on', (b.dataset.d === '1') === this.compact));
  };

  Grid.prototype.paintColumnsMenu = function () {
    const list = this.q('.dg-menu-list');
    const scrollTop = list ? list.scrollTop : 0;    // keep the scroll position while ticking boxes
    this.q('.dg-cols').innerHTML = '<div class="mh">Show columns</div><div class="dg-menu-list">' + this.o.columns.filter((c) => c.hideable !== false).map((c) =>
      `<label><input type="checkbox" data-col="${esc(c.key)}" ${this.hidden.has(c.key) ? '' : 'checked'}> ${esc(c.label)}</label>`).join('') +
      '</div><button type="button" data-reset><i class="bi bi-arrow-counterclockwise"></i>Reset columns</button>';
    this.q('.dg-menu-list').scrollTop = scrollTop;
  };

  Grid.prototype.visibleCols = function () { return this.o.columns.filter((c) => !this.hidden.has(c.key)); };

  Grid.prototype.applyHidden = function () {
    const rules = this.o.columns.map((c, i) => this.hidden.has(c.key)
      ? `#${this.id} .dgt tr > :nth-child(${i + 1}):not(.empty) { display: none; }` : '').join('\n');
    this.hideStyle.textContent = rules;
  };

  // ---- data model: every row keeps raw values (sort / search / filter / export) ----
  Grid.prototype.cellValue = function (row, c, i) {
    if (row.el) return row.vals[i];
    if (c.value) return c.value(row.data);
    return row.data[c.key];
  };
  Grid.prototype.cellText = function (row, c, i) {
    if (row.el) return row.texts[i];
    if (c.exportValue) return String(c.exportValue(row.data) ?? '');
    const v = this.cellValue(row, c, i);
    if (c.type === 'money' || c.type === 'number') return v === null || v === undefined || v === '' ? '' : fmtMoney(num(v));
    return String(v ?? '');
  };
  Grid.prototype.sortKey = function (row, c, i) {
    if (row.el && row.orders[i] !== undefined) {
      const o = row.orders[i];
      return c.type === 'number' || c.type === 'money' ? num(o) : c.type === 'date' ? (dateVal(o) ?? null) : String(o).toLowerCase();
    }
    const v = row.el ? row.texts[i] : this.cellValue(row, c, i);
    if (c.type === 'number' || c.type === 'money') return num(v);
    if (c.type === 'date') return dateVal(v);
    return String(v ?? '').toLowerCase();
  };

  Grid.prototype.setRows = function (records) {
    this.rows = (records || []).map((d) => ({ data: d }));
    this.page = 1;
    this.buildFilterOptions();
    this.refresh();
  };

  Grid.prototype.buildFilterOptions = function () {
    this.o.columns.forEach((c, i) => {
      if (!c.filter) return;
      const sel = this.el.querySelector(`[data-filter="${c.key}"]`);
      const found = [...new Set(this.rows.map((r) => this.cellText(r, c, i).trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b));
      // fixed options (in the page's order) are always offered, even when no row has that value yet
      const fixed = c.filterOptions || [];
      const vals = fixed.concat(found.filter((v) => !fixed.includes(v)));
      const cur = sel.value;
      sel.innerHTML = `<option value="">All ${esc(c.filterLabel || c.label.toLowerCase())}</option>` + vals.map((v) => `<option>${esc(v)}</option>`).join('');
      if (vals.includes(cur)) sel.value = cur; else this.filters[c.key] = '';
    });
  };

  Grid.prototype.setLoading = function (on) { this.q('.dg-scroll').classList.toggle('dg-busy', !!on); };
  Grid.prototype.setChips = function (chips) { this.extChips = chips || []; this.renderChips(); };

  Grid.prototype.refresh = function () {
    const cols = this.o.columns;
    const s = this.search.toLowerCase();
    const active = Object.entries(this.filters).filter(([, v]) => v);
    this.view = this.rows.filter((r) => {
      if (s && !cols.some((c, i) => c.export !== false && this.cellText(r, c, i).toLowerCase().includes(s))) return false;
      return active.every(([k, v]) => { const i = cols.findIndex((c) => c.key === k); return this.cellText(r, cols[i], i).trim() === v; });
    });
    if (this.sort) {
      const i = cols.findIndex((c) => c.key === this.sort.key);
      if (i >= 0) {
        const c = cols[i], dir = this.sort.dir === 'desc' ? -1 : 1;
        this.view.sort((a, b) => {
          const x = this.sortKey(a, c, i), y = this.sortKey(b, c, i);
          if (x === null || x === '') return (y === null || y === '') ? 0 : 1;   // empty values last
          if (y === null || y === '') return -1;
          return (x < y ? -1 : x > y ? 1 : 0) * dir;
        });
      }
    }
    this.renderHead();
    this.renderChips();
    this.render();
    // let the page follow the filtered rows (e.g. summary cards, charts)
    if (typeof this.o.onView === 'function') this.o.onView(this.view.map((r) => r.data || r.el));
  };

  Grid.prototype.renderHead = function () {
    const ths = this.table.tHead.rows[0].cells;
    this.o.columns.forEach((c, i) => {
      const th = ths[i];
      th.dataset.key = c.key;
      th.className = [c.sortable === false ? '' : 'sortable', (c.type === 'number' || c.type === 'money') ? 'num' : '', c.act ? 'act' : '',
                       this.sort && this.sort.key === c.key ? this.sort.dir : ''].filter(Boolean).join(' ');
      if (c.sortable !== false && !th.querySelector('.sort')) th.insertAdjacentHTML('beforeend', '<span class="sort"></span>');
      const mark = th.querySelector('.sort');
      if (mark) mark.innerHTML = this.sort && this.sort.key === c.key ? (this.sort.dir === 'asc' ? '&#9650;' : '&#9660;') : '&#9650;';
    });
  };

  Grid.prototype.renderChips = function () {
    const chips = [];
    if (this.search) chips.push(`<span class="dg-chip">Search: ${esc(this.search)}<button type="button" data-chip="s:" aria-label="Clear search">&times;</button></span>`);
    Object.entries(this.filters).forEach(([k, v]) => {
      if (!v) return;
      const c = this.o.columns.find((x) => x.key === k);
      chips.push(`<span class="dg-chip">${esc(c.label)}: ${esc(v)}<button type="button" data-chip="f:${esc(k)}" aria-label="Remove filter">&times;</button></span>`);
    });
    this.extChips.forEach((c, i) => chips.push(`<span class="dg-chip">${esc(c.label)}${c.remove ? `<button type="button" data-chip="x:${i}" aria-label="Remove filter">&times;</button>` : ''}</span>`));
    this.q('.dg-chips').innerHTML = chips.join('');
  };

  Grid.prototype.render = function () {
    const tbody = this.table.tBodies[0];
    const total = this.view.length;
    const pages = Math.max(1, Math.ceil(total / this.size));
    this.page = Math.min(Math.max(1, this.page), pages);
    const start = (this.page - 1) * this.size;
    const slice = this.view.slice(start, start + this.size);
    const cols = this.o.columns;

    tbody.textContent = '';
    if (!slice.length) {
      const msg = this.rows.length ? this.o.noMatchText : (this.o.emptyHtml || esc(this.o.emptyText));
      tbody.innerHTML = `<tr><td class="empty" colspan="${cols.length}">${msg}</td></tr>`;
    } else if (slice[0].el) {
      slice.forEach((r) => tbody.appendChild(r.el));
    } else {
      tbody.innerHTML = slice.map((r) => '<tr>' + cols.map((c, i) => {
        const cls = [(c.type === 'number' || c.type === 'money') ? 'num' : '', c.act ? 'act' : '', c.className || ''].filter(Boolean).join(' ');
        const html = c.render ? c.render(r.data) : esc(this.cellText(r, c, i));
        return `<td${cls ? ` class="${cls}"` : ''}>${html}</td>`;
      }).join('') + '</tr>').join('');
    }
    this.applyHidden();
    this.renderFoot();

    this.q('.dg-info').textContent = total ? `Showing ${start + 1}\u2013${Math.min(start + this.size, total)} of ${total.toLocaleString('en-US')}` : 'No records';
    const p = this.page, items = [];
    const link = (n, label, dis, on) => `<li class="page-item${dis ? ' disabled' : ''}${on ? ' active' : ''}"><a class="page-link" href="#" ${dis ? '' : `data-p="${n}"`}>${label}</a></li>`;
    items.push(link(p - 1, 'Previous', p === 1));
    let a = Math.max(1, p - 2), b = Math.min(pages, a + 4); a = Math.max(1, b - 4);
    if (a > 1) { items.push(link(1, '1')); if (a > 2) items.push('<li class="page-item disabled"><span class="page-link">\u2026</span></li>'); }
    for (let i = a; i <= b; i++) items.push(link(i, i, false, i === p));
    if (b < pages) { if (b < pages - 1) items.push('<li class="page-item disabled"><span class="page-link">\u2026</span></li>'); items.push(link(pages, pages)); }
    items.push(link(p + 1, 'Next', p === pages));
    this.q('.pagination').innerHTML = pages > 1 ? items.join('') : '';
  };

  // totals row over all filtered rows (not just the visible page)
  Grid.prototype.renderFoot = function () {
    const cols = this.o.columns;
    const tfoot = this.table.tFoot;
    if (!cols.some((c) => c.sum) || !this.view.length) { tfoot.innerHTML = ''; return; }
    const firstVisible = cols.findIndex((c) => !this.hidden.has(c.key));
    tfoot.innerHTML = '<tr>' + cols.map((c, i) => {
      let html = '';
      if (c.sum) html = fmtMoney(this.view.reduce((s, r) => s + (num(r.el ? r.vals[i] : this.cellValue(r, c, i)) || 0), 0));
      else if (i === firstVisible) html = `Total (${this.view.length.toLocaleString('en-US')})`;
      const cls = [(c.type === 'number' || c.type === 'money') ? 'num' : '', c.act ? 'act' : ''].filter(Boolean).join(' ');
      return `<td${cls ? ` class="${cls}"` : ''}>${html}</td>`;
    }).join('') + '</tr>';
    this.applyHidden();
  };

  // ---- export: filtered + sorted rows, visible columns, never the actions column ----
  Grid.prototype.exportMatrix = function () {
    const cols = this.o.columns.map((c, i) => [c, i]).filter(([c]) => c.export !== false && !c.act && !this.hidden.has(c.key));
    return [cols.map(([c]) => c.label)].concat(this.view.map((r) => cols.map(([c, i]) => this.cellText(r, c, i).trim())));
  };
  Grid.prototype.fileName = function (ext) {
    return (this.o.exportName || 'Export').replace(/[^A-Za-z0-9_\-]+/g, '_') + '_' + new Date().toISOString().slice(0, 10) + '.' + ext;
  };
  Grid.prototype.exportCsv = function () {
    const csv = this.exportMatrix().map((row) => row.map((v) => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\r\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' }));
    a.download = this.fileName('csv');
    document.body.appendChild(a); a.click(); a.remove();
  };
  Grid.prototype.exportXlsx = function () {
    const ws = XLSX.utils.aoa_to_sheet(this.exportMatrix());
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, (this.o.exportName || 'Sheet').slice(0, 31));
    XLSX.writeFile(wb, this.fileName('xlsx'));
  };
  Grid.prototype.print = function () {
    const m = this.exportMatrix();
    const w = window.open('', '_blank');
    if (!w) return;
    w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${esc(this.o.exportName)}</title>
      <style>body{font:12px Arial,sans-serif;margin:16px}h2{font-size:16px;margin:0 0 8px}table{border-collapse:collapse;width:100%}
      th,td{border:1px solid #999;padding:4px 6px;text-align:left}th{background:#eee}</style></head><body>
      <h2>${esc(this.o.exportName)} <small>(${m.length - 1} rows, ${new Date().toLocaleString()})</small></h2>
      <table><thead><tr>${m[0].map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead>
      <tbody>${m.slice(1).map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></body></html>`);
    w.document.close(); w.focus(); w.print();
  };

  // ---- constructors ----
  function create(mount, opts) {
    const g = new Grid(opts);
    if (!g.table.tHead.rows.length) {
      g.table.tHead.innerHTML = '<tr>' + opts.columns.map((c) => `<th>${esc(c.label)}</th>`).join('') + '</tr>';
    }
    mount.appendChild(g.el);
    g.refresh();
    return g;
  }

  function fromTable(table, opts = {}) {
    const ths = [...table.tHead.rows[0].cells];
    const columns = ths.map((th, i) => {
      const label = th.textContent.trim();
      const isAct = th.classList.contains('act');
      return {
        key: th.dataset.key || 'c' + i, label: label || (isAct ? 'Actions' : 'Column ' + (i + 1)),
        type: th.dataset.type || 'text', sum: th.hasAttribute('data-sum'), act: isAct,
        sortable: !(isAct || th.dataset.sort === 'false'), export: !(isAct || th.dataset.export === 'false'),
        hideable: !(isAct || th.dataset.hide === 'false'), hidden: th.hasAttribute('data-hidden'), filter: th.hasAttribute('data-filter'),
        filterLabel: th.dataset.filterLabel,
        filterOptions: th.dataset.filterOptions ? th.dataset.filterOptions.split('|').map((v) => v.trim()).filter(Boolean) : null,
      };
    });
    const rows = [...table.tBodies[0].rows].filter((tr) => tr.cells.length === columns.length).map((tr) => {
      const cells = [...tr.cells];
      cells.forEach((td, i) => {
        if (columns[i].type === 'number' || columns[i].type === 'money') td.classList.add('num');
        if (columns[i].act) td.classList.add('act');
      });
      return {
        el: tr,
        texts: cells.map((td) => td.textContent.replace(/\s+/g, ' ').trim()),
        orders: cells.map((td) => td.dataset.order),
        vals: cells.map((td) => td.dataset.order !== undefined ? td.dataset.order : td.textContent.replace(/\s+/g, ' ').trim()),
      };
    });
    const mount = document.createElement('div');
    table.parentNode.insertBefore(mount, table);
    const g = new Grid(Object.assign({}, opts, { columns, table }));
    mount.replaceWith(g.el);
    g.rows = rows;
    g.buildFilterOptions();
    g.refresh();
    return g;
  }

  /* Declarative set-up: <table id="x" data-grid="storage-key" data-grid-title="\u2026" data-grid-subtitle="\u2026"
   *   data-grid-export="File_Name" data-grid-search="placeholder" data-grid-empty="\u2026" data-grid-sort="0:asc">
   * Any element with data-grid-action="x" (e.g. an "Add" button) is moved into the grid's header. */
  function auto(root) {
    (root || document).querySelectorAll('table[data-grid]').forEach((t) => {
      if (t.dataset.gridReady) return;
      t.dataset.gridReady = '1';
      const d = t.dataset;
      const actions = t.id ? [...document.querySelectorAll(`[data-grid-action="${t.id}"]`)] : [];
      const [sortCol, sortDir] = (d.gridSort || '').split(':');
      fromTable(t, {
        storageKey: d.grid, title: d.gridTitle, subtitle: d.gridSubtitle,
        exportName: d.gridExport || d.gridTitle || 'Export',
        searchPlaceholder: d.gridSearch || 'Search\u2026', emptyText: d.gridEmpty || 'No records yet',
        headActions: actions.length ? actions : undefined,
        sort: sortCol !== '' && sortCol !== undefined ? { key: 'c' + sortCol, dir: sortDir || 'asc' } : null,
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => auto());
  else auto();

  window.KFTGrid = { create, fromTable, auto, escape: esc };
})();
