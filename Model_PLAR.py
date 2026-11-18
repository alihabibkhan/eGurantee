from imports import *
import json

# ---------------------------------------------------------------------------------------------
# PLAR - Post Loan-Disbursement Assurance Review.
# Reads the bank MIS (tbl_post_disbursement) and the EGS applications (tbl_pre_disbursement_temp)
# and only ever WRITES to its own tbl_plar_* tables.
#
# EGS application statuses used here: 2 = Agreed (approved), 9 = Agreed with exception.
# The bank MIS holds one row per loan per monthly snapshot, so a month's population is the
# latest snapshot row of every loan booked in that month.
# ---------------------------------------------------------------------------------------------

# Products that go through EGS. The MIS carries every KF product; only these are in PLAR scope.
PLAR_PRODUCT_CODES = ['MEL1', 'STD1']
PLAR_APPROVED_STATUSES = ('2', '9')
# Fallback match window: an approval counts for a disbursement booked from 10 days before to 150 days after it
PLAR_MATCH_DAYS_BEFORE = 150
PLAR_MATCH_DAYS_AFTER = 10
PLAR_NPL_DAYS = 90

PLAR_CATEGORIES = ['Matrix / Limit', 'Loan Cycle', 'NPL / Credit', 'Disbursement', 'Documents',
                   'Fees / End Use', 'Duplicate', 'Other']
PLAR_SEVERITIES = ['Low', 'Medium', 'High', 'Critical']

# exception code -> (short name, default severity, issue category used when a finding is raised)
PLAR_EXCEPTIONS = {
    'NOAPPR':   ('Missing authorization: no approval', 'Critical', 'Disbursement'),
    'NOLETTER': ('Missing authorization: lien letter not sent', 'Critical', 'Disbursement'),
    'NOFINAL':  ('No final executive approval', 'Critical', 'Disbursement'),
    'MATRIX':   ('Over matrix / product limit', 'Critical', 'Matrix / Limit'),
    'AMTDIFF':  ('Amount mismatch', 'High', 'Disbursement'),
    'CYCLE':    ('Loan cycle mismatch', 'High', 'Loan Cycle'),
    'NPL':      ('Prior overdue / NPL', 'High', 'NPL / Credit'),
    'DUP':      ('Multiple active loans', 'High', 'Duplicate'),
    'DUPDISB':  ('Approval used for more than one loan', 'Critical', 'Duplicate'),
    'LIENPEND': ('Lien confirmation pending', 'Medium', 'Disbursement'),
}

_AMT = """NULLIF(regexp_replace(COALESCE({col}, ''), '[^0-9.]', '', 'g'), '')::numeric"""


def plar_month_start(value):
    """'2026-08' or '2026-08-15' -> date(2026, 8, 1). Raises ValueError for anything else."""
    text = str(value or '').strip()[:7]
    return datetime.strptime(text + '-01', '%Y-%m-%d').date()


def plar_next_month(d):
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def get_plar_months():
    """Months that have disbursements in scope, newest first."""
    rows = fetch_records("""
        SELECT to_char(date_trunc('month', booked_on), 'YYYY-MM') AS month, COUNT(DISTINCT loan_no) AS loans
        FROM tbl_post_disbursement
        WHERE product_code = ANY(%s) AND booked_on > DATE '2000-01-01'
        GROUP BY 1 ORDER BY 1 DESC LIMIT 36
    """, is_print=False, params=(PLAR_PRODUCT_CODES,))
    return rows


def get_plar_population(month_start):
    """
    Every in-scope loan booked in the month, with its matched EGS approval and the facts needed by the
    exception rules. Each row also gets an 'exceptions' list.
    The lien letter is the approval email EGS sends to the bank: tbl_pre_disbursement_temp.email_status = 2.
    """
    month_end = plar_next_month(month_start)

    query = f"""
        WITH mis AS (
            SELECT DISTINCT ON (p.loan_no)
                   p.loan_no, p.cnic, p.loan_title, p.branch_code, p.branch_name AS mis_branch_name, p.product_code,
                   p.booked_on, p.disbursed_amount, p.mis_date, p.application_num, p.overdue_days, p.loan_status
            FROM tbl_post_disbursement p
            WHERE p.booked_on >= %s AND p.booked_on < %s AND p.product_code = ANY(%s)
            ORDER BY p.loan_no, p.mis_date DESC
        ),
        hist AS (
            SELECT h.cnic, h.loan_no, MIN(h.booked_on) AS booked_on, MAX(h.overdue_days) AS max_overdue,
                   MAX(h.loan_closed_on) AS closed_on
            FROM tbl_post_disbursement h
            WHERE h.cnic IN (SELECT cnic FROM mis)
            GROUP BY h.cnic, h.loan_no
        )
        SELECT mis.*,
               b.branch_id, b.branch AS branch_label, b.role AS branch_role_id,
               ncd.national_council_distribution_id AS region_id,
               ncd.national_council_distribution_name AS region,
               m.pre_disb_temp_id, m.application_no, m.borrower_name, m.status AS egs_status,
               m.approved_amount, m.matrix_limit, m.loan_cycle, m.approved_by_id, m.approved_by,
               m.approved_date, m.exec_approval_pending, m.egs_branch_name, m.match_type, m.email_status,
               o.other_status,
               hs.prior_loans, hs.prior_npl, hs.other_active
        FROM mis
        LEFT JOIN LATERAL (
            SELECT bb.branch_id, bb.branch, bb.role, bb.national_council_distribution
            FROM tbl_branches bb WHERE bb.branch_code = mis.branch_code
            ORDER BY bb.live_branch DESC, bb.branch_id LIMIT 1
        ) b ON TRUE
        LEFT JOIN tbl_national_council_distribution ncd
               ON ncd.national_council_distribution_id = b.national_council_distribution
        LEFT JOIN LATERAL (
            SELECT e.pre_disb_temp_id, e."Application_No" AS application_no, e."Borrower_Name" AS borrower_name,
                   e.status, {_AMT.format(col='e."Loan_Amount"')} AS approved_amount,
                   e.kft_approved_loan_limit AS matrix_limit, e."Loan_Cycle" AS loan_cycle,
                   e.approved_by AS approved_by_id, u.name AS approved_by, e.approved_date,
                   e.exec_approval_pending, e."Branch_Name" AS egs_branch_name, e.email_status,
                   CASE WHEN NULLIF(mis.application_num, '') IS NOT NULL
                             AND e."Application_No" = mis.application_num THEN 'Application no.'
                        ELSE 'Fallback' END AS match_type
            FROM tbl_pre_disbursement_temp e
            LEFT JOIN tbl_users u ON u.user_id = e.approved_by
            WHERE e.status IN %s
              AND ( (NULLIF(mis.application_num, '') IS NOT NULL AND e."Application_No" = mis.application_num)
                 OR (e."CNIC" = mis.cnic
                     AND e.approved_date::date BETWEEN mis.booked_on - {PLAR_MATCH_DAYS_BEFORE}
                                                   AND mis.booked_on + {PLAR_MATCH_DAYS_AFTER}) )
            ORDER BY (e."Application_No" = NULLIF(mis.application_num, '')) DESC NULLS LAST,
                     ({_AMT.format(col='e."Loan_Amount"')} = mis.disbursed_amount) DESC NULLS LAST,
                     ABS(mis.booked_on - e.approved_date::date)
            LIMIT 1
        ) m ON TRUE
        LEFT JOIN LATERAL (
            SELECT e2.status AS other_status FROM tbl_pre_disbursement_temp e2
            WHERE e2."CNIC" = mis.cnic AND m.pre_disb_temp_id IS NULL
            ORDER BY e2."ApplicationDate" DESC NULLS LAST LIMIT 1
        ) o ON TRUE
        LEFT JOIN LATERAL (
            SELECT COUNT(*) FILTER (WHERE h.loan_no <> mis.loan_no AND h.booked_on < mis.booked_on) AS prior_loans,
                   COALESCE(BOOL_OR(h.max_overdue >= {PLAR_NPL_DAYS} AND h.loan_no <> mis.loan_no
                                    AND h.booked_on < mis.booked_on), FALSE) AS prior_npl,
                   COUNT(*) FILTER (WHERE h.loan_no <> mis.loan_no AND h.booked_on <= mis.booked_on
                                     AND (h.closed_on IS NULL OR h.closed_on < DATE '1901-01-01'
                                          OR h.closed_on >= mis.booked_on)) AS other_active
            FROM hist h WHERE h.cnic = mis.cnic
        ) hs ON TRUE
        ORDER BY mis.booked_on, mis.loan_no
    """
    rows = fetch_records(query, is_print=False,
                         params=(month_start, month_end, PLAR_PRODUCT_CODES, PLAR_APPROVED_STATUSES))

    # An application that explains more than one disbursement is a duplicate disbursement
    uses = {}
    for r in rows:
        if r['pre_disb_temp_id']:
            uses.setdefault(r['pre_disb_temp_id'], []).append(r['loan_no'])
    for r in rows:
        r['duplicate_loans'] = [x for x in uses.get(r['pre_disb_temp_id'], []) if x != r['loan_no']] \
            if r['pre_disb_temp_id'] else []
        r['exceptions'] = plar_exceptions_for(r)
    return rows


