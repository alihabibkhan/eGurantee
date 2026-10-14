// KFT Management / Regional dashboard.
// Data comes from /dashboard/kft-data (latest tbl_post_disbursement snapshot); all filtering happens client-side.
(function () {
  const ENT = 0, EDU = 1;
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  // Chart colours come from the theme tokens (--c1 green, --c2 gold, --c3 sage, --c4 orange, --c5 red)
  const C = (n) => themeVar('--c' + n, ['', '#1F6E4B', '#B8862B', '#9DB5A7', '#D9793A', '#B3392F'][n]);
  // loan tuple indexes
  const L_BRANCH = 0, L_CAT = 1, L_BEN = 2, L_YM = 3, L_DISB = 4, L_OS = 5, L_OD = 6;

  let D = null;
  let charts = {};
  let loading = false;
  let RY, RM, RYM;

  const $ = (id) => document.getElementById(id);
  const fmtNum = (n) => (n === null || n === undefined) ? '—' : Math.round(n).toLocaleString('en-US');
  const fmtPKR = (n) => {
    if (n === null || n === undefined) return '—';
    const a = Math.abs(n);
    if (a >= 1e9) return 'PKR ' + (n / 1e9).toFixed(2) + 'B';
    if (a >= 1e6) return 'PKR ' + (n / 1e6).toFixed(1) + 'M';
    return 'PKR ' + fmtNum(n);
  };
  // KPI value: small "PKR" prefix as in the approved design
  const pkrHtml = (n) => {
    const t = fmtPKR(n);
    return t.startsWith('PKR ') ? '<small>PKR</small>' + t.slice(4) : t;
  };
  const pct = (part, whole, digits = 1) => whole ? (part / whole * 100).toFixed(digits) + '%' : '—';
  const esc = (s) => String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  // ---------- loading ----------
  function load(refresh) {
    if (loading) return;
    loading = true;
    $('kfd-loading').style.display = 'block';
    $('kfd-content').style.display = 'none';
    $('kfd-error').style.display = 'none';
    fetch('/dashboard/kft-data' + (refresh ? '?refresh=1' : ''), { credentials: 'same-origin' })
      .then((r) => r.json())
      .then((res) => {
        if (!res.success) throw new Error(res.error || 'Unable to load dashboard data');
        D = res.data;
        RY = D.meta.reportYear; RM = D.meta.reportMonth; RYM = RY * 100 + RM;
        setupFilters();
        $('kfd-loading').style.display = 'none';
        $('kfd-content').style.display = 'block';
        applyFilters();
      })
      .catch((e) => {
        $('kfd-loading').style.display = 'none';
        $('kfd-error').style.display = 'block';
        $('kfd-error').textContent = 'Could not load dashboard data: ' + e.message;
      })
      .finally(() => { loading = false; });
  }

  function setupFilters() {
    const regionSel = $('kfd-region');
    regionSel.innerHTML = '<option value="">All regions</option>' +
      D.regions.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join('');

    const yearSel = $('kfd-year');
    yearSel.innerHTML = trendYears().slice().reverse()
      .map((y) => `<option value="${y}">${y}${y === RY && RM < 12 ? ' (YTD)' : ''}</option>`).join('');

    populateBranches();

    const periodLabel = MONTHS_LONG[RM - 1] + ' ' + RY;
    $('kfd-period').textContent = 'Reporting Period: ' + periodLabel;
    $('kfd-refresh').textContent = 'MIS data as of ' + formatIsoDate(D.meta.misDate) + ' · ' +
      fmtNum(D.loans.length) + ' loans since inception';
  }

  function populateBranches() {
    const region = $('kfd-region').value;
    const branchSel = $('kfd-branch');
    const current = branchSel.value;
    const withLoans = new Set(D.loans.map((l) => l[L_BRANCH]));
    const list = D.branches
      .map((b, i) => ({ ...b, idx: i }))
      .filter((b) => withLoans.has(b.idx) && (!region || b.region === region))
      .sort((a, b) => a.name.localeCompare(b.name));

    let html = '<option value="">All branches</option>';
    if (region) {
      html += list.map((b) => `<option value="${b.idx}">${esc(b.name)}</option>`).join('');
    } else {
      D.regions.forEach((r) => {
        const items = list.filter((b) => b.region === r);
        if (!items.length) return;
        html += `<optgroup label="${esc(r)}">` +
          items.map((b) => `<option value="${b.idx}">${esc(b.name)}</option>`).join('') + '</optgroup>';
      });
    }
    branchSel.innerHTML = html;
    if ([...branchSel.options].some((o) => o.value === current)) branchSel.value = current;
  }

  function formatIsoDate(iso) {
    const [y, m, d] = iso.split('-').map(Number);
    return String(d).padStart(2, '0') + '-' + MONTHS[m - 1] + '-' + y;
  }

  function trendYears() {
    return [RY - 2, RY - 1, RY];
  }

  // ---------- filtering ----------
  function getFilters() {
    const branchVal = $('kfd-branch').value;
    return {
      region: $('kfd-region').value,
      branch: branchVal === '' ? null : Number(branchVal),
      product: $('kfd-product').value,
      focusYear: Number($('kfd-year').value),
    };
  }

  function inLocation(branchIdx, f) {
    if (f.branch !== null) return branchIdx === f.branch;
    if (f.region) return D.branches[branchIdx].region === f.region;
    return true;
  }

  function inProduct(cat, f) {
    if (f.product === 'enterprise') return cat === ENT;
    if (f.product === 'education') return cat === EDU;
    return true;
  }

  // loans in the selected region (all its branches) — used for group comparisons
  function regionLoans(f, withProduct = true) {
    return D.loans.filter((l) => (!f.region || D.branches[l[L_BRANCH]].region === f.region) &&
      (!withProduct || inProduct(l[L_CAT], f)));
  }

  function summarize(loans) {
    const s = {
      loans: 0, disb: 0, bens: new Set(),
      ytdLoans: 0, ytdDisb: 0, ytdBens: new Set(),
      curLoans: 0, curDisb: 0, curBens: new Set(),
      os: 0, active: 0,
      b30: 0, b60: 0, b180: 0, arrearsCases: 0, arrearsAmt: 0, writeOffCases: 0,
    };
    loans.forEach((l) => {
      const ym = l[L_YM], disb = l[L_DISB], os = l[L_OS], od = l[L_OD];
      s.loans++; s.disb += disb; s.bens.add(l[L_BEN]);
      if (Math.floor(ym / 100) === RY && ym <= RYM) { s.ytdLoans++; s.ytdDisb += disb; s.ytdBens.add(l[L_BEN]); }
      if (ym === RYM) { s.curLoans++; s.curDisb += disb; s.curBens.add(l[L_BEN]); }
      if (os > 0) { s.os += os; s.active++; }
      if (od >= 30) {
        s.arrearsCases++; s.arrearsAmt += os;
        if (od < 60) s.b30 += os; else if (od < 180) s.b60 += os; else { s.b180 += os; s.writeOffCases++; }
      }
    });
    return s;
  }

  // group = region when no region is selected, otherwise branch within the region
  function groupKey(f) {
    return f.region ? (l) => l[L_BRANCH] : (l) => D.branches[l[L_BRANCH]].region;
  }

  function groupLabel(f, key) {
    return f.region ? D.branches[key].name : key;
  }

  function isHighlighted(f, key) {
    return f.region ? key === f.branch : false;
  }

  function groupBy(loans, keyFn) {
    const m = new Map();
    loans.forEach((l) => {
      const k = keyFn(l);
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(l);
    });
    return m;
  }

  // ---------- render ----------
  function applyFilters() {
    if (!D) return;
    const f = getFilters();
    const scope = D.loans.filter((l) => inLocation(l[L_BRANCH], f) && inProduct(l[L_CAT], f));
    const scopeAllProducts = D.loans.filter((l) => inLocation(l[L_BRANCH], f));
    const s = summarize(scope);
    const dim = f.region ? 'Branch' : 'Region';

    const where = f.branch !== null ? D.branches[f.branch].name : (f.region || 'all regions');
    const what = f.product ? f.product[0].toUpperCase() + f.product.slice(1) : 'all products';
    const title = f.region ? 'KFT Regional Dashboard · ' + f.region : 'KFT Management Dashboard';
    $('kfd-title').textContent = title;
    $('kfd-print-title').textContent = 'KFT - Khushali Foundation Trust - ' + (f.region ? 'Regional Dashboard · ' + f.region : 'Management Dashboard');
    $('kfd-kpi-heading').textContent = 'Key performance indicators — ' + where + ' / ' + what;

    renderKpis(s, scopeAllProducts);
    renderDistribution(f);
    document.querySelectorAll('.kfd-dim').forEach((el) => { el.textContent = dim; });
    $('kfd-rank-title').textContent = (f.region ? 'Branch' : 'Regional') + ' performance & ranking';
    document.querySelectorAll('.kfd-ry').forEach((el) => { el.textContent = RY; });

    renderTrendChart(scope, f);
    renderMixChart(scopeAllProducts);
    renderGroupBars(f);
    renderRankingTable(f);
    renderYoY(scope);
    renderPortfolioQuality(s, scope, f);
  }

  // value is built from numbers only (fmtNum / pkrHtml), so it is safe as HTML
  function setKpi(id, value, sub) {
    $(id).innerHTML = value;
    if (sub !== undefined) $(id + '-sub').textContent = sub;
  }

  function renderKpis(s, scopeAllProducts) {
    const ytdRange = 'Jan – ' + MONTHS[RM - 1] + ' ' + RY;
    const curLabel = MONTHS_LONG[RM - 1] + ' ' + RY;

    setKpi('kfd-k-bens', fmtNum(s.bens.size), 'Unique CNICs since inception');
    setKpi('kfd-k-loans', fmtNum(s.loans), 'Cumulative loan count');
    setKpi('kfd-k-disb', pkrHtml(s.disb), 'Since inception');
    setKpi('kfd-k-os', pkrHtml(s.os), fmtNum(s.active) + ' active loans');
    setKpi('kfd-k-npl', pkrHtml(s.arrearsAmt));
    $('kfd-k-npl-sub').innerHTML = '<span class="down">' + pct(s.arrearsAmt, s.os, 2) + '</span> of outstanding · ' + fmtNum(s.arrearsCases) + ' loans (30+ days)';
    setKpi('kfd-k-avg', pkrHtml(s.loans ? s.disb / s.loans : 0), 'Per loan');
    setKpi('kfd-k-ytd-disb', pkrHtml(s.ytdDisb), ytdRange + ' · ' + fmtNum(s.ytdLoans) + ' loans');
    setKpi('kfd-k-ytd-bens', fmtNum(s.ytdBens.size), ytdRange);
    setKpi('kfd-k-cur-disb', pkrHtml(s.curDisb), curLabel + ' · ' + fmtNum(s.curLoans) + ' loans');
    setKpi('kfd-k-cur-bens', fmtNum(s.curBens.size), curLabel);

    let ent = 0, edu = 0, total = 0;
    scopeAllProducts.forEach((l) => {
      total += l[L_DISB];
      if (l[L_CAT] === ENT) ent += l[L_DISB]; else if (l[L_CAT] === EDU) edu += l[L_DISB];
    });
    setKpi('kfd-k-ent', pkrHtml(ent), pct(ent, total) + ' of total disbursement (SI)');
    setKpi('kfd-k-edu', pkrHtml(edu), pct(edu, total) + ' of total disbursement (SI)');
  }

  function renderDistribution(f) {
    $('kfd-dist-title').textContent = f.region
      ? f.region + ' — Branch / Local Council Distribution'
      : 'National Council Distribution';
    const groups = groupBy(regionLoans(f), groupKey(f));
    const rows = [...groups.entries()]
      .map(([k, ls]) => {
        const s = summarize(ls);
        return { key: k, label: groupLabel(f, k), bens: s.bens.size, loans: s.loans, active: s.active };
      })
      .sort((a, b) => a.label.localeCompare(b.label));

    // share = % of loans disbursed since inception; the bar is scaled to the largest council
    const totalLoans = rows.reduce((a, r) => a + r.loans, 0);
    const maxLoans = Math.max(1, ...rows.map((r) => r.loans));
    $('kfd-dist-grid').innerHTML = rows.map((r) => `
      <button type="button" class="rc${isHighlighted(f, r.key) ? ' selected' : ''}" data-key="${esc(r.key)}">
        <div class="rc-top"><span class="rc-name">${esc(r.label)}</span><span class="rc-share">${pct(r.loans, totalLoans)}</span></div>
        <div class="rc-main"><b>${fmtNum(r.bens)}</b><span>beneficiaries</span></div>
        <div class="rc-bar"><i style="width:${Math.max(r.loans / maxLoans * 100, 2)}%"></i></div>
        <div class="rc-stats">
          <div><b>${fmtNum(r.loans)}</b><span>Loans disbursed</span></div>
          <div><b>${fmtNum(r.active)}</b><span>Active loans</span></div>
        </div>
      </button>`).join('') || '<div class="kfd-empty">No data for the selected filters</div>';

    $('kfd-dist-grid').querySelectorAll('.rc').forEach((el) => {
      el.onclick = () => drillInto(f, el.dataset.key);
    });
  }

  function drillInto(f, key) {
    if (f.region) {
      $('kfd-branch').value = String(key);
    } else {
      $('kfd-region').value = key;
      populateBranches();
      $('kfd-branch').value = '';
    }
    applyFilters();
  }

  function destroyChart(key) {
    if (charts[key]) { charts[key].destroy(); delete charts[key]; }
  }

  // Axis text, gridlines and slice borders follow the app's light / dark theme (kft-theme.css tokens)
  function themeVar(name, fallback) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
  }
  function applyChartTheme() {
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
    Chart.defaults.font.size = 11.5;
    Chart.defaults.color = themeVar('--ink-3', '#64756B');
    Chart.defaults.borderColor = themeVar('--grid', 'rgba(0,0,0,0.1)');
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Object.assign(Chart.defaults.plugins.tooltip, {
      backgroundColor: themeVar('--ink', '#17211C'), titleColor: themeVar('--bg', '#fff'), bodyColor: themeVar('--bg', '#fff'),
      padding: 10, cornerRadius: 6,
    });
  }
  const sliceBorder = () => themeVar('--surface', '#fff');

  function makeChart(key, canvasId, config) {
    destroyChart(key);
    applyChartTheme();
    try {
      charts[key] = new Chart($(canvasId).getContext('2d'), config);
    } catch (e) {
      console.warn('Chart render skipped:', key, e.message);
    }
  }

  const pkrTooltip = { callbacks: { label: (c) => (c.dataset.label ? c.dataset.label + ': ' : '') + fmtPKR(c.raw) } };
  const pkrAxis = { border: { display: false }, ticks: { callback: (v) => fmtPKR(v) } };
  const catAxis = { grid: { display: false } };

  function renderTrendChart(scope, f) {
    const years = trendYears();
    const series = {};
    years.forEach((y) => { series[y] = new Array(12).fill(0); });
    scope.forEach((l) => {
      const y = Math.floor(l[L_YM] / 100);
      if (series[y]) series[y][(l[L_YM] % 100) - 1] += l[L_DISB];
    });
    // months after the reporting month in the reporting year have no data yet
    for (let m = RM; m < 12; m++) series[RY][m] = null;

    $('kfd-trend-title').textContent = '· ' +
      years.map((y) => y === RY && RM < 12 ? y + ' YTD' : y).join(' vs ');

    const trendColors = [C(3), C(2), C(1)];
    makeChart('trend', 'kfd-ch-trend', {
      type: 'line',
      data: {
        labels: MONTHS,
        datasets: years.map((y, i) => ({
          label: y === RY && RM < 12 ? y + ' YTD' : String(y),
          data: series[y],
          borderColor: trendColors[i],
          backgroundColor: trendColors[i],
          borderWidth: y === f.focusYear ? 3 : 1.75,
          tension: 0.35, pointRadius: y === f.focusYear ? 3 : 2, spanGaps: false,
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { tooltip: pkrTooltip },
        scales: { x: catAxis, y: pkrAxis },
      },
    });
  }

  function renderMixChart(scopeAllProducts) {
    let ent = 0, edu = 0;
    scopeAllProducts.forEach((l) => {
      if (l[L_CAT] === ENT) ent += l[L_DISB]; else if (l[L_CAT] === EDU) edu += l[L_DISB];
    });
    const total = ent + edu;
    makeChart('mix', 'kfd-ch-mix', {
      type: 'doughnut',
      data: {
        labels: ['Enterprise', 'Education'],
        datasets: [{ data: [ent, edu], backgroundColor: [C(1), C(2)], borderWidth: 3, borderColor: sliceBorder() }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '62%',
        plugins: {
          legend: { position: 'bottom' },
          tooltip: { callbacks: { label: (c) => c.label + ': ' + fmtPKR(c.raw) + ' (' + pct(c.raw, total) + ')' } },
        },
      },
    });
  }

  function groupRows(f) {
    const groups = groupBy(regionLoans(f), groupKey(f));
    return [...groups.entries()].map(([k, ls]) => ({ key: k, label: groupLabel(f, k), s: summarize(ls) }));
  }

  function horizontalBar(key, canvasId, rows, valueFn, color, highlightColor, f, label) {
    const sorted = rows.slice().sort((a, b) => valueFn(b) - valueFn(a));
    const canvas = $(canvasId);
    canvas.parentElement.style.height = Math.max(270, sorted.length * 26 + 60) + 'px';
    makeChart(key, canvasId, {
      type: 'bar',
      data: {
        labels: sorted.map((r) => r.label),
        datasets: [{
          label, data: sorted.map(valueFn),
          backgroundColor: sorted.map((r) => isHighlighted(f, r.key) ? highlightColor : color),
          borderRadius: 4, maxBarThickness: 16,
        }],
      },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => fmtPKR(c.raw) } } },
        scales: { x: pkrAxis, y: catAxis },
        onClick: (evt, els) => { if (els.length) drillInto(f, sorted[els[0].index].key); },
      },
    });
  }

  function renderGroupBars(f) {
    const rows = groupRows(f);
    horizontalBar('groupSI', 'kfd-ch-group-si', rows, (r) => r.s.disb, C(1), C(2), f, 'Disbursed SI (PKR)');
    horizontalBar('groupYTD', 'kfd-ch-group-ytd', rows, (r) => r.s.ytdDisb, C(2), C(1), f, 'YTD Disbursed (PKR)');
  }

  function renderRankingTable(f) {
    const rows = groupRows(f).sort((a, b) => b.s.disb - a.s.disb);
    const total = rows.reduce((a, r) => a + r.s.disb, 0);
    const maxDisb = rows.length ? rows[0].s.disb : 0;
    const tbody = $('kfd-rank-body');
    tbody.innerHTML = rows.map((r, i) => {
      const rank = i + 1;
      return `<tr class="${isHighlighted(f, r.key) ? 'selected-row' : ''}" data-i="${i}">
        <td><span class="rank${rank <= 3 ? ' r' + rank : ''}">${rank}</span></td>
        <td class="strong">${esc(r.label)}</td>
        <td class="num">${fmtNum(r.s.bens.size)}</td>
        <td class="num">${fmtNum(r.s.loans)}</td>
        <td class="num">${fmtNum(r.s.disb)}</td>
        <td><div class="share"><div class="bar"><i style="width:${maxDisb ? r.s.disb / maxDisb * 100 : 0}%"></i></div><span>${pct(r.s.disb, total)}</span></div></td>
        <td class="num">${fmtNum(r.s.ytdBens.size)}</td>
        <td class="num">${fmtNum(r.s.ytdLoans)}</td>
        <td class="num">${fmtNum(r.s.ytdDisb)}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="9" class="kfd-empty">No data for the selected filters</td></tr>';
    tbody.querySelectorAll('tr[data-i]').forEach((tr) => {
      tr.onclick = () => drillInto(f, rows[Number(tr.dataset.i)].key);
    });
  }

  function periodTotals(scope, year, lastMonth) {
    let loans = 0, disb = 0;
    const bens = new Set();
    scope.forEach((l) => {
      const ym = l[L_YM];
      if (Math.floor(ym / 100) === year && ym % 100 <= lastMonth) { loans++; disb += l[L_DISB]; bens.add(l[L_BEN]); }
    });
    return { loans, disb, bens: bens.size };
  }

  function renderYoY(scope) {
    // Last completed year pair on a full-year basis, and the ongoing year compared on the same YTD months.
    const pairs = [[RY - 2, RY - 1, 12], [RY - 1, RY, RM]];
    const growth = (a, b) => a ? (b - a) / a * 100 : null;
    const cards = [];
    pairs.forEach(([y1, y2, m]) => {
      const a = periodTotals(scope, y1, m), b = periodTotals(scope, y2, m);
      const basis = `${y1} → ${y2} · ` + (m === 12 ? 'full year' : 'Jan–' + MONTHS[m - 1] + ', comparable');
      cards.push(['Disbursement growth', basis, growth(a.disb, b.disb)]);
      cards.push(['Loan count growth', basis, growth(a.loans, b.loans)]);
      cards.push(['Beneficiaries growth', basis, growth(a.bens, b.bens)]);
    });
    $('kfd-yoy').innerHTML = cards.map(([lbl, basis, g]) => `
      <div class="kc yoy">
        <div class="l">${lbl}<small>${basis}</small></div>
        <div class="v ${g === null ? 'na' : g >= 0 ? '' : 'neg'}">${g === null ? '—' : (g >= 0 ? '+' : '') + g.toFixed(1) + '%'}</div>
      </div>`).join('');
  }

  function renderPortfolioQuality(s, scope, f) {
    $('kfd-pq-title').textContent = 'Portfolio quality — arrears & write-offs (' + MONTHS_LONG[RM - 1] + ' ' + RY + ')';
    setKpi('kfd-pq-os', pkrHtml(s.os), 'Total principal outstanding');
    setKpi('kfd-pq-30', pkrHtml(s.b30), pct(s.b30, s.os, 2) + ' of outstanding');
    setKpi('kfd-pq-60', pkrHtml(s.b60), pct(s.b60, s.os, 2) + ' of outstanding');
    setKpi('kfd-pq-180', pkrHtml(s.b180), pct(s.b180, s.os, 2) + ' of outstanding');
    setKpi('kfd-pq-cases', fmtNum(s.arrearsCases), fmtPKR(s.arrearsAmt) + ' outstanding (30+ days)');
    setKpi('kfd-pq-wo', fmtNum(s.writeOffCases), fmtPKR(s.b180) + ' outstanding (180+ days)');

    makeChart('aging', 'kfd-ch-aging', {
      type: 'bar',
      data: {
        labels: ['30–59 days', '60–179 days', '180+ days'],
        datasets: [{ label: 'Outstanding Principal (PKR)', data: [s.b30, s.b60, s.b180], backgroundColor: [C(2), C(4), C(5)], borderRadius: 6, maxBarThickness: 56 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => fmtPKR(c.raw) } } },
        scales: { x: catAxis, y: pkrAxis },
      },
    });

    const months = D.arrearsTrend.months;
    const totals = new Array(months.length).fill(0);
    D.arrearsTrend.rows.forEach(([mi, b, cat, amt]) => {
      if (inLocation(b, f) && inProduct(cat, f)) totals[mi] += amt;
    });
    makeChart('arrearsTrend', 'kfd-ch-arrears-trend', {
      type: 'line',
      data: {
        labels: months.map((m) => { const [y, mo] = m.split('-'); return MONTHS[Number(mo) - 1] + ' ' + y.slice(2); }),
        datasets: [{ label: 'Arrears Outstanding (PKR)', data: totals, borderColor: C(5), backgroundColor: C(5) + '1F', fill: true, tension: 0.3, pointRadius: 3 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => fmtPKR(c.raw) } } },
        scales: { x: catAxis, y: pkrAxis },
      },
    });

    horizontalBar('arrearsGroup', 'kfd-ch-arrears-group', groupRows(f), (r) => r.s.arrearsAmt, C(5), C(2), f, 'Current Arrears (PKR)');

    let ent = 0, edu = 0, entN = 0, eduN = 0;
    scope.forEach((l) => {
      if (l[L_OD] < 30) return;
      if (l[L_CAT] === ENT) { ent += l[L_OS]; entN++; } else if (l[L_CAT] === EDU) { edu += l[L_OS]; eduN++; }
    });
    makeChart('arrearsSector', 'kfd-ch-arrears-sector', {
      type: 'doughnut',
      data: { labels: ['Enterprise', 'Education'], datasets: [{ data: [ent, edu], backgroundColor: [C(1), C(2)], borderWidth: 3, borderColor: sliceBorder() }] },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '62%',
        plugins: {
          legend: { position: 'bottom' },
          tooltip: { callbacks: { label: (c) => c.label + ': ' + fmtPKR(c.raw) + ' (' + [entN, eduN][c.dataIndex] + ' cases)' } },
        },
      },
    });

    renderArrearsListing(f);
  }

  function listingRows(f) {
    return D.arrearsListing.filter((r) => inLocation(r.b, f) && inProduct(r.c, f));
  }

  const LISTING_COLUMNS = [
    ['sector_code', 'Sector Code'], ['branch_name', 'Branch Name'], ['gender', 'Gender'], ['mobile_no', 'Mobile Number'],
    ['loan_title', 'Loan Title'], ['loan_no', 'Loan Number'], ['product_code', 'Product Code'], ['booked_on', 'Loan Creation Date'],
    ['disbursed_amount', 'Disb. Amount'], ['loan_status', 'Loan Status'], ['overdue_days', 'OD Days'],
    ['principal_outstanding', 'OS_P'], ['sector', 'Sector'],
  ];
  const sectorName = (c) => c === ENT ? 'Enterprise' : c === EDU ? 'Education' : 'Other';

  function renderArrearsListing(f) {
    // Arrear listing is part of the Regional report — shown once a region is selected
    $('kfd-listing-section').style.display = f.region ? 'block' : 'none';
    if (!f.region) return;
    const rows = listingRows(f);
    $('kfd-listing-count').textContent = '· ' + fmtNum(rows.length) + ' loans, 30+ days';
    $('kfd-listing-body').innerHTML = rows.map((r) => `<tr>
        <td>${esc(r.sector_code)}</td><td>${esc(r.branch_name)}</td><td>${esc(r.gender)}</td><td>${esc(r.mobile_no)}</td>
        <td>${esc(r.loan_title)}</td><td>${esc(r.loan_no)}</td><td>${esc(r.product_code)}</td><td>${esc(r.booked_on)}</td>
        <td class="num">${fmtNum(r.disbursed_amount)}</td><td>${esc(r.loan_status)}</td><td class="num">${fmtNum(r.overdue_days)}</td>
        <td class="num">${fmtNum(r.principal_outstanding)}</td>
        <td><span class="sector-tag ${r.c === EDU ? 'edu' : 'ent'}">${sectorName(r.c)}</span></td>
      </tr>`).join('') || `<tr><td colspan="${LISTING_COLUMNS.length}" class="kfd-empty">No loans in arrears for the selected filters</td></tr>`;
  }

  function downloadListingCsv() {
    const f = getFilters();
    const rows = listingRows(f);
    const csvCell = (v) => '"' + String(v === null || v === undefined ? '' : v).replace(/"/g, '""') + '"';
    const lines = [LISTING_COLUMNS.map((c) => csvCell(c[1])).join(',')].concat(
      rows.map((r) => LISTING_COLUMNS.map(([k]) => csvCell(k === 'sector' ? sectorName(r.c) : r[k])).join(','))
    );
    const blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'Arrears_Listing_' + (f.region || 'All').replace(/\s+/g, '_') + '_' + D.meta.misDate + '.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  function resetFilters() {
    $('kfd-region').value = '';
    $('kfd-product').value = '';
    $('kfd-year').value = String(RY);
    populateBranches();
    $('kfd-branch').value = '';
    applyFilters();
  }

  function resizeCharts() {
    Object.values(charts).forEach((c) => c.resize());
  }

  // ---------- view toggle ----------
  const VIEW_KEY = 'egs_dashboard_view';

  function setView(view) {
    const isNew = view !== 'classic';
    $('kft-dashboard').style.display = isNew ? 'block' : 'none';
    $('classic-dashboard').style.display = isNew ? 'none' : 'block';
    document.querySelectorAll('[data-dashboard-view]').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.dashboardView === (isNew ? 'new' : 'classic'));
    });
    try { localStorage.setItem(VIEW_KEY, isNew ? 'new' : 'classic'); } catch (e) { /* storage unavailable */ }
    if (isNew) {
      if (!D) load(false); else resizeCharts();
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    $('kfd-region').addEventListener('change', () => { populateBranches(); $('kfd-branch').value = ''; applyFilters(); });
    $('kfd-branch').addEventListener('change', () => {
      const v = $('kfd-branch').value;
      if (v !== '' && !$('kfd-region').value) {
        $('kfd-region').value = D.branches[Number(v)].region;
        populateBranches();
        $('kfd-branch').value = v;
      }
      applyFilters();
    });
    $('kfd-product').addEventListener('change', applyFilters);
    $('kfd-year').addEventListener('change', applyFilters);
    $('kfd-reset').addEventListener('click', resetFilters);
    $('kfd-print').addEventListener('click', () => window.print());
    $('kfd-reload').addEventListener('click', () => load(true));
    $('kfd-listing-csv').addEventListener('click', downloadListingCsv);
    document.querySelectorAll('[data-dashboard-view]').forEach((btn) => {
      btn.addEventListener('click', () => setView(btn.dataset.dashboardView));
    });

    // Task 004: the New / Classic switch is hidden, so always open the new dashboard
    // (a saved 'classic' choice would otherwise leave users stuck on the classic view)
    setView('new');
  });

  window.addEventListener('beforeprint', resizeCharts);
  // Redraw the charts in the new colours when the user switches light / dark mode (event fired by navbar.html)
  window.addEventListener('kft-theme-change', () => applyFilters());
})();
