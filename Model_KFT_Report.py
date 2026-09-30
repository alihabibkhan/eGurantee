"""
Offline KFT Management / Regional report.

Builds the same figures as the KFT dashboard (static/assets/jsFiles/kft_dashboard.js) on the server and
renders them into one self-contained HTML file: inline CSS, charts as inline SVG, no scripts and no external
resources, so the emailed report opens without any web access.
"""
import math

from markupsafe import Markup, escape as _escape

from imports import *

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
               'November', 'December']
TREND_COLORS = ['#9BB0A5', '#2E8B57', '#143D2A']
GREEN, DARK, ACCENT, GOLD, ORANGE, RED, MUTED = '#1F5C3F', '#143D2A', '#2E8B57', '#C99A2E', '#E08E45', '#B4453A', '#64756B'

# loan tuple indexes (see Model_KFT_Dashboard.build_kft_dashboard_data)
L_BRANCH, L_CAT, L_BEN, L_YM, L_DISB, L_OS, L_OD = range(7)


# ---------- formatting ----------
def fmt_num(n):
    return '—' if n is None else f"{round(n):,}"


def fmt_pkr(n):
    if n is None:
        return '—'
    a = abs(n)
    if a >= 1e9:
        return f"PKR {n / 1e9:.2f}B"
    if a >= 1e6:
        return f"PKR {n / 1e6:.1f}M"
    return 'PKR ' + fmt_num(n)


def fmt_pct(part, whole, digits=1):
    return f"{part / whole * 100:.{digits}f}%" if whole else '—'


# ---------- aggregation ----------
def _summarize(loans, ry, rym):
    s = {
        'loans': 0, 'disb': 0.0, 'bens': set(),
        'ytd_loans': 0, 'ytd_disb': 0.0, 'ytd_bens': set(),
        'cur_loans': 0, 'cur_disb': 0.0, 'cur_bens': set(),
        'os': 0.0, 'active': 0,
        'b30': 0.0, 'b60': 0.0, 'b180': 0.0, 'arrears_cases': 0, 'arrears_amt': 0.0, 'write_off_cases': 0,
        'ent': 0.0, 'edu': 0.0,
    }
    for l in loans:
        ym, disb, os_p, od = l[L_YM], l[L_DISB], l[L_OS], l[L_OD]
        s['loans'] += 1
        s['disb'] += disb
        s['bens'].add(l[L_BEN])
        if ym // 100 == ry and ym <= rym:
            s['ytd_loans'] += 1
            s['ytd_disb'] += disb
            s['ytd_bens'].add(l[L_BEN])
        if ym == rym:
            s['cur_loans'] += 1
            s['cur_disb'] += disb
            s['cur_bens'].add(l[L_BEN])
        if os_p > 0:
            s['os'] += os_p
            s['active'] += 1
        if od >= 30:
            s['arrears_cases'] += 1
            s['arrears_amt'] += os_p
            if od < 60:
                s['b30'] += os_p
            elif od < 180:
                s['b60'] += os_p
            else:
                s['b180'] += os_p
                s['write_off_cases'] += 1
        if l[L_CAT] == CATEGORY_ENTERPRISE:
            s['ent'] += disb
        elif l[L_CAT] == CATEGORY_EDUCATION:
            s['edu'] += disb
    return s


def _period_totals(loans, year, last_month):
    count, disb, bens = 0, 0.0, set()
    for l in loans:
        ym = l[L_YM]
        if ym // 100 == year and ym % 100 <= last_month:
            count += 1
            disb += l[L_DISB]
            bens.add(l[L_BEN])
    return count, disb, len(bens)


