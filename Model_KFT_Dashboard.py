from imports import *


# Product code -> sector category (as defined in "Updates in KF MIS Process")
ENTERPRISE_PRODUCT_CODES = {'WFP1', 'WFP3', 'WFP4', 'MEL1', 'EFP1', 'EFP2', 'EFP3', 'RZP1', 'GLP1', 'GLP2', 'AFP2', 'KFJ7'}
EDUCATION_PRODUCT_CODES = {'STD1', 'SFP1', 'SFP2', 'KFJ1', 'KFJ2', 'KFJ4'}

CATEGORY_ENTERPRISE = 0
CATEGORY_EDUCATION = 1
CATEGORY_OTHER = 2

UNASSIGNED_REGION = 'Unassigned'

_KFT_CACHE = {'data': None, 'expires_at': None}
_KFT_CACHE_TTL = timedelta(minutes=10)


def get_product_category(product_code):
    code = (product_code or '').strip().upper()
    if code in ENTERPRISE_PRODUCT_CODES:
        return CATEGORY_ENTERPRISE
    if code in EDUCATION_PRODUCT_CODES:
        return CATEGORY_EDUCATION
    return CATEGORY_OTHER


def _to_float(value):
    return float(value) if value is not None else 0.0


def _get_branch_regions():
    query = """
        SELECT
            b.branch_code,
            b.branch_name,
            ncd.national_council_distribution_name AS region
        FROM tbl_branches b
        LEFT JOIN tbl_national_council_distribution ncd
            ON b.national_council_distribution = ncd.national_council_distribution_id
    """
    return fetch_records(query)


def _get_latest_snapshot_loans():
    # One row per loan from the latest monthly MIS snapshot (the snapshot is cumulative, closed loans included)
    query = """
        SELECT DISTINCT ON (pd.loan_no)
            pd.mis_date,
            pd.loan_no,
            pd.cnic,
            pd.branch_code,
            pd.branch_name,
            pd.sector_code,
            pd.gender,
            pd.mobile_no,
            pd.loan_title,
            pd.product_code,
            pd.booked_on,
            pd.disbursed_amount,
            pd.principal_outstanding,
            pd.overdue_days,
            pd.loan_status
        FROM tbl_post_disbursement pd
        WHERE DATE_TRUNC('month', pd.mis_date) = (
            SELECT DATE_TRUNC('month', MAX(mis_date)) FROM tbl_post_disbursement
        )
        ORDER BY pd.loan_no, pd.id
    """
    return fetch_records(query, is_print=False)


def _get_arrears_trend_rows():
    # Arrears (OD_Days >= 30) outstanding principal per snapshot month for the last 12 months
    query = """
        SELECT
            TO_CHAR(DATE_TRUNC('month', t.mis_date), 'YYYY-MM') AS month,
            t.branch_code,
            t.product_code,
            SUM(t.principal_outstanding) AS arrears_amount
        FROM (
            SELECT DISTINCT ON (DATE_TRUNC('month', mis_date), loan_no)
                mis_date, loan_no, branch_code, product_code, principal_outstanding, overdue_days
            FROM tbl_post_disbursement
            WHERE mis_date >= DATE_TRUNC('month', (SELECT MAX(mis_date) FROM tbl_post_disbursement)) - INTERVAL '11 months'
            ORDER BY DATE_TRUNC('month', mis_date), loan_no, id
        ) t
        WHERE t.overdue_days >= 30
        GROUP BY 1, 2, 3
        ORDER BY 1
    """
    return fetch_records(query, is_print=False)