def _num(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _stated_cycle(v):
    digits = re.sub(r'\D', '', str(v or ''))
    return int(digits) if digits else None


def plar_exceptions_for(r):
    """Automated exception rules for one population row. Returns a list of {code, label, severity, detail}."""
    out = []

    def add(code, detail=''):
        name, sev, cat = PLAR_EXCEPTIONS[code]
        out.append({'code': code, 'label': name, 'severity': sev, 'category': cat, 'detail': detail})

    disbursed = _num(r.get('disbursed_amount'))
    if not r.get('pre_disb_temp_id'):
        other = r.get('other_status')
        if str(other or '') in PLAR_APPROVED_STATUSES:
            add('NOAPPR', 'An approved EGS application exists for this CNIC but its approval date is outside the '
                          f'{PLAR_MATCH_DAYS_BEFORE}-day window before disbursement')
        else:
            add('NOAPPR', 'No approved EGS application found for this CNIC' +
                (f' (latest application has status {other})' if other else ' (no application at all)'))
        return out

    if str(r.get('email_status') or '') != '2':
        add('NOLETTER', 'The approval exists but the lien letter was never emailed to the bank')
    if str(r.get('exec_approval_pending') or '') == '1':
        add('NOFINAL', 'EGS shows the executive approval as still pending')
    approved = _num(r.get('approved_amount'))
    limit = _num(r.get('matrix_limit'))
    # An application agreed "with exception" (status 9) is an authorised override of the matrix, so it only
    # counts as a breach when the bank paid out more than was approved.
    authorised_override = str(r.get('egs_status') or '') == '9' and approved is not None         and disbursed is not None and disbursed <= approved + 0.5
    if limit and disbursed is not None and disbursed > limit and not authorised_override:
        add('MATRIX', f'Disbursed {disbursed:,.0f} is above the KFT approved limit {limit:,.0f}')
    if approved is not None and disbursed is not None and abs(disbursed - approved) > 0.5:
        add('AMTDIFF', f'Approved {approved:,.0f}, disbursed {disbursed:,.0f}')
        if disbursed < approved:
            out[-1]['severity'] = 'Medium'    # paying out less than approved is a smaller concern than more
    # The bank history only goes back to 2020, so it can show too few earlier loans but not too many:
    # flag only when it shows MORE earlier loans than the cycle EGS recorded.
    stated = _stated_cycle(r.get('loan_cycle'))
    expected = int(r.get('prior_loans') or 0) + 1
    if stated is not None and expected > stated:
        add('CYCLE', f'EGS recorded cycle {stated}, but the bank history shows {expected - 1} earlier loan(s), '
                     f'so this should be cycle {expected}')
    if r.get('prior_npl'):
        add('NPL', f'An earlier loan of this CNIC was overdue {PLAR_NPL_DAYS}+ days')
    if int(r.get('other_active') or 0) >= 1:
        add('DUP', f"{int(r['other_active'])} other loan(s) of this CNIC were still open at disbursement")
    if r.get('duplicate_loans'):
        add('DUPDISB', 'Same approval also matches loan ' + ', '.join(r['duplicate_loans']))
    return out


def get_plar_approved_not_disbursed(month_start, population=None):
    """Approvals decided in the 90 days up to the end of the month whose lien letter was emailed to the bank but
    which have no matching disbursement in the bank MIS.
    An approval can only be judged "not disbursed" once the MIS of the FOLLOWING month has been loaded, so each row
    carries 'conclusive': False while it is still waiting for that snapshot ("Awaiting next MIS", not an exception)."""
    month_end = plar_next_month(month_start)
    matched_ids = {r['pre_disb_temp_id'] for r in (population or []) if r['pre_disb_temp_id']}
    rows = fetch_records(f"""
        SELECT e.pre_disb_temp_id, e."Application_No" AS application_no, e."Borrower_Name" AS borrower_name,
               e."CNIC" AS cnic, e."Branch_Name" AS branch_name, e."LoanProductCode" AS product,
               {_AMT.format(col='e."Loan_Amount"')} AS approved_amount, e.approved_date, e.status,
               ncd.national_council_distribution_name AS region
        FROM tbl_pre_disbursement_temp e
        LEFT JOIN LATERAL (
            SELECT bb.national_council_distribution FROM tbl_branches bb
            WHERE e."Branch_Name" LIKE CONCAT('%%', bb.branch_code, '%%') AND bb.live_branch = 1
            ORDER BY LENGTH(bb.branch_code) DESC LIMIT 1
        ) b ON TRUE
        LEFT JOIN tbl_national_council_distribution ncd
               ON ncd.national_council_distribution_id = b.national_council_distribution
        WHERE e.status IN %s AND e.email_status = 2
          AND e.approved_date::date >= %s::date - 90 AND e.approved_date::date < %s
          AND NOT EXISTS (
              SELECT 1 FROM tbl_post_disbursement p
              WHERE p.cnic = e."CNIC" AND p.booked_on >= e.approved_date::date - {PLAR_MATCH_DAYS_AFTER}
                AND p.product_code = ANY(%s))
        ORDER BY e.approved_date
    """, is_print=False, params=(PLAR_APPROVED_STATUSES, month_start, month_end, PLAR_PRODUCT_CODES))
    rows = [r for r in rows if r['pre_disb_temp_id'] not in matched_ids]
    latest = fetch_records("SELECT MAX(mis_date) AS d FROM tbl_post_disbursement", is_print=False)
    latest_mis = latest[0]['d'].date() if latest and latest[0]['d'] else None
    for r in rows:
        approved = r['approved_date']
        following_month_end = plar_next_month(plar_next_month(approved.date().replace(day=1))) - timedelta(days=1) \
            if approved else None
        r['conclusive'] = bool(latest_mis and following_month_end and latest_mis >= following_month_end)
    return rows


def plar_summary(rows, not_disbursed):
    matched = [r for r in rows if r['pre_disb_temp_id']]
    codes = {}
    for r in rows:
        for e in r['exceptions']:
            codes[e['code']] = codes.get(e['code'], 0) + 1
    return {
        'mis_loans': len(rows),
        'mis_amount': sum(_num(r['disbursed_amount']) or 0 for r in rows),
        'matched': len(matched),
        'matched_app_no': sum(1 for r in matched if r['match_type'] == 'Application no.'),
        'matched_fallback': sum(1 for r in matched if r['match_type'] == 'Fallback'),
        'unmatched': len(rows) - len(matched),
        'approved_not_disbursed': sum(1 for r in not_disbursed if r['conclusive']),
        'with_exceptions': sum(1 for r in rows if r['exceptions']),
        'by_code': codes,
        'lien_pending': sum(1 for r in not_disbursed if r['conclusive']),
        'lien_awaiting': sum(1 for r in not_disbursed if not r['conclusive']),
    }


def plar_audit(entity, entity_id, action, old=None, new=None):
    """One line in the PLAR audit trail (PLAR tables only)."""
    try:
        execute_command("""INSERT INTO tbl_plar_audit (entity, entity_id, action, old_value, new_value, user_id, user_name)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""", return_id=False,
                        params=(entity, str(entity_id), action, None if old is None else str(old),
                                None if new is None else str(new), int(get_current_user_id()),
                                session.get('name') or session.get('user_name')))
    except Exception as e:
        print('plar_audit exception:- ', str(e))


# ---------------------------------------------------------------------------------------------
# Sampling (5-10% per region, minimum 5, half risk-based / half random, locked once generated)
# ---------------------------------------------------------------------------------------------
PLAR_DEFAULT_PCT = 5
PLAR_MIN_PCT = 5
PLAR_MAX_PCT = 10
PLAR_MIN_CASES = 5

_POP_CACHE = {}


def get_plar_population_cached(month_start, ttl=45):
    """get_plar_population with a short in-process cache (case review opens one loan at a time)."""
    hit = _POP_CACHE.get(month_start)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    rows = get_plar_population(month_start)
    _POP_CACHE.clear()
    _POP_CACHE[month_start] = (time.time(), rows)
    return rows


def plar_regions():
    return fetch_records("""SELECT national_council_distribution_id AS region_id,
                                   national_council_distribution_name AS name
                            FROM tbl_national_council_distribution ORDER BY national_council_distribution_id""",
                         is_print=False)


def plar_sample_target(population, pct):
    if population <= 0:
        return 0
    return min(population, max(PLAR_MIN_CASES, -(-int(population) * float(pct) // 100)))  # ceiling


def get_plar_run(month_start):
    rows = fetch_records("SELECT * FROM tbl_plar_run WHERE mis_month = %s", is_print=False, params=(month_start,))
    return rows[0] if rows else None


def ensure_plar_run(month_start):
    run = get_plar_run(month_start)
    if run:
        return run
    execute_command("INSERT INTO tbl_plar_run (mis_month, created_by) VALUES (%s, %s) ON CONFLICT (mis_month) DO NOTHING",
                    return_id=False, params=(month_start, int(get_current_user_id())))
    return get_plar_run(month_start)


def get_plar_region_pcts(run):
    if not run:
        return {}
    rows = fetch_records("SELECT region_id, sample_pct FROM tbl_plar_region_target WHERE run_id = %s",
                         is_print=False, params=(run['run_id'],))
    return {r['region_id']: float(r['sample_pct']) for r in rows}


def set_plar_region_pct(month_start, region_id, pct):
    """Returns an error string, or None when saved."""
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return 'Enter a percentage between 5 and 10.'
    if pct < PLAR_MIN_PCT or pct > PLAR_MAX_PCT:
        return f'The sample must be between {PLAR_MIN_PCT}% and {PLAR_MAX_PCT}%.'
    run = ensure_plar_run(month_start)
    if run['sample_locked']:
        return 'The sample for this month is already generated and locked.'
    old = get_plar_region_pcts(run).get(int(region_id), PLAR_DEFAULT_PCT)
    execute_command("""INSERT INTO tbl_plar_region_target (run_id, region_id, sample_pct) VALUES (%s, %s, %s)
                       ON CONFLICT (run_id, region_id) DO UPDATE SET sample_pct = EXCLUDED.sample_pct""",
                    return_id=False, params=(run['run_id'], int(region_id), pct))
    plar_audit('Sample', f"{month_start:%Y-%m}", f'Sample % for region {region_id}', old, pct)
    return None


def plar_sampling_overview(month_start):
    """Per-region population / % / target, plus the saved sample rows when locked."""
    rows = get_plar_population_cached(month_start)
    run = get_plar_run(month_start)
    pcts = get_plar_region_pcts(run)
    sample = get_plar_sample(run) if run and run['sample_locked'] else []
    regions = []
    for reg in plar_regions():
        pop = sum(1 for r in rows if r['region_id'] == reg['region_id'])
        pct = pcts.get(reg['region_id'], PLAR_DEFAULT_PCT)
        mine = [s for s in sample if s['region_id'] == reg['region_id']]
        regions.append({'region_id': reg['region_id'], 'name': reg['name'], 'population': pop, 'pct': pct,
                        'target': int(plar_sample_target(pop, pct)),
                        'risk': sum(1 for s in mine if s['basis'] == 'Risk-Based'),
                        'random': sum(1 for s in mine if s['basis'] == 'Random')})
    return {'run': run, 'regions': regions, 'sample': sample, 'locked': bool(run and run['sample_locked']),
            'unmapped': sum(1 for r in rows if r['region_id'] is None)}


def plar_risk_score(r, amount_cutoff):
    """Higher = reviewed first. Mirrors the key points: bigger loans, repeat borrowers, unusual transactions."""
    score, why = 0.0, []
    if not r['pre_disb_temp_id']:
        score += 5
        why.append('no approval found')
    for e in r['exceptions']:
        score += 2.0 if e['severity'] in ('Critical', 'High') else 1.0
    if r['exceptions']:
        why.append(f"{len(r['exceptions'])} automated exception(s)")
    amount = _num(r['disbursed_amount']) or 0
    if amount_cutoff and amount >= amount_cutoff.get(r['product_code'], float('inf')):
        score += 1.5
        why.append('high amount for the product')
    if int(r.get('prior_loans') or 0) >= 2:
        score += 1.0
        why.append('repeat borrower')
    if r['booked_on'] and r['booked_on'].weekday() == 6:
        score += 1.0
        why.append('booked on a Sunday')
    return score, ', '.join(why) or 'highest risk score'


def generate_plar_sample(month_start):
    """Builds and locks the month's sample. Returns (count, error)."""
    run = ensure_plar_run(month_start)
    if run['sample_locked']:
        return 0, 'The sample for this month is already generated and cannot be redrawn.'
    rows = get_plar_population_cached(month_start, ttl=0)
    pcts = get_plar_region_pcts(run)
    by_product = {}
    for r in rows:
        by_product.setdefault(r['product_code'], []).append(_num(r['disbursed_amount']) or 0)
    cutoff = {p: sorted(v)[int(len(v) * 0.9)] if len(v) >= 10 else float('inf') for p, v in by_product.items()}
    rng = random.SystemRandom()
    chosen = []
    for reg in plar_regions():
        pool = [r for r in rows if r['region_id'] == reg['region_id']]
        target = int(plar_sample_target(len(pool), pcts.get(reg['region_id'], PLAR_DEFAULT_PCT)))
        if not target:
            continue
        scored = sorted(((plar_risk_score(r, cutoff), r) for r in pool), key=lambda x: -x[0][0])
        risk_n = -(-target // 2)
        picked = scored[:risk_n]
        rest = list(scored[risk_n:])
        rng.shuffle(rest)
        for (score, why), r in picked:
            chosen.append((r, 'Risk-Based', why, score, reg))
        for (score, why), r in rest[:target - risk_n]:
            chosen.append((r, 'Random', 'Random draw', score, reg))
    for r, basis, why, score, reg in chosen:
        execute_command("""INSERT INTO tbl_plar_sample (run_id, loan_no, pre_disb_temp_id, region_id, region_name, branch_code,
                               branch_name, product_code, disbursed_amount, basis, why, risk_score, created_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id, loan_no) DO NOTHING""",
                        return_id=False,
                        params=(run['run_id'], r['loan_no'], r['pre_disb_temp_id'], reg['region_id'], reg['name'],
                                r['branch_code'], r['mis_branch_name'], r['product_code'], r['disbursed_amount'],
                                basis, why, round(score, 2), int(get_current_user_id())))
    execute_command("UPDATE tbl_plar_run SET sample_locked = 1, locked_by = %s, locked_date = CURRENT_TIMESTAMP WHERE run_id = %s",
                    return_id=False, params=(int(get_current_user_id()), run['run_id']))
    plar_audit('Sample', f"{month_start:%Y-%m}", 'Sample generated and locked', None, f'{len(chosen)} cases')
    return len(chosen), None


def get_plar_sample(run):
    if not run:
        return []
    return fetch_records("""
        SELECT s.sample_id, s.loan_no, s.pre_disb_temp_id, s.region_id, s.region_name, s.branch_code, s.branch_name,
               s.product_code, s.disbursed_amount, s.basis, s.why, s.risk_score,
               rv.review_id, rv.overall_status, rv.issue_severity, rv.reviewed_date, u.name AS reviewed_by
        FROM tbl_plar_sample s
        LEFT JOIN tbl_plar_review rv ON rv.sample_id = s.sample_id
        LEFT JOIN tbl_users u ON u.user_id = rv.reviewed_by
        WHERE s.run_id = %s ORDER BY s.region_id, s.basis DESC, s.risk_score DESC
    """, is_print=False, params=(run['run_id'],))


# ---------------------------------------------------------------------------------------------
# Case review (single screen) and findings
# ---------------------------------------------------------------------------------------------
PLAR_CHECKS = [  # key, label, exception codes that pre-fill it as an issue
    ('approval', 'Disbursement traceable to final KFT approval', ('NOAPPR', 'NOFINAL', 'DUPDISB')),
    ('matrix', 'Matrix / product limit', ('MATRIX',)),
    ('amount', 'Approved vs disbursed amount', ('AMTDIFF',)),
    ('cycle', 'Loan cycle', ('CYCLE',)),
    ('npl', 'Prior NPL / overdue exposure', ('NPL',)),
    ('lien', 'Lien letter issued to the bank', ('NOLETTER',)),
    ('dup', 'Duplicate / multiple active loans', ('DUP',)),
    ('docs', 'Mandatory documents complete', ()),
    ('fee', 'Fee / end-use', ()),
    ('evid', 'Disbursement evidence', ()),
]
PLAR_CHECK_VALUES = ['Verified', 'Issue Identified', 'Clarification Required', 'Not Applicable']
PLAR_REVIEW_STATUSES = ['Review In Progress', 'Compliant', 'Issue Identified', 'Clarification Required']
PLAR_OPTIONAL_CHECKS = ('fee', 'evid')


def plar_auto_checks(row):
    """Pre-fill from the automated rules: 'Issue Identified' where a rule fired, 'Verified' where it is clean."""
    fired = {e['code'] for e in row['exceptions']}
    checks = {}
    for key, _label, codes in PLAR_CHECKS:
        if not codes:
            checks[key] = ''
        else:
            checks[key] = 'Issue Identified' if fired.intersection(codes) else 'Verified'
    return checks


def get_plar_case(sample_id):
    rows = fetch_records("""SELECT s.*, r.mis_month, r.sample_locked FROM tbl_plar_sample s
                            JOIN tbl_plar_run r ON r.run_id = s.run_id WHERE s.sample_id = %s""",
                         is_print=False, params=(int(sample_id),))
    if not rows:
        return None
    s = rows[0]
    pop = get_plar_population_cached(s['mis_month'])
    loan = next((r for r in pop if r['loan_no'] == s['loan_no']), None)
    review = fetch_records("""SELECT rv.*, u.name AS reviewed_by_name FROM tbl_plar_review rv
                              LEFT JOIN tbl_users u ON u.user_id = rv.reviewed_by WHERE rv.sample_id = %s""",
                           is_print=False, params=(int(sample_id),))
    actions = fetch_records("""SELECT a.*, (SELECT COUNT(*) FROM tbl_plar_action_evidence e WHERE e.action_id = a.action_id) AS evidence_count
                               FROM tbl_plar_action a WHERE a.sample_id = %s ORDER BY a.action_id""",
                            is_print=False, params=(int(sample_id),))
    app = None
    history = []
    if s['pre_disb_temp_id']:
        app = fetch_records(f"""
            SELECT e.pre_disb_temp_id, e."Application_No" AS application_no, e."Borrower_Name" AS borrower_name,
                   e."Father_Husband_Name" AS father_husband_name, e."CNIC" AS cnic, e."Gender" AS gender,
                   e."LoanProductCode" AS product, e."Purpose_Of_Loan" AS purpose, e."Loan_Cycle" AS loan_cycle,
                   e."Tenor_Of_Month" AS tenor, e."Branch_Name" AS branch_name, e.status,
                   {_AMT.format(col='e."Requested_Loan_Amount"')} AS requested_amount,
                   {_AMT.format(col='e."Loan_Amount"')} AS approved_amount,
                   e.kft_approved_loan_limit AS matrix_limit, e."Credit_History_Ecib" AS ecib,
                   e."ApplicationDate" AS application_date, e.uploaded_date, e.reviewed_date, e.approved_date,
                   e.exec_approved_date, e.exec_approval_pending, e.email_status, e.notes,
                   ul.name AS uploaded_by, ur.name AS reviewed_by, ua.name AS approved_by, ux.name AS exec_approved_by,
                   e.reviewed_by AS reviewed_by_id, e.approved_by AS approved_by_id
            FROM tbl_pre_disbursement_temp e
            LEFT JOIN tbl_users ul ON ul.user_id = e.uploaded_by
            LEFT JOIN tbl_users ur ON ur.user_id = e.reviewed_by
            LEFT JOIN tbl_users ua ON ua.user_id = e.approved_by
            LEFT JOIN tbl_users ux ON ux.user_id = e.exec_approved_by
            WHERE e.pre_disb_temp_id = %s""", is_print=False, params=(s['pre_disb_temp_id'],))
        app = app[0] if app else None
        if app:
            history = [h for h in [
                ('Application uploaded', app['uploaded_date'], app['uploaded_by']),
                ('Reviewed', app['reviewed_date'], app['reviewed_by']),
                ('Approved', app['approved_date'], app['approved_by']),
                ('Executive approval', app['exec_approved_date'], app['exec_approved_by'])]
                if h[1] and getattr(h[1], 'year', 0) > 1901]
    if loan:
        history.append(('Disbursed by the bank', loan['booked_on'], None))
    return {'sample': s, 'loan': loan, 'app': app, 'history': history,
            'review': review[0] if review else None, 'actions': actions,
            'auto_checks': plar_auto_checks(loan) if loan else {}}


def plar_reviewer_conflict(case):
    """True when the signed-in user approved or reviewed this case in EGS (PLAR must be independent)."""
    app = case.get('app') or {}
    me = int(get_current_user_id())
    return me in [x for x in (app.get('approved_by_id'), app.get('reviewed_by_id')) if x is not None]


def validate_plar_review(payload, case):
    """Returns (clean dict, error text)."""
    checks = {}
    raw = payload.get('checks') or {}
    for key, _l, _c in PLAR_CHECKS:
        v = str(raw.get(key) or '').strip()
        if v and v not in PLAR_CHECK_VALUES:
            return None, 'Invalid value for a check.'
        checks[key] = v
    status = str(payload.get('status') or '')
    if status not in PLAR_REVIEW_STATUSES:
        return None, 'Choose an overall review status.'
    category = str(payload.get('category') or '').strip()
    severity = str(payload.get('severity') or '').strip()
    obs = str(payload.get('observation') or '').strip()
    if category and category not in PLAR_CATEGORIES:
        return None, 'Invalid issue category.'
    if severity and severity not in PLAR_SEVERITIES:
        return None, 'Invalid severity.'
    values = list(checks.values())
    if status == 'Compliant':
        if 'Issue Identified' in values:
            return None, 'A check shows "Issue Identified", so the case cannot be marked Compliant.'
        if 'Clarification Required' in values:
            return None, 'A check needs clarification, so the case cannot be marked Compliant.'
        if any(not checks[k] for k, _l, _c in PLAR_CHECKS if k not in PLAR_OPTIONAL_CHECKS):
            return None, 'Complete every required check before marking the case Compliant.'
        fired = [e for e in ((case['loan'] or {}).get('exceptions') or []) if e['severity'] in ('Critical', 'High')]
        if fired and not obs:
            return None, ('The automated rules found ' + ', '.join(e['label'] for e in fired) +
                          '. Explain in the observation why the case is still Compliant.')
    if status == 'Issue Identified':
        if not category or not severity or not obs:
            return None, 'Issue Identified needs a category, a severity and an observation.'
        if 'Issue Identified' not in values:
            return None, 'Mark at least one check as "Issue Identified".'
    if status == 'Clarification Required' and not obs:
        return None, 'Say what clarification is needed in the observation.'
    return {'checks': checks, 'status': status, 'category': category, 'severity': severity, 'observation': obs}, None


def save_plar_review(sample_id, clean, case, owner_name, owner_user_id, due_date):
    """Insert/update the review; open a corrective action the first time a finding is recorded."""
    me = int(get_current_user_id())
    old = case['review']
    execute_command("""
        INSERT INTO tbl_plar_review (sample_id, checks, overall_status, issue_category, issue_severity, observation,
                                     reviewed_by, reviewed_date, modified_date)
        VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (sample_id) DO UPDATE SET checks = EXCLUDED.checks, overall_status = EXCLUDED.overall_status,
            issue_category = EXCLUDED.issue_category, issue_severity = EXCLUDED.issue_severity,
            observation = EXCLUDED.observation, reviewed_by = EXCLUDED.reviewed_by,
            modified_date = CURRENT_TIMESTAMP""",
                    return_id=False,
                    params=(int(sample_id), json.dumps(clean['checks']), clean['status'], clean['category'] or None,
                            clean['severity'] or None, clean['observation'] or None, me))
    plar_audit('Review', sample_id, 'Overall status', old['overall_status'] if old else '(new)', clean['status'])
    review = fetch_records("SELECT review_id FROM tbl_plar_review WHERE sample_id = %s", is_print=False,
                           params=(int(sample_id),))[0]
    created = None
    if clean['status'] in ('Issue Identified', 'Clarification Required') and not case['actions']:
        s = case['sample']
        created = fetch_records("""
            INSERT INTO tbl_plar_action (review_id, sample_id, loan_no, region_name, branch_name, category, severity,
                                         action_text, owner_name, owner_user_id, due_date, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING action_id""",
                                is_print=False,
                                params=(review['review_id'], int(sample_id), s['loan_no'], s['region_name'], s['branch_name'],
                                        clean['category'] or 'Other', clean['severity'] or 'Medium', clean['observation'],
                                        owner_name, owner_user_id, due_date, me))
        if created:
            plar_audit('Action', created[0]['action_id'], 'Created', None, f'{owner_name}, due {due_date}')
    return created[0]['action_id'] if created else None


# ---------------------------------------------------------------------------------------------
# Corrective actions: owners, deadlines, evidence-before-closure, reminders, escalation
# ---------------------------------------------------------------------------------------------
PLAR_ACTION_STATUSES = ['Open', 'In Progress', 'Resolved', 'Closed']
PLAR_ESCALATE_SEVERITIES = ('High', 'Critical')
PLAR_EVIDENCE_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls', 'docx', 'doc', 'csv', 'txt', 'msg', 'eml'}
PLAR_EVIDENCE_MAX_BYTES = 10 * 1024 * 1024


def get_plar_actions():
    rows = fetch_records("""
        SELECT a.action_id, a.sample_id, a.loan_no, a.region_name, a.branch_name, a.category, a.severity, a.action_text,
               a.owner_name, a.owner_user_id, a.due_date, a.status, a.escalated, a.escalated_date, a.last_reminder,
               a.closed_date, a.created_date, uc.name AS created_by_name, uo.name AS owner_user_name,
               (a.status NOT IN ('Resolved', 'Closed') AND a.due_date < CURRENT_DATE) AS overdue,
               GREATEST(CURRENT_DATE - a.due_date, 0) AS days_overdue
        FROM tbl_plar_action a
        LEFT JOIN tbl_users uc ON uc.user_id = a.created_by
        LEFT JOIN tbl_users uo ON uo.user_id = a.owner_user_id
        ORDER BY (a.status IN ('Resolved', 'Closed')), a.due_date, a.action_id
    """, is_print=False)
    evidence = fetch_records("SELECT evidence_id, action_id, file_name, uploaded_date FROM tbl_plar_action_evidence ORDER BY evidence_id",
                             is_print=False)
    by_action = {}
    for e in evidence:
        by_action.setdefault(e['action_id'], []).append(e)
    for r in rows:
        r['evidence'] = by_action.get(r['action_id'], [])
    return rows


def update_plar_action_status(action_id, new_status):
    """Returns an error string or None. Resolved / Closed need uploaded evidence."""
    if new_status not in PLAR_ACTION_STATUSES:
        return 'Invalid status.'
    rows = fetch_records("""SELECT a.status, (SELECT COUNT(*) FROM tbl_plar_action_evidence e WHERE e.action_id = a.action_id) AS ev
                            FROM tbl_plar_action a WHERE a.action_id = %s""", is_print=False, params=(int(action_id),))
    if not rows:
        return 'Action not found.'
    old, evidence = rows[0]['status'], int(rows[0]['ev'])
    if new_status in ('Resolved', 'Closed') and evidence == 0:
        return 'Upload evidence of resolution before marking the action Resolved or Closed.'
    execute_command("""UPDATE tbl_plar_action SET status = %s,
                           closed_date = CASE WHEN %s IN ('Resolved', 'Closed') THEN CURRENT_TIMESTAMP ELSE NULL END
                       WHERE action_id = %s""", return_id=False, params=(new_status, new_status, int(action_id)))
    plar_audit('Action', action_id, 'Status', old, new_status)
    return None


def add_plar_evidence(action_id, file_name, file_path):
    execute_command("""INSERT INTO tbl_plar_action_evidence (action_id, file_name, file_path, uploaded_by)
                       VALUES (%s, %s, %s, %s)""", return_id=False,
                    params=(int(action_id), file_name, file_path, int(get_current_user_id())))
    plar_audit('Action', action_id, 'Evidence uploaded', None, file_name)


def get_plar_evidence_file(evidence_id):
    rows = fetch_records("SELECT file_name, file_path FROM tbl_plar_action_evidence WHERE evidence_id = %s",
                         is_print=False, params=(int(evidence_id),))
    return rows[0] if rows else None


def _plar_management_emails():
    rows = fetch_records("SELECT email FROM tbl_users WHERE active = 1 AND rights IN (3, 5) AND COALESCE(email, '') <> ''",
                         is_print=False)
    return sorted({r['email'] for r in rows})


def _plar_table_html(title, intro, actions):
    body = ''.join(
        f"<tr><td>{a['loan_no'] or ''}</td><td>{a['region_name'] or ''} / {a['branch_name'] or ''}</td><td>{a['category']}</td>"
        f"<td>{a['severity']}</td><td>{a['owner_name'] or ''}</td><td>{a['due_date']:%d %b %Y}</td>"
        f"<td>{a['days_overdue']}</td></tr>" for a in actions)
    return (f"<p>{intro}</p><table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;font-family:Arial;font-size:13px'>"
            "<tr style='background:#eef1ef'><th>Loan</th><th>Region / branch</th><th>Category</th><th>Severity</th>"
            f"<th>Owner</th><th>Deadline</th><th>Days overdue</th></tr>{body}</table><p>{title}</p>")


def escalate_plar_actions(send=True):
    """High / Critical actions that are overdue and not yet escalated go to KFT management. Returns (count, emails_sent, recipients)."""
    todo = [a for a in get_plar_actions()
            if a['overdue'] and a['severity'] in PLAR_ESCALATE_SEVERITIES and not a['escalated']]
    if not todo:
        return 0, False, []
    recipients = _plar_management_emails()
    sent = False
    if send and recipients:
        from Model_Email import send_email
        html = _plar_table_html('Open them under Risk Management &rarr; Assurance Review (PLAR) &rarr; Corrective actions.',
                                f'{len(todo)} high-risk PLAR corrective action(s) are past their deadline and need management attention:', todo)
        sent = send_email('PLAR escalation: overdue high-risk corrective actions', recipients, '', html_message=html)
    for a in todo:
        execute_command("UPDATE tbl_plar_action SET escalated = 1, escalated_date = CURRENT_TIMESTAMP WHERE action_id = %s",
                        return_id=False, params=(a['action_id'],))
        plar_audit('Action', a['action_id'], 'Escalated to management', None, ', '.join(recipients) or 'no recipients')
    return len(todo), sent, recipients


def remind_plar_actions(send=True):
    """Email each EGS user who owns overdue or soon-due actions (once per day). Returns (reminded actions, emails sent, skipped without an EGS user)."""
    rows = fetch_records("""
        SELECT a.action_id, a.loan_no, a.region_name, a.branch_name, a.category, a.severity, a.owner_name, a.due_date,
               a.owner_user_id, u.email, GREATEST(CURRENT_DATE - a.due_date, 0) AS days_overdue
        FROM tbl_plar_action a LEFT JOIN tbl_users u ON u.user_id = a.owner_user_id
        WHERE a.status NOT IN ('Resolved', 'Closed') AND a.due_date <= CURRENT_DATE + 3
          AND (a.last_reminder IS NULL OR a.last_reminder < CURRENT_TIMESTAMP - INTERVAL '23 hours')
        ORDER BY a.due_date""", is_print=False)
    no_user = [r for r in rows if not r['owner_user_id'] or not r['email']]
    by_user = {}
    for r in rows:
        if r['owner_user_id'] and r['email']:
            by_user.setdefault(r['email'], []).append(r)
    emails = 0
    if send:
        from Model_Email import send_email
        for email_addr, acts in by_user.items():
            html = _plar_table_html('Please resolve each item and upload evidence under Corrective actions.',
                                    'These PLAR corrective actions assigned to you are due soon or overdue:', acts)
            if send_email('PLAR reminder: corrective actions due', [email_addr], '', html_message=html):
                emails += 1
                for a in acts:
                    execute_command("UPDATE tbl_plar_action SET last_reminder = CURRENT_TIMESTAMP WHERE action_id = %s",
                                    return_id=False, params=(a['action_id'],))
                    plar_audit('Action', a['action_id'], 'Reminder emailed', None, email_addr)
    return sum(len(v) for v in by_user.values()), emails, len(no_user)


def get_plar_audit(limit=1000):
    return fetch_records("""SELECT audit_id, created_date, user_name, entity, entity_id, action, old_value, new_value
                            FROM tbl_plar_audit ORDER BY audit_id DESC LIMIT %s""", is_print=False, params=(int(limit),))


# ---------------------------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------------------------
_TREND_CACHE = {}


def _plar_month_stats(month_start):
    """Auto-exception counts for a month, cached for 10 minutes (each month is one population query)."""
    hit = _TREND_CACHE.get(month_start)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    rows = get_plar_population(month_start)
    stats = {'loans': len(rows), 'with_exceptions': sum(1 for r in rows if r['exceptions'])}
    _TREND_CACHE[month_start] = (time.time(), stats)
    return stats


def get_plar_dashboard(month_start):
    month_end = plar_next_month(month_start)
    rows = get_plar_population_cached(month_start)
    not_disbursed = get_plar_approved_not_disbursed(month_start, rows)
    summary = plar_summary(rows, not_disbursed)
    case_records, _pop = get_plar_exception_records(month_start)
    cases = plar_case_summary(case_records)

    approved = fetch_records(f"""
        SELECT COUNT(*) AS n, COALESCE(SUM({_AMT.format(col='e."Loan_Amount"')}), 0) AS amount
        FROM tbl_pre_disbursement_temp e
        WHERE e.status IN %s AND e.approved_date::date >= %s AND e.approved_date::date < %s""",
                             is_print=False, params=(PLAR_APPROVED_STATUSES, month_start, month_end))[0]
    outstanding = fetch_records("""
        SELECT COALESCE(SUM(principal_outstanding), 0) AS amount, COUNT(DISTINCT loan_no) AS loans
        FROM tbl_post_disbursement
        WHERE mis_date = (SELECT MAX(mis_date) FROM tbl_post_disbursement WHERE mis_date < %s)
          AND product_code = ANY(%s) AND (loan_closed_on IS NULL OR loan_closed_on < DATE '1901-01-01')""",
                                is_print=False, params=(month_end + timedelta(days=1), PLAR_PRODUCT_CODES))[0]

    def tally(key_fn, sev=False):
        out = {}
        for r in rows:
            for e in r['exceptions']:
                k = key_fn(r, e) or 'Unmapped'
                out[k] = out.get(k, 0) + 1
        return out
    by_region = tally(lambda r, e: r['region'])
    by_branch = tally(lambda r, e: r['mis_branch_name'])
    by_product = tally(lambda r, e: r['product_code'])
    by_severity = tally(lambda r, e: e['severity'])
    by_type = tally(lambda r, e: e['label'])

    run = get_plar_run(month_start)
    sample = get_plar_sample(run) if run and run['sample_locked'] else []
    status_count = {}
    for s in sample:
        k = s['overall_status'] or 'Not reviewed'
        status_count[k] = status_count.get(k, 0) + 1
    reviewed = sum(v for k, v in status_count.items() if k not in ('Not reviewed', 'Review In Progress'))

    actions = get_plar_actions()
    open_actions = [a for a in actions if a['status'] not in ('Resolved', 'Closed')]
    recurring = {}
    for a in actions:
        key = (a['branch_name'] or '-', a['category'] or '-')
        recurring[key] = recurring.get(key, 0) + 1
    recurring_rows = sorted(([k[0], k[1], v] for k, v in recurring.items() if v > 1), key=lambda x: -x[2])[:15]
    findings_by_reviewer = fetch_records("""
        SELECT COALESCE(u.name, '-') AS reviewer, COUNT(*) AS reviews,
               COUNT(*) FILTER (WHERE rv.overall_status = 'Issue Identified') AS issues
        FROM tbl_plar_review rv LEFT JOIN tbl_users u ON u.user_id = rv.reviewed_by
        GROUP BY 1 ORDER BY 2 DESC""", is_print=False)

    trend = []
    runs = {r['mis_month']: r for r in fetch_records("SELECT * FROM tbl_plar_run", is_print=False)}
    for i in range(5, -1, -1):
        m = month_start
        for _ in range(i):
            m = date(m.year - (m.month == 1), (m.month - 2) % 12 + 1, 1)
        st = _plar_month_stats(m)
        rn = runs.get(m)
        sm = fetch_records("""SELECT COUNT(*) AS sampled, COUNT(*) FILTER (WHERE rv.overall_status = 'Issue Identified') AS issues
                              FROM tbl_plar_sample s LEFT JOIN tbl_plar_review rv ON rv.sample_id = s.sample_id
                              WHERE s.run_id = %s""", is_print=False, params=(rn['run_id'],))[0] if rn else {'sampled': 0, 'issues': 0}
        trend.append({'month': m.strftime('%Y-%m'), 'disbursed': st['loans'], 'auto_exceptions': st['with_exceptions'],
                      'sampled': sm['sampled'], 'issues': sm['issues']})

    return {
        'summary': summary, 'cases': cases,
        'approved_count': approved['n'], 'approved_amount': approved['amount'],
        'outstanding_amount': outstanding['amount'], 'outstanding_loans': outstanding['loans'],
        'by_region': by_region, 'by_branch': dict(sorted(by_branch.items(), key=lambda x: -x[1])[:10]),
        'by_product': by_product, 'by_severity': by_severity, 'by_type': by_type,
        'sample': {'sampled': len(sample), 'reviewed': reviewed, 'status': status_count,
                   'pct_of_disbursed': round(100 * len(sample) / len(rows), 1) if rows else 0},
        'actions': {'open': len(open_actions), 'overdue': sum(1 for a in open_actions if a['overdue']),
                    'closed': len(actions) - len(open_actions),
                    'escalated': sum(1 for a in actions if a['escalated']),
                    'by_severity': {s: sum(1 for a in open_actions if a['severity'] == s) for s in PLAR_SEVERITIES}},
        'recurring': recurring_rows, 'reviewers': findings_by_reviewer, 'trend': trend}


# ---------------------------------------------------------------------------------------------
# Reconciliation exception cases: every automated exception is Pending until a PLAR reviewer resolves
# it with a note (and an optional file). Only decisions are stored; the exceptions themselves are
# recomputed from the bank MIS and EGS each time.
# ---------------------------------------------------------------------------------------------
PLAR_CASE_EVIDENCE_EXTENSIONS = PLAR_EVIDENCE_EXTENSIONS if 'PLAR_EVIDENCE_EXTENSIONS' in globals() else {'pdf', 'png', 'jpg', 'jpeg'}


def plar_case_key(code, loan_no, pre_disb_temp_id):
    """Loan exceptions are keyed by loan number; pending-lien rows have no loan yet, so use the application."""
    return loan_no if loan_no else f'APP{pre_disb_temp_id}'


def get_plar_exception_records(month_start):
    """All automated exceptions of the month as flat rows, each with its Pending / Resolved state."""
    rows = get_plar_population_cached(month_start)
    not_disbursed = get_plar_approved_not_disbursed(month_start, rows)
    today = date.today()
    records = []
    for r in rows:
        days = (today - r['booked_on']).days if r['booked_on'] else None
        for e in r['exceptions']:
            records.append({'code': e['code'], 'exception': e['label'], 'severity': e['severity'], 'detail': e['detail'],
                            'loan_no': r['loan_no'], 'pre_disb_temp_id': r['pre_disb_temp_id'],
                            'borrower': r['borrower_name'] or r['loan_title'], 'cnic': r['cnic'], 'region': r['region'],
                            'branch': r['mis_branch_name'], 'product': r['product_code'],
                            'disbursed': r['disbursed_amount'], 'approved': r['approved_amount'],
                            'booked_on': r['booked_on'], 'application_no': r['application_no'],
                            'approved_by': r['approved_by'], 'days_open': days})
    for r in not_disbursed:
        if not r['conclusive']:
            continue                      # still waiting for the next month's MIS: informational only
        waiting = (today - r['approved_date'].date()).days if r['approved_date'] else None
        records.append({'code': 'LIENPEND', 'exception': PLAR_EXCEPTIONS['LIENPEND'][0],
                        'severity': PLAR_EXCEPTIONS['LIENPEND'][1],
                        'detail': f"Lien letter emailed; approved on {r['approved_date']:%d %b %Y}, not in the bank MIS of the following month",
                        'loan_no': '', 'pre_disb_temp_id': r['pre_disb_temp_id'], 'borrower': r['borrower_name'],
                        'cnic': r['cnic'], 'region': r['region'], 'branch': r['branch_name'], 'product': r['product'],
                        'disbursed': None, 'approved': r['approved_amount'], 'booked_on': None,
                        'application_no': r['application_no'], 'approved_by': None, 'days_open': waiting})
    states = get_plar_case_states(month_start)
    for rec in records:
        rec['case_key'] = plar_case_key(rec['code'], rec['loan_no'], rec['pre_disb_temp_id'])
        st = states.get((rec['code'], rec['case_key']))
        rec['case_status'] = st['status'] if st else 'Pending'
        rec['resolution_note'] = st['resolution_note'] if st else None
        rec['resolved_by'] = st['resolved_by_name'] if st else None
        rec['resolved_date'] = st['resolved_date'] if st else None
        rec['evidence'] = st['evidence'] if st else []
    return records, rows


def get_plar_case_states(month_start):
    cases = fetch_records("""
        SELECT c.case_id, c.exception_code, c.case_key, c.status, c.resolution_note, c.resolved_date, u.name AS resolved_by_name
        FROM tbl_plar_exception_case c LEFT JOIN tbl_users u ON u.user_id = c.resolved_by
        WHERE c.mis_month = %s""", is_print=False, params=(month_start,))
    evidence = fetch_records("""
        SELECT e.evidence_id, e.case_id, e.file_name FROM tbl_plar_exception_evidence e
        JOIN tbl_plar_exception_case c ON c.case_id = e.case_id WHERE c.mis_month = %s ORDER BY e.evidence_id""",
                             is_print=False, params=(month_start,))
    by_case = {}
    for e in evidence:
        by_case.setdefault(e['case_id'], []).append(e)
    return {(c['exception_code'], c['case_key']): dict(c, evidence=by_case.get(c['case_id'], [])) for c in cases}


def set_plar_case_state(month_start, code, loan_no, pre_disb_temp_id, status, note):
    """Resolve (note required) or reopen an exception. Returns (case_id, error)."""
    if code not in PLAR_EXCEPTIONS:
        return None, 'Unknown exception type.'
    if status not in ('Resolved', 'Pending'):
        return None, 'Invalid status.'
    note = str(note or '').strip()
    if status == 'Resolved' and len(note) < 5:
        return None, 'Write a short note saying how the exception was resolved.'
    key = plar_case_key(code, loan_no, pre_disb_temp_id)
    records, _rows = get_plar_exception_records(month_start)
    if not any(r['code'] == code and r['case_key'] == key for r in records):
        return None, 'This exception is no longer in the month\'s report.'
    old = get_plar_case_states(month_start).get((code, key))
    saved = fetch_records("""
        INSERT INTO tbl_plar_exception_case (mis_month, exception_code, case_key, loan_no, pre_disb_temp_id, status,
                                             resolution_note, resolved_by, resolved_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s = 'Resolved' THEN CURRENT_TIMESTAMP ELSE NULL END)
        ON CONFLICT (mis_month, exception_code, case_key) DO UPDATE SET status = EXCLUDED.status,
            resolution_note = EXCLUDED.resolution_note, resolved_by = EXCLUDED.resolved_by,
            resolved_date = EXCLUDED.resolved_date
        RETURNING case_id""", is_print=False,
                          params=(month_start, code, key, loan_no or None, pre_disb_temp_id or None, status,
                                  note or None, int(get_current_user_id()), status))
    if not saved:
        return None, 'Could not save.'
    plar_audit('Exception case', f'{month_start:%Y-%m} {code} {key}', 'Status',
               old['status'] if old else 'Pending', status + (f' - {note[:120]}' if note else ''))
    return saved[0]['case_id'], None


def add_plar_case_evidence(case_id, file_name, file_path):
    execute_command("""INSERT INTO tbl_plar_exception_evidence (case_id, file_name, file_path, uploaded_by)
                       VALUES (%s, %s, %s, %s)""", return_id=False,
                    params=(int(case_id), file_name, file_path, int(get_current_user_id())))
    plar_audit('Exception case', case_id, 'Evidence uploaded', None, file_name)


def get_plar_case_evidence_file(evidence_id):
    rows = fetch_records("SELECT file_name, file_path FROM tbl_plar_exception_evidence WHERE evidence_id = %s",
                         is_print=False, params=(int(evidence_id),))
    return rows[0] if rows else None


def plar_case_summary(records):
    """Pending / resolved counts for the dashboard, by exception type and by age of the pending ones."""
    pending = [r for r in records if r['case_status'] != 'Resolved']
    resolved = [r for r in records if r['case_status'] == 'Resolved']
    by_type = {}
    for r in records:
        t = by_type.setdefault(r['exception'], {'pending': 0, 'resolved': 0})
        t['resolved' if r['case_status'] == 'Resolved' else 'pending'] += 1
    ageing = {'0-30 days': 0, '31-60 days': 0, 'Over 60 days': 0}
    for r in pending:
        d = r['days_open'] or 0
        ageing['0-30 days' if d <= 30 else ('31-60 days' if d <= 60 else 'Over 60 days')] += 1
    return {'total': len(records), 'pending': len(pending), 'resolved': len(resolved),
            'pending_critical': sum(1 for r in pending if r['severity'] == 'Critical'),
            'by_type': by_type, 'ageing': ageing}