def build_report_context(data, region=None, commentary=''):
    """region=None -> Management report (grouped by region); region name -> Regional report (grouped by branch)."""
    ry, rm = data['meta']['reportYear'], data['meta']['reportMonth']
    rym = ry * 100 + rm
    branches = data['branches']

    if region:
        scope = [l for l in data['loans'] if branches[l[L_BRANCH]]['region'] == region]
        group_of = lambda l: l[L_BRANCH]
        group_label = lambda k: branches[k]['name']
    else:
        scope = data['loans']
        group_of = lambda l: branches[l[L_BRANCH]]['region']
        group_label = lambda k: k

    s = _summarize(scope, ry, rym)
    period = f"{MONTHS_LONG[rm - 1]} {ry}"
    ytd_range = f"Jan – {MONTHS[rm - 1]} {ry}"

    groups = {}
    for l in scope:
        groups.setdefault(group_of(l), []).append(l)
    group_rows = [{'key': k, 'label': group_label(k), 's': _summarize(ls, ry, rym)} for k, ls in groups.items()]

    kpis = [
        ('# of Beneficiaries', fmt_num(len(s['bens'])), 'Unique CNICs, since inception', DARK),
        ('# of Loans', fmt_num(s['loans']), 'Cumulative loan count', DARK),
        ('Loan Disbursement', fmt_pkr(s['disb']), 'PKR, since inception', GREEN),
        ('Outstanding Loans', fmt_pkr(s['os']), f"{fmt_num(s['active'])} active loans", GREEN),
        ('Non-Performing Loans', fmt_pkr(s['arrears_amt']),
         f"{fmt_pct(s['arrears_amt'], s['os'], 2)} of outstanding · {fmt_num(s['arrears_cases'])} loans (30+ days)", RED),
        ('Avg Loan Size', fmt_pkr(s['disb'] / s['loans'] if s['loans'] else 0), 'PKR per loan', ACCENT),
        ('YTD Disbursement', fmt_pkr(s['ytd_disb']), f"{ytd_range} · {fmt_num(s['ytd_loans'])} loans", GOLD),
        ('YTD # of Beneficiaries', fmt_num(len(s['ytd_bens'])), ytd_range, GOLD),
        ('Latest Month Disbursement', fmt_pkr(s['cur_disb']), f"{period} · {fmt_num(s['cur_loans'])} loans", GREEN),
        ('Latest Month # of Beneficiaries', fmt_num(len(s['cur_bens'])), period, GREEN),
        ('Enterprise Share', fmt_pkr(s['ent']), f"{fmt_pct(s['ent'], s['disb'])} of total disbursement (SI)", ACCENT),
        ('Education Share', fmt_pkr(s['edu']), f"{fmt_pct(s['edu'], s['disb'])} of total disbursement (SI)", GOLD),
    ]

    distribution = sorted(
        ({'label': r['label'], 'bens': fmt_num(len(r['s']['bens'])), 'loans': fmt_num(r['s']['loans']),
          'active': fmt_num(r['s']['active'])} for r in group_rows),
        key=lambda r: r['label'])

    # Monthly disbursement trend for the last three years
    years = [ry - 2, ry - 1, ry]
    series = {y: [0.0] * 12 for y in years}
    for l in scope:
        y = l[L_YM] // 100
        if y in series:
            series[y][l[L_YM] % 100 - 1] += l[L_DISB]
    for m in range(rm, 12):
        series[ry][m] = None
    year_label = lambda y: f"{y} YTD" if y == ry and rm < 12 else str(y)
    trend_svg = svg_line_chart(
        MONTHS, [(year_label(y), series[y], TREND_COLORS[i], 3.5 if y == ry else 1.75) for i, y in enumerate(years)])

    ranked = sorted(group_rows, key=lambda r: -r['s']['disb'])
    total_disb = sum(r['s']['disb'] for r in ranked)
    ranking = [{
        'rank': i + 1, 'label': r['label'],
        'bens': fmt_num(len(r['s']['bens'])), 'loans': fmt_num(r['s']['loans']), 'disb': fmt_num(r['s']['disb']),
        'share': fmt_pct(r['s']['disb'], total_disb), 'ytd_bens': fmt_num(len(r['s']['ytd_bens'])),
        'ytd_loans': fmt_num(r['s']['ytd_loans']), 'ytd_disb': fmt_num(r['s']['ytd_disb']),
    } for i, r in enumerate(ranked)]

    # Year-on-year: last completed pair on a full-year basis, ongoing year on the same YTD months
    yoy = []
    growth = lambda a, b: (b - a) / a * 100 if a else None
    for y1, y2, m in [(ry - 2, ry - 1, 12), (ry - 1, ry, rm)]:
        a, b = _period_totals(scope, y1, m), _period_totals(scope, y2, m)
        basis = 'Full Year' if m == 12 else f"Jan–{MONTHS[m - 1]}, comparable"
        for label, idx in (('Disbursement', 1), ('Loan Count', 0), ('Beneficiaries', 2)):
            g = growth(a[idx], b[idx])
            yoy.append({
                'label': f"{y1} → {y2} {label} Growth ({basis})",
                'value': '—' if g is None else f"{'+' if g >= 0 else ''}{g:.1f}%",
                'cls': '' if g is None else ('pos' if g >= 0 else 'neg'),
            })

    pq_kpis = [
        ('Total Outstanding', fmt_pkr(s['os']), 'Total principal outstanding', DARK),
        ('30-60 Days Past Due', fmt_pkr(s['b30']), f"{fmt_pct(s['b30'], s['os'], 2)} of outstanding", GOLD),
        ('60-180 Days Past Due', fmt_pkr(s['b60']), f"{fmt_pct(s['b60'], s['os'], 2)} of outstanding", ORANGE),
        ('180+ Days Past Due', fmt_pkr(s['b180']), f"{fmt_pct(s['b180'], s['os'], 2)} of outstanding", RED),
        ('Cases in Arrears', fmt_num(s['arrears_cases']), f"{fmt_pkr(s['arrears_amt'])} outstanding (30+ days)", GOLD),
        ('Written-off Loans', fmt_num(s['write_off_cases']), f"{fmt_pkr(s['b180'])} outstanding (180+ days)", GREEN),
    ]

    trend = data['arrearsTrend']
    arrears_totals = [0.0] * len(trend['months'])
    for mi, b, cat, amt in trend['rows']:
        if not region or branches[b]['region'] == region:
            arrears_totals[mi] += amt
    arrears_labels = [f"{MONTHS[int(m[5:7]) - 1]} {m[2:4]}" for m in trend['months']]

    ent_arrears = sum(l[L_OS] for l in scope if l[L_OD] >= 30 and l[L_CAT] == CATEGORY_ENTERPRISE)
    edu_arrears = sum(l[L_OS] for l in scope if l[L_OD] >= 30 and l[L_CAT] == CATEGORY_EDUCATION)

    listing = []
    if region:
        listing = [dict(r, sector='Education' if r['c'] == CATEGORY_EDUCATION else 'Enterprise')
                   for r in data['arrearsListing'] if branches[r['b']]['region'] == region]

    dim = 'Branch' if region else 'Region'
    by_disb = lambda key: [(r['label'], r['s'][key]) for r in sorted(group_rows, key=lambda r: -r['s'][key])]

    # Data embedded in the file so its filters work offline. Only the loans in scope are included and the
    # arrear listing (borrower details) only goes into the regional report of that region.
    embedded = {
        'mode': 'regional' if region else 'management',
        'region': region,
        'meta': data['meta'],
        'regions': [region] if region else data['regions'],
        'branches': [{'name': b['name'], 'region': b['region']} for b in branches],
        'loans': scope,
        'arrearsTrend': {
            'months': trend['months'],
            'rows': [row for row in trend['rows'] if not region or branches[row[1]]['region'] == region],
        },
        'arrearsListing': [{k: v for k, v in row.items() if k != 'sector'} for row in listing],
    }

    return {
        'title': ('KFT - Khushali Foundation Trust - Regional Report · ' + region) if region
        else 'KFT - Khushali Foundation Trust - Management Report',
        'region': region,
        'dim': dim,
        'period': period,
        'report_year': ry,
        'mis_date': data['meta']['misDate'],
        'loan_count': fmt_num(s['loans']),
        'generated_at': datetime.now().strftime('%d-%b-%Y %H:%M'),
        'commentary': commentary.strip(),
        'kpis': kpis,
        'distribution_title': (region + ' — Branch / Local Council Distribution') if region
        else 'National Council Distribution',
        'distribution': distribution,
        'trend_title': 'Monthly Disbursement Trend — ' + ' vs '.join(year_label(y) for y in years),
        'trend_svg': trend_svg,
        'mix_svg': svg_donut([('Enterprise', s['ent'], GREEN), ('Education', s['edu'], GOLD)]),
        'group_si_svg': svg_hbar(by_disb('disb'), GREEN),
        'group_ytd_svg': svg_hbar(by_disb('ytd_disb'), ACCENT),
        'ranking': ranking,
        'yoy': yoy,
        'pq_kpis': pq_kpis,
        'aging_svg': svg_vbar([('30-59 Days', s['b30'], GOLD), ('60-179 Days', s['b60'], ORANGE),
                               ('180+ Days', s['b180'], RED)]),
        'arrears_trend_svg': svg_line_chart(arrears_labels, [('Arrears', arrears_totals, RED, 2.5)], fill=True,
                                            legend=False),
        'arrears_group_svg': svg_hbar(by_disb('arrears_amt'), RED),
        'arrears_sector_svg': svg_donut([('Enterprise', ent_arrears, GREEN), ('Education', edu_arrears, GOLD)]),
        'listing': listing,
        'embedded': embedded,
        'offline_js': _offline_script(),
        # short summary for the email body
        'summary': [
            ('Beneficiaries (since inception)', fmt_num(len(s['bens']))),
            ('Loans (since inception)', fmt_num(s['loans'])),
            ('Disbursement (since inception)', fmt_pkr(s['disb'])),
            (f"YTD {ry} Disbursement", fmt_pkr(s['ytd_disb'])),
            (f"{period} Disbursement", fmt_pkr(s['cur_disb'])),
            ('Outstanding Portfolio', fmt_pkr(s['os'])),
            ('Non-Performing Loans (30+ days)', f"{fmt_pkr(s['arrears_amt'])} ({fmt_pct(s['arrears_amt'], s['os'], 2)})"),
        ],
    }