def build_kft_dashboard_data():
    branch_rows = _get_branch_regions()
    loan_rows = _get_latest_snapshot_loans()
    trend_rows = _get_arrears_trend_rows()

    if not loan_rows:
        return None

    # Branch lookup: tbl_branches is the source of truth for branch -> region (National Council Distribution)
    known_branches = {
        (row['branch_code'] or '').strip(): {
            'name': (row['branch_name'] or '').strip() or (row['branch_code'] or '').strip(),
            'region': row['region'] or UNASSIGNED_REGION,
        }
        for row in branch_rows
    }

    branches = []
    branch_index = {}

    def get_branch_idx(branch_code, fallback_name):
        code = (branch_code or '').strip()
        if code not in branch_index:
            info = known_branches.get(code) or {
                'name': (fallback_name or code).replace(' BRANCH', '').strip(),
                'region': UNASSIGNED_REGION,
            }
            branch_index[code] = len(branches)
            branches.append({'code': code, 'name': info['name'], 'region': info['region']})
        return branch_index[code]

    beneficiary_index = {}
    loans = []
    arrears_listing = []
    mis_date = max(row['mis_date'] for row in loan_rows)

    for row in loan_rows:
        booked_on = row['booked_on']
        if not booked_on:
            continue

        branch_idx = get_branch_idx(row['branch_code'], row['branch_name'])
        category = get_product_category(row['product_code'])
        cnic = (row['cnic'] or '').strip() or row['loan_no']
        beneficiary_id = beneficiary_index.setdefault(cnic, len(beneficiary_index))
        outstanding = _to_float(row['principal_outstanding'])
        overdue_days = int(row['overdue_days'] or 0)

        # [branch, category, beneficiary, booked yyyymm, disbursed, outstanding, overdue days]
        loans.append([
            branch_idx,
            category,
            beneficiary_id,
            booked_on.year * 100 + booked_on.month,
            round(_to_float(row['disbursed_amount']), 2),
            round(outstanding, 2),
            overdue_days,
        ])

        if overdue_days >= 30:
            arrears_listing.append({
                'b': branch_idx,
                'c': category,
                'sector_code': row['sector_code'] or '',
                'branch_name': row['branch_name'] or '',
                'gender': row['gender'] or '',
                'mobile_no': row['mobile_no'] or '',
                'loan_title': row['loan_title'] or '',
                'loan_no': row['loan_no'] or '',
                'product_code': row['product_code'] or '',
                'booked_on': booked_on.strftime('%d-%b-%Y'),
                'disbursed_amount': round(_to_float(row['disbursed_amount']), 2),
                'loan_status': row['loan_status'] or '',
                'overdue_days': overdue_days,
                'principal_outstanding': round(outstanding, 2),
            })

    arrears_listing.sort(key=lambda r: -r['overdue_days'])

    trend_months = sorted({row['month'] for row in trend_rows})
    trend_month_index = {m: i for i, m in enumerate(trend_months)}
    trend = [
        [
            trend_month_index[row['month']],
            get_branch_idx(row['branch_code'], row['branch_code']),
            get_product_category(row['product_code']),
            round(_to_float(row['arrears_amount']), 2),
        ]
        for row in trend_rows
    ]

    regions = sorted({b['region'] for b in branches if b['region'] != UNASSIGNED_REGION})
    if any(b['region'] == UNASSIGNED_REGION for b in branches):
        regions.append(UNASSIGNED_REGION)

    return {
        'meta': {
            'misDate': mis_date.strftime('%Y-%m-%d'),
            'reportYear': mis_date.year,
            'reportMonth': mis_date.month,
            'generatedAt': datetime.now().strftime('%d-%b-%Y %H:%M'),
        },
        'regions': regions,
        'branches': branches,
        'loans': loans,
        'arrearsListing': arrears_listing,
        'arrearsTrend': {'months': trend_months, 'rows': trend},
    }


def get_kft_dashboard_data(force_refresh=False):
    now = datetime.now()
    if not force_refresh and _KFT_CACHE['data'] is not None and _KFT_CACHE['expires_at'] > now:
        return _KFT_CACHE['data']

    data = build_kft_dashboard_data()
    if data is not None:
        _KFT_CACHE['data'] = data
        _KFT_CACHE['expires_at'] = now + _KFT_CACHE_TTL
    return data
