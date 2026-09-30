// Filters for the emailed KFT report (templates/kft_report.html).
// This file is inlined into the report, reads the data embedded next to it and redraws the sections as
// inline SVG/HTML — no libraries and no network access. Calculations mirror kft_dashboard.js and the charts
// mirror the SVG helpers in Model_KFT_Report.py.
(function () {
  const dataEl = document.getElementById('rpt-data');
  if (!dataEl) return;
  const D = JSON.parse(dataEl.textContent);
  const ENT = 0, EDU = 1;
  const L_BRANCH = 0, L_CAT = 1, L_BEN = 2, L_YM = 3, L_DISB = 4, L_OS = 5, L_OD = 6;
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const C = { green: '#1F5C3F', dark: '#143D2A', accent: '#2E8B57', gold: '#C99A2E', orange: '#E08E45', red: '#B4453A', muted: '#64756B', grid: '#E4EAE6', text: '#1B2420' };
  const TREND_COLORS = ['#9BB0A5', '#2E8B57', '#143D2A'];
  const RY = D.meta.reportYear, RM = D.meta.reportMonth, RYM = RY * 100 + RM;
  const REGIONAL = D.mode === 'regional';
  const $ = (id) => document.getElementById(id);

  // ---------- formatting ----------
  const fmtNum = (n) => (n === null || n === undefined) ? '—' : Math.round(n).toLocaleString('en-US');
  const fmtPKR = (n) => {
    if (n === null || n === undefined) return '—';
    const a = Math.abs(n);
    if (a >= 1e9) return 'PKR ' + (n / 1e9).toFixed(2) + 'B';
    if (a >= 1e6) return 'PKR ' + (n / 1e6).toFixed(1) + 'M';
    return 'PKR ' + fmtNum(n);
  };
  const pct = (part, whole, digits = 1) => whole ? (part / whole * 100).toFixed(digits) + '%' : '—';
  const esc = (s) => String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  // ---------- filters ----------
  function setupFilters() {
    const bar = $('rpt-filters');
    let html = '<span class="lbl">FILTERS:</span>';
    if (!REGIONAL) {
      html += '<label>Region<select id="f-region"><option value="">All Regions</option>' +
        D.regions.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join('') + '</select></label>';
    }
    html += '<label>Branch<select id="f-branch"></select></label>';
    if (!REGIONAL) {
      html += '<label>Product<select id="f-product"><option value="">All Products</option>' +
        '<option value="enterprise">Enterprise</option><option value="education">Education</option></select></label>';
      html += '<label>Trend Focus Year<select id="f-year">' + [RY, RY - 1, RY - 2]
        .map((y) => `<option value="${y}">${y}${y === RY && RM < 12 ? ' (YTD)' : ''}</option>`).join('') + '</select></label>';
    }
    html += '<button type="button" id="f-reset">Reset Filters</button>';
    bar.innerHTML = html;
    populateBranches();

    if (!REGIONAL) {
      $('f-region').addEventListener('change', () => { populateBranches(); $('f-branch').value = ''; render(); });
      $('f-product').addEventListener('change', render);
      $('f-year').addEventListener('change', render);
    }
    $('f-branch').addEventListener('change', () => {
      const v = $('f-branch').value;
      if (!REGIONAL && v !== '' && !$('f-region').value) {
        $('f-region').value = D.branches[Number(v)].region;
        populateBranches();
        $('f-branch').value = v;
      }
      render();
    });
    $('f-reset').addEventListener('click', () => {
      if (!REGIONAL) { $('f-region').value = ''; $('f-product').value = ''; $('f-year').value = String(RY); }
      populateBranches();
      $('f-branch').value = '';
      render();
    });
  }

  function populateBranches() {
    const region = REGIONAL ? D.region : $('f-region').value;
    const withLoans = new Set(D.loans.map((l) => l[L_BRANCH]));
    const list = D.branches.map((b, i) => ({ name: b.name, region: b.region, idx: i }))
      .filter((b) => withLoans.has(b.idx) && (!region || b.region === region))
      .sort((a, b) => a.name.localeCompare(b.name));
    let html = '<option value="">All Branches</option>';
    if (region) {
      html += list.map((b) => `<option value="${b.idx}">${esc(b.name)}</option>`).join('');
    } else {
      D.regions.forEach((r) => {
        const items = list.filter((b) => b.region === r);
        if (items.length) {
          html += `<optgroup label="${esc(r)}">` + items.map((b) => `<option value="${b.idx}">${esc(b.name)}</option>`).join('') + '</optgroup>';
        }
      });
    }
    $('f-branch').innerHTML = html;
  }

  function getFilters() {
    const branch = $('f-branch').value;
    return {
      region: REGIONAL ? D.region : $('f-region').value,
      branch: branch === '' ? null : Number(branch),
      product: REGIONAL ? '' : $('f-product').value,
      focusYear: REGIONAL ? RY : Number($('f-year').value),
    };
  }

  const inLocation = (b, f) => f.branch !== null ? b === f.branch : (!f.region || D.branches[b].region === f.region);
  const inProduct = (cat, f) => f.product === 'enterprise' ? cat === ENT : f.product === 'education' ? cat === EDU : true;

  // ---------- aggregation ----------
  function summarize(loans) {
    const s = { loans: 0, disb: 0, bens: new Set(), ytdLoans: 0, ytdDisb: 0, ytdBens: new Set(), curLoans: 0, curDisb: 0,
      curBens: new Set(), os: 0, active: 0, b30: 0, b60: 0, b180: 0, arrearsCases: 0, arrearsAmt: 0, writeOffCases: 0 };
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

  function groupRows(f) {
    const byBranch = !!f.region;
    const m = new Map();
    D.loans.forEach((l) => {
      if (f.region && D.branches[l[L_BRANCH]].region !== f.region) return;
      if (!inProduct(l[L_CAT], f)) return;
      const k = byBranch ? l[L_BRANCH] : D.branches[l[L_BRANCH]].region;
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(l);
    });
    return [...m.entries()].map(([k, ls]) => ({
      key: k, label: byBranch ? D.branches[k].name : k, s: summarize(ls), highlight: byBranch && k === f.branch,
    }));
  }

  // ---------- SVG charts (same geometry as Model_KFT_Report.py) ----------
  const svgOpen = (w, h, size) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="100%" font-family="Segoe UI, Arial, sans-serif" font-size="${size}">`;
  const axisLabel = (v) => fmtPKR(v).replace('PKR ', '');
  function niceStep(max, ticks = 4) {
    const raw = max / ticks, exp = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / exp;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * exp;
  }

  function lineChart(labels, series, fill = false, legend = true, width = 620, height = 280) {
    const left = 62, right = 14, top = 14, bottom = legend ? 58 : 34;
    const pw = width - left - right, ph = height - top - bottom;
    const values = series.flatMap((s) => s.values.filter((v) => v !== null));
    const maxV = values.length && Math.max(...values) > 0 ? Math.max(...values) : 1;
    const step = niceStep(maxV), yMax = step * Math.ceil(maxV / step), n = labels.length;
    const xAt = (i) => left + (n > 1 ? pw * i / (n - 1) : pw / 2);
    const yAt = (v) => top + ph - v / yMax * ph;
    let out = svgOpen(width, height, 10);
    for (let t = 0; t <= yMax + step / 2; t += step) {
      const y = yAt(t).toFixed(1);
      out += `<line x1="${left}" y1="${y}" x2="${width - right}" y2="${y}" stroke="${C.grid}"/>` +
        `<text x="${left - 6}" y="${(+y + 3).toFixed(1)}" text-anchor="end" fill="${C.muted}">${axisLabel(t)}</text>`;
    }
    labels.forEach((l, i) => { out += `<text x="${xAt(i).toFixed(1)}" y="${top + ph + 16}" text-anchor="middle" fill="${C.muted}">${esc(l)}</text>`; });
    series.forEach((s) => {
      const segments = []; let cur = [];
      s.values.forEach((v, i) => { if (v === null) { if (cur.length) segments.push(cur); cur = []; } else cur.push([xAt(i), yAt(v)]); });
      if (cur.length) segments.push(cur);
      segments.forEach((seg) => {
        const pts = seg.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
        if (fill && seg.length > 1) {
          const base = top + ph;
          out += `<polygon points="${seg[0][0].toFixed(1)},${base} ${pts} ${seg[seg.length - 1][0].toFixed(1)},${base}" fill="${s.color}" fill-opacity="0.08"/>`;
        }
        out += `<polyline points="${pts}" fill="none" stroke="${s.color}" stroke-width="${s.width}" stroke-linejoin="round" stroke-linecap="round"/>`;
        seg.forEach(([x, y]) => { out += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.5" fill="${s.color}"/>`; });
      });
    });
    if (legend) {
      let x = left;
      series.forEach((s) => {
        out += `<rect x="${x}" y="${height - 16}" width="12" height="10" fill="${s.color}" rx="2"/>` +
          `<text x="${x + 16}" y="${height - 7}" fill="${C.text}" font-size="11">${esc(s.name)}</text>`;
        x += 26 + s.name.length * 7;
      });
    }
    return out + '</svg>';
  }

  function hbar(rows, valueFn, color, highlightColor, width = 620) {
    const sorted = rows.slice().sort((a, b) => valueFn(b) - valueFn(a));
    if (!sorted.length) return '<div class="empty">No data</div>';
    const rowH = 26, top = 6, labelW = 150, valueW = 96, height = top * 2 + rowH * sorted.length;
    const barW = width - labelW - valueW, maxV = Math.max(...sorted.map(valueFn)) || 1;
    let out = svgOpen(width, height, 11);
    sorted.forEach((r, i) => {
      const v = valueFn(r), y = top + i * rowH, w = Math.max(barW * v / maxV, v > 0 ? 1 : 0);
      out += `<text x="${labelW - 8}" y="${y + 16}" text-anchor="end" fill="${C.text}"${r.highlight ? ' font-weight="700"' : ''}>${esc(r.label)}</text>` +
        `<rect x="${labelW}" y="${y + 4}" width="${w.toFixed(1)}" height="${rowH - 8}" fill="${r.highlight ? highlightColor : color}" rx="2"/>` +
        `<text x="${(labelW + w + 6).toFixed(1)}" y="${y + 16}" fill="${C.muted}">${fmtPKR(v)}</text>`;
    });
    return out + '</svg>';
  }

  function vbar(rows, width = 620, height = 260) {
    const left = 62, right = 14, top = 22, bottom = 30, pw = width - left - right, ph = height - top - bottom;
    const maxV = Math.max(0, ...rows.map((r) => r[1])) || 1, step = niceStep(maxV), yMax = step * Math.ceil(maxV / step);
    let out = svgOpen(width, height, 10);
    for (let t = 0; t <= yMax + step / 2; t += step) {
      const y = (top + ph - t / yMax * ph).toFixed(1);
      out += `<line x1="${left}" y1="${y}" x2="${width - right}" y2="${y}" stroke="${C.grid}"/>` +
        `<text x="${left - 6}" y="${(+y + 3).toFixed(1)}" text-anchor="end" fill="${C.muted}">${axisLabel(t)}</text>`;
    }
    const slot = pw / rows.length;
    rows.forEach(([label, v, color], i) => {
      const h = v / yMax * ph, x = left + i * slot + slot * 0.2, w = slot * 0.6, y = top + ph - h;
      out += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" fill="${color}" rx="2"/>` +
        `<text x="${(x + w / 2).toFixed(1)}" y="${(y - 5).toFixed(1)}" text-anchor="middle" fill="${C.text}" font-size="11">${fmtPKR(v)}</text>` +
        `<text x="${(x + w / 2).toFixed(1)}" y="${top + ph + 16}" text-anchor="middle" fill="${C.muted}" font-size="11">${esc(label)}</text>`;
    });
    return out + '</svg>';
  }

  function donut(parts, width = 620, height = 240) {
    const total = parts.reduce((a, p) => a + p[1], 0), cx = 130, cy = height / 2, r = 78, stroke = 34, circ = 2 * Math.PI * r;
    let out = svgOpen(width, height, 12), offset = 0;
    if (!total) out += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${C.grid}" stroke-width="${stroke}"/>`;
    parts.forEach(([, v, color]) => {
      if (!total || v <= 0) return;
      const len = circ * v / total;
      out += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${stroke}" stroke-dasharray="${len.toFixed(2)} ${(circ - len).toFixed(2)}" stroke-dashoffset="${(-offset).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"/>`;
      offset += len;
    });
    let y = cy - 44 * (parts.length - 1) / 2 + 4;
    parts.forEach(([label, v, color]) => {
      out += `<rect x="270" y="${(y - 10).toFixed(1)}" width="14" height="14" rx="3" fill="${color}"/>` +
        `<text x="292" y="${(y + 2).toFixed(1)}" fill="${C.text}" font-weight="600">${esc(label)}</text>` +
        `<text x="390" y="${(y + 2).toFixed(1)}" fill="${C.muted}">${fmtPKR(v)} · ${pct(v, total)}</text>`;
      y += 44;
    });
    return out + '</svg>';
  }

  // ---------- render ----------
  const kpiCard = ([label, value, sub, color]) =>
    `<div class="kpi-card" style="border-left-color:${color};"><div class="kpi-label">${esc(label)}</div><div class="kpi-value">${esc(value)}</div><div class="kpi-sub">${esc(sub)}</div></div>`;

  function render() {
    const f = getFilters();
    const scope = D.loans.filter((l) => inLocation(l[L_BRANCH], f) && inProduct(l[L_CAT], f));
    const scopeAll = D.loans.filter((l) => inLocation(l[L_BRANCH], f));
    const s = summarize(scope);
    const rows = groupRows(f);
    const dim = f.region ? 'Branch' : 'Region';
    const period = MONTHS_LONG[RM - 1] + ' ' + RY, ytdRange = 'Jan – ' + MONTHS[RM - 1] + ' ' + RY;
    const where = f.branch !== null ? D.branches[f.branch].name : (f.region || 'All Regions');
    const what = f.product ? f.product[0].toUpperCase() + f.product.slice(1) : 'All Products';

    document.querySelectorAll('.rpt-dim').forEach((el) => { el.textContent = dim; });
    $('rpt-kpi-heading').textContent = 'Key Performance Indicators — ' + where + ' / ' + what;
    $('rpt-rank-title').textContent = (f.region ? 'Branch' : 'Regional') + ' Performance & Ranking';

    let ent = 0, edu = 0, total = 0;
    scopeAll.forEach((l) => { total += l[L_DISB]; if (l[L_CAT] === ENT) ent += l[L_DISB]; else if (l[L_CAT] === EDU) edu += l[L_DISB]; });

    $('rpt-kpis').innerHTML = [
      ['# of Beneficiaries', fmtNum(s.bens.size), 'Unique CNICs, since inception', C.dark],
      ['# of Loans', fmtNum(s.loans), 'Cumulative loan count', C.dark],
      ['Loan Disbursement', fmtPKR(s.disb), 'PKR, since inception', C.green],
      ['Outstanding Loans', fmtPKR(s.os), fmtNum(s.active) + ' active loans', C.green],
      ['Non-Performing Loans', fmtPKR(s.arrearsAmt), pct(s.arrearsAmt, s.os, 2) + ' of outstanding · ' + fmtNum(s.arrearsCases) + ' loans (30+ days)', C.red],
      ['Avg Loan Size', fmtPKR(s.loans ? s.disb / s.loans : 0), 'PKR per loan', C.accent],
      ['YTD Disbursement', fmtPKR(s.ytdDisb), ytdRange + ' · ' + fmtNum(s.ytdLoans) + ' loans', C.gold],
      ['YTD # of Beneficiaries', fmtNum(s.ytdBens.size), ytdRange, C.gold],
      ['Latest Month Disbursement', fmtPKR(s.curDisb), period + ' · ' + fmtNum(s.curLoans) + ' loans', C.green],
      ['Latest Month # of Beneficiaries', fmtNum(s.curBens.size), period, C.green],
      ['Enterprise Share', fmtPKR(ent), pct(ent, total) + ' of total disbursement (SI)', C.accent],
      ['Education Share', fmtPKR(edu), pct(edu, total) + ' of total disbursement (SI)', C.gold],
    ].map(kpiCard).join('');

    $('rpt-dist-title').textContent = f.region ? f.region + ' — Branch / Local Council Distribution' : 'National Council Distribution';
    $('rpt-dist').innerHTML = rows.slice().sort((a, b) => a.label.localeCompare(b.label)).map((r) => `
      <div class="dist-card${r.highlight ? ' selected' : ''}"><div class="dist-name">${esc(r.label)}</div>
        <div class="v">${fmtNum(r.s.bens.size)}</div><div class="l">Beneficiaries</div>
        <div class="dist-row"><div><div class="v">${fmtNum(r.s.loans)}</div><div class="l">Loan Disbursed</div></div>
          <div><div class="v">${fmtNum(r.s.active)}</div><div class="l">Active Loan</div></div></div></div>`).join('')
      || '<div class="empty">No data for the selected filters</div>';

    // monthly trend
    const years = [RY - 2, RY - 1, RY];
    const yearLabel = (y) => y === RY && RM < 12 ? y + ' YTD' : String(y);
    const series = {};
    years.forEach((y) => { series[y] = new Array(12).fill(0); });
    scope.forEach((l) => { const y = Math.floor(l[L_YM] / 100); if (series[y]) series[y][(l[L_YM] % 100) - 1] += l[L_DISB]; });
    for (let m = RM; m < 12; m++) series[RY][m] = null;
    $('rpt-trend-title').textContent = 'Monthly Disbursement Trend — ' + years.map(yearLabel).join(' vs ');
    $('rpt-trend').innerHTML = lineChart(MONTHS, years.map((y, i) => ({
      name: yearLabel(y), values: series[y], color: TREND_COLORS[i], width: y === f.focusYear ? 3.5 : 1.75,
    })));
    $('rpt-mix').innerHTML = donut([['Enterprise', ent, C.green], ['Education', edu, C.gold]]);
    $('rpt-group-si').innerHTML = hbar(rows, (r) => r.s.disb, C.green, C.gold);
    $('rpt-group-ytd').innerHTML = hbar(rows, (r) => r.s.ytdDisb, C.accent, C.red);

    // ranking
    const ranked = rows.slice().sort((a, b) => b.s.disb - a.s.disb);
    const totalDisb = ranked.reduce((a, r) => a + r.s.disb, 0);
    $('rpt-rank').innerHTML = ranked.map((r, i) => `<tr${r.highlight ? ' class="selected-row"' : ''}>
        <td><span class="rank-badge ${i < 3 ? 'rank-' + (i + 1) : ''}">${i + 1}</span></td><td>${esc(r.label)}</td>
        <td class="num">${fmtNum(r.s.bens.size)}</td><td class="num">${fmtNum(r.s.loans)}</td><td class="num">${fmtNum(r.s.disb)}</td>
        <td class="num">${pct(r.s.disb, totalDisb)}</td><td class="num">${fmtNum(r.s.ytdBens.size)}</td>
        <td class="num">${fmtNum(r.s.ytdLoans)}</td><td class="num">${fmtNum(r.s.ytdDisb)}</td></tr>`).join('')
      || '<tr><td colspan="9" class="empty">No data for the selected filters</td></tr>';

    // year-on-year
    const totals = (y, m) => {
      let loans = 0, disb = 0; const bens = new Set();
      scope.forEach((l) => { if (Math.floor(l[L_YM] / 100) === y && l[L_YM] % 100 <= m) { loans++; disb += l[L_DISB]; bens.add(l[L_BEN]); } });
      return [loans, disb, bens.size];
    };
    const yoy = [];
    [[RY - 2, RY - 1, 12], [RY - 1, RY, RM]].forEach(([y1, y2, m]) => {
      const a = totals(y1, m), b = totals(y2, m);
      const basis = m === 12 ? 'Full Year' : 'Jan–' + MONTHS[m - 1] + ', comparable';
      [['Disbursement', 1], ['Loan Count', 0], ['Beneficiaries', 2]].forEach(([label, idx]) => {
        const g = a[idx] ? (b[idx] - a[idx]) / a[idx] * 100 : null;
        yoy.push(`<div class="yoy-card"><div class="lbl">${y1} → ${y2} ${label} Growth (${basis})</div>
          <div class="val ${g === null ? '' : g >= 0 ? 'pos' : 'neg'}">${g === null ? '—' : (g >= 0 ? '+' : '') + g.toFixed(1) + '%'}</div></div>`);
      });
    });
    $('rpt-yoy').innerHTML = yoy.join('');

    // portfolio quality
    $('rpt-pq').innerHTML = [
      ['Total Outstanding', fmtPKR(s.os), 'Total principal outstanding', C.dark],
      ['30-60 Days Past Due', fmtPKR(s.b30), pct(s.b30, s.os, 2) + ' of outstanding', C.gold],
      ['60-180 Days Past Due', fmtPKR(s.b60), pct(s.b60, s.os, 2) + ' of outstanding', C.orange],
      ['180+ Days Past Due', fmtPKR(s.b180), pct(s.b180, s.os, 2) + ' of outstanding', C.red],
      ['Cases in Arrears', fmtNum(s.arrearsCases), fmtPKR(s.arrearsAmt) + ' outstanding (30+ days)', C.gold],
      ['Written-off Loans', fmtNum(s.writeOffCases), fmtPKR(s.b180) + ' outstanding (180+ days)', C.green],
    ].map(kpiCard).join('');
    $('rpt-aging').innerHTML = vbar([['30-59 Days', s.b30, C.gold], ['60-179 Days', s.b60, C.orange], ['180+ Days', s.b180, C.red]]);

    const arrearsTotals = new Array(D.arrearsTrend.months.length).fill(0);
    D.arrearsTrend.rows.forEach(([mi, b, cat, amt]) => { if (inLocation(b, f) && inProduct(cat, f)) arrearsTotals[mi] += amt; });
    $('rpt-arrears-trend').innerHTML = lineChart(
      D.arrearsTrend.months.map((m) => MONTHS[Number(m.slice(5, 7)) - 1] + ' ' + m.slice(2, 4)),
      [{ name: 'Arrears', values: arrearsTotals, color: C.red, width: 2.5 }], true, false);
    $('rpt-arrears-group').innerHTML = hbar(rows, (r) => r.s.arrearsAmt, C.red, C.gold);

    let entA = 0, eduA = 0;
    scope.forEach((l) => { if (l[L_OD] >= 30) { if (l[L_CAT] === ENT) entA += l[L_OS]; else if (l[L_CAT] === EDU) eduA += l[L_OS]; } });
    $('rpt-arrears-sector').innerHTML = donut([['Enterprise', entA, C.green], ['Education', eduA, C.gold]]);

    // arrear listing (regional report only)
    if ($('rpt-listing')) {
      const listing = D.arrearsListing.filter((r) => inLocation(r.b, f) && inProduct(r.c, f));
      $('rpt-listing-count').textContent = fmtNum(listing.length);
      $('rpt-listing').innerHTML = listing.map((a) => `<tr>
          <td>${esc(a.sector_code)}</td><td>${esc(a.branch_name)}</td><td>${esc(a.gender)}</td><td>${esc(a.mobile_no)}</td>
          <td>${esc(a.loan_title)}</td><td>${esc(a.loan_no)}</td><td>${esc(a.product_code)}</td><td>${esc(a.booked_on)}</td>
          <td class="num">${fmtNum(a.disbursed_amount)}</td><td>${esc(a.loan_status)}</td><td class="num">${fmtNum(a.overdue_days)}</td>
          <td class="num">${fmtNum(a.principal_outstanding)}</td>
          <td><span class="tag ${a.c === EDU ? 'edu' : ''}">${a.c === EDU ? 'Education' : 'Enterprise'}</span></td></tr>`).join('')
        || '<tr><td colspan="13" class="empty">No loans in arrears</td></tr>';
    }
  }

  document.documentElement.classList.add('js');
  setupFilters();
})();