def _offline_script():
    # Inlined into the report (never linked) so the filters run without any web access
    path = os.path.join(current_app.root_path, 'static', 'assets', 'jsFiles', 'kft_report_offline.js')
    with open(path, encoding='utf-8') as f:
        script = f.read()
    return Markup(re.sub(r'</(script)', r'<\\/\1', script, flags=re.IGNORECASE))


def render_kft_report(data, region=None, commentary=''):
    return render_template('kft_report.html', r=build_report_context(data, region, commentary))


# ---------- inline SVG charts ----------
def _nice_step(max_value, ticks=4):
    raw = max_value / ticks
    exp = 10 ** math.floor(math.log10(raw))
    f = raw / exp
    return (1 if f <= 1 else 2 if f <= 2 else 5 if f <= 5 else 10) * exp


def _axis_label(v):
    return fmt_pkr(v).replace('PKR ', '')


def svg_line_chart(labels, series, fill=False, legend=True, width=620, height=280):
    left, right, top = 62, 14, 14
    bottom = 58 if legend else 34
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [v for _, vals, _, _ in series for v in vals if v is not None]
    max_v = max(values) if values and max(values) > 0 else 1
    step = _nice_step(max_v)
    y_max = step * math.ceil(max_v / step)
    n = len(labels)
    x_at = lambda i: left + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)
    y_at = lambda v: top + plot_h - (v / y_max * plot_h)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" '
             f'font-family="Segoe UI, Arial, sans-serif" font-size="10">']
    t = 0
    while t <= y_max + step / 2:
        y = y_at(t)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#E4EAE6"/>')
        parts.append(f'<text x="{left - 6}" y="{y + 3:.1f}" text-anchor="end" fill="{MUTED}">{_axis_label(t)}</text>')
        t += step
    for i, lbl in enumerate(labels):
        parts.append(f'<text x="{x_at(i):.1f}" y="{top + plot_h + 16}" text-anchor="middle" fill="{MUTED}">'
                     f'{_escape(lbl)}</text>')

    for name, vals, color, stroke in series:
        segments, current = [], []
        for i, v in enumerate(vals):
            if v is None:
                if current:
                    segments.append(current)
                current = []
            else:
                current.append((x_at(i), y_at(v)))
        if current:
            segments.append(current)
        for seg in segments:
            pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in seg)
            if fill and len(seg) > 1:
                base = top + plot_h
                parts.append(f'<polygon points="{seg[0][0]:.1f},{base} {pts} {seg[-1][0]:.1f},{base}" '
                             f'fill="{color}" fill-opacity="0.08"/>')
            parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{stroke}" '
                         f'stroke-linejoin="round" stroke-linecap="round"/>')
            for x, y in seg:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}"/>')

    if legend:
        x = left
        for name, _, color, _ in series:
            parts.append(f'<rect x="{x}" y="{height - 16}" width="12" height="10" fill="{color}" rx="2"/>')
            parts.append(f'<text x="{x + 16}" y="{height - 7}" fill="#1B2420" font-size="11">{_escape(name)}</text>')
            x += 26 + len(name) * 7
    parts.append('</svg>')
    return Markup(''.join(parts))


