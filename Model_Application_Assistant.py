from imports import *

# Application Tracker: gathers everything known about one application for the chat-style lookup screen.
# All queries here are parameterized (%s) - never format user input into the SQL.

APPLICATION_STATUS_LABELS = {
    '1': 'Under Review',
    '2': 'Agreed',
    '3': 'Disagreed',
    '5': 'Recommended For Agreement',
    '6': 'Recommended For Disagreement',
    '7': 'Recommended For Agreement (With Exception)',
    '8': 'Recommended For Disagreement (With Exception)',
    '9': 'Agreed (With Exception)',
    '10': 'Disagreed (With Exception)'
}


NAME_SEARCH_LIMIT = 20


def _branch_scope_sql():
    # Reviewers / approvers only see applications of their assigned branches (same rule as the
    # Loan Application Analysis screen); everyone else who can open the screen sees all branches.
    # Executives are scoped to their assigned branches like approvers.
    if get_current_user_role() in ['1', '2', '5']:
        return """
            AND EXISTS (
                SELECT 1
                FROM tbl_branches b
                INNER JOIN tbl_users u ON b.role = ANY (u.assigned_branch) AND u.active = '1'
                WHERE pdt."Branch_Name" LIKE CONCAT('%%', b.branch_code, '%%') AND b.live_branch = '1'
                  AND u.user_id = %s
            )
        """, (str(get_current_user_id()),)
    return '', ()


_APPLICATION_SELECT = f"""
        SELECT
            pdt."pre_disb_temp_id",
            pdt."Application_No",
            pdt."Borrower_Name",
            pdt."CNIC",
            pdt."Branch_Name",
            pdt."LoanProductCode",
            pdt."Loan_Amount",
            pdt."Requested_Loan_Amount",
            pdt.KFT_Approved_Loan_Limit,
            pdt."ApplicationDate",
            pdt.status,
            pdt.email_status,
            pdt.notes,
            u3.name AS reviewed_by, pdt.reviewed_date,
            u2.name AS approved_by, pdt.approved_date,
            u4.name AS rejected_by, pdt.rejected_date,
            u5.name AS exec_approved_by, pdt.exec_approved_date,
            pdt.exec_approval_pending,
            {ALLOW_EXCEPTIONAL_APPROVAL_SQL} AS allow_exceptional_approval
        FROM tbl_pre_disbursement_temp pdt
        LEFT JOIN tbl_users u2 ON u2.user_id = pdt.approved_by
        LEFT JOIN tbl_users u3 ON u3.user_id = pdt.reviewed_by
        LEFT JOIN tbl_users u4 ON u4.user_id = pdt.rejected_by
        LEFT JOIN tbl_users u5 ON u5.user_id = pdt.exec_approved_by
"""


def find_applications(search_text):
    """Match by exact Application No or CNIC (with or without dashes), scoped to the user's branches."""
    search_text = str(search_text).strip()
    scope_sql, scope_params = _branch_scope_sql()
    query = f"""
        {_APPLICATION_SELECT}
        WHERE (
            CAST(pdt."Application_No" AS VARCHAR) = %s
            OR pdt."CNIC" IN %s
        )
        {scope_sql}
        ORDER BY pdt."ApplicationDate" DESC
        LIMIT 10
    """
    return fetch_records(query, params=(search_text, cnic_variants(search_text)) + scope_params)


def find_applications_by_name(name):
    """Case-insensitive partial match on Borrower Name; each word must appear in order
    (so 'ali habib' also matches 'ALI  HABIB KHAN'). Scoped to the user's branches."""
    words = str(name).split()
    pattern = '%' + '%'.join(words) + '%'
    scope_sql, scope_params = _branch_scope_sql()
    query = f"""
        {_APPLICATION_SELECT}
        WHERE pdt."Borrower_Name" ILIKE %s
        {scope_sql}
        ORDER BY pdt."ApplicationDate" DESC
        LIMIT {NAME_SEARCH_LIMIT}
    """
    return fetch_records(query, params=(pattern,) + scope_params)


def get_application_images_info(application_no):
    query = """
        SELECT pd_ai_id, created_date
        FROM tbl_pre_disbursement_application_images
        WHERE CAST(application_no AS VARCHAR) = %s
        ORDER BY created_date DESC
    """
    return fetch_records(query, params=(str(application_no),))


def cnic_variants(cnic):
    # The same CNIC can be stored with or without dashes; compare the column directly against both
    # spellings (no function on the column) so the lookup can use an index.
    cnic = str(cnic).strip()
    digits = re.sub(r'\D', '', cnic)
    variants = {cnic, digits}
    if len(digits) == 13:
        variants.add(f"{digits[:5]}-{digits[5:12]}-{digits[12:]}")
    return tuple(v for v in variants if v)