def svg_hbar(rows, color, width=620):
    """rows: [(label, value)] already sorted."""
    if not rows:
        return Markup('<div class="empty">No data</div>')
    row_h, top, label_w, value_w = 26, 6, 150, 96
    height = top * 2 + row_h * len(rows)
    bar_w = width - label_w - value_w
    max_v = max(v for _, v in rows) or 1
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" '
             f'font-family="Segoe UI, Arial, sans-serif" font-size="11">']
    for i, (label, v) in enumerate(rows):
        y = top + i * row_h
        w = max(bar_w * v / max_v, 1 if v > 0 else 0)
        parts.append(f'<text x="{label_w - 8}" y="{y + 16}" text-anchor="end" fill="#1B2420">{_escape(label)}</text>')
        parts.append(f'<rect x="{label_w}" y="{y + 4}" width="{w:.1f}" height="{row_h - 8}" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{label_w + w + 6:.1f}" y="{y + 16}" fill="{MUTED}">{fmt_pkr(v)}</text>')
    parts.append('</svg>')
    return Markup(''.join(parts))


def svg_vbar(rows, width=620, height=260):
    """rows: [(label, value, color)]"""
    left, right, top, bottom = 62, 14, 22, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    max_v = max((v for _, v, _ in rows), default=0) or 1
    step = _nice_step(max_v)
    y_max = step * math.ceil(max_v / step)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" '
             f'font-family="Segoe UI, Arial, sans-serif" font-size="10">']
    t = 0
    while t <= y_max + step / 2:
        y = top + plot_h - t / y_max * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#E4EAE6"/>')
        parts.append(f'<text x="{left - 6}" y="{y + 3:.1f}" text-anchor="end" fill="{MUTED}">{_axis_label(t)}</text>')
        t += step
    slot = plot_w / len(rows)
    for i, (label, v, color) in enumerate(rows):
        h = v / y_max * plot_h
        x = left + i * slot + slot * 0.2
        w = slot * 0.6
        y = top + plot_h - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{x + w / 2:.1f}" y="{y - 5:.1f}" text-anchor="middle" fill="#1B2420" font-size="11">'
                     f'{fmt_pkr(v)}</text>')
        parts.append(f'<text x="{x + w / 2:.1f}" y="{top + plot_h + 16}" text-anchor="middle" fill="{MUTED}" '
                     f'font-size="11">{_escape(label)}</text>')
    parts.append('</svg>')
    return Markup(''.join(parts))


def svg_donut(parts_in, width=620, height=240):
    """parts_in: [(label, value, color)]"""
    total = sum(v for _, v, _ in parts_in)
    cx, cy, r, stroke = 130, height / 2, 78, 34
    circ = 2 * math.pi * r
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" '
             f'font-family="Segoe UI, Arial, sans-serif" font-size="12">']
    if not total:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#E4EAE6" stroke-width="{stroke}"/>')
    offset = 0.0
    for label, v, color in parts_in:
        if not total or v <= 0:
            continue
        length = circ * v / total
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}" '
                     f'stroke-dasharray="{length:.2f} {circ - length:.2f}" stroke-dashoffset="{-offset:.2f}" '
                     f'transform="rotate(-90 {cx} {cy})"/>')
        offset += length
    y = cy - 44 * (len(parts_in) - 1) / 2 + 4
    for label, v, color in parts_in:
        parts.append(f'<rect x="270" y="{y - 10:.1f}" width="14" height="14" rx="3" fill="{color}"/>')
        parts.append(f'<text x="292" y="{y + 2:.1f}" fill="#1B2420" font-weight="600">{_escape(label)}</text>')
        parts.append(f'<text x="390" y="{y + 2:.1f}" fill="{MUTED}">{fmt_pkr(v)} · {fmt_pct(v, total)}</text>')
        y += 44
    parts.append('</svg>')
    return Markup(''.join(parts))
