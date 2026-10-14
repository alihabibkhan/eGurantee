from imports import *


# def get_all_pre_disbursement_temp():
#     sql_part_temp = ''
#
#     if get_current_user_role() in ['1', '2']:
#         sql_part_temp = f"""
#             INNER JOIN tbl_branches b on pdt."Branch_Name" LIKE CONCAT('%', b."branch_code", '%') AND b."live_branch" = '1'
#             INNER JOIN tbl_users u on u.assigned_branch = b.role and u."active" = '1'
#             LEFT JOIN tbl_branch_role tbr on u.assigned_branch = tbr.branch_role_id
#             LEFT JOIN tbl_users u1 ON u1."user_id" = pdt."uploaded_by"
#             LEFT JOIN tbl_users u2 ON u2."user_id" = pdt."approved_by"
#             LEFT JOIN tbl_users u3 ON u3."user_id" = pdt."reviewed_by"
#             LEFT JOIN tbl_users u4 ON u4."user_id" = pdt."rejected_by"
#             LEFT JOIN tbl_bank_details bd ON bd.bank_id = b.bank_id and bd.status = '1'
#             WHERE pdt.status in {("('1', '5', '6')" if get_current_user_role() == '1' else "('2', '3', '5', '6')")}
#         """
#     else:
#         sql_part_temp = """
#             LEFT JOIN tbl_branches b on pdt."Branch_Name" LIKE CONCAT('%', b."branch_code", '%') AND b."live_branch" = '1'
#             LEFT JOIN tbl_branch_role tbr on b.role = tbr.branch_role_id
#             LEFT JOIN tbl_users u1 ON u1."user_id" = pdt."uploaded_by"
#             LEFT JOIN tbl_users u2 ON u2."user_id" = pdt."approved_by"
#             LEFT JOIN tbl_users u3 ON u3."user_id" = pdt."reviewed_by"
#             LEFT JOIN tbl_users u4 ON u4."user_id" = pdt."rejected_by"
#             LEFT JOIN tbl_bank_details bd ON bd.bank_id = b.bank_id and bd.status = '1'
#         """
#
#     query = f"""
#         SELECT
#             {("DISTINCT" if get_current_user_role() in ['1', '2'] else "")}
#             pdt."pre_disb_temp_id",
#             pdt."Application_No",
#             pdt."Annual_Business_Incomes",
#             pdt."Annual_Disposable_Income",
#             pdt."Annual_Expenses",
#             pdt."ApplicationDate",
#             pdt."Bcc_Approval_Date",
#             pdt."Borrower_Name",
#             pdt."Branch_Area",
#             pdt."Branch_Name",
#             pdt."Business_Expense_Description",
#             pdt."Business_Experiense_Since",
#             pdt."Business_Premises",
#             pdt."CNIC",
#             pdt."Collage_Univeristy",
#             pdt."Collateral_Type",
#             pdt."Contact_No",
#             pdt."Credit_History_Ecib",
#             pdt."Current_Residencial",
#             pdt."Dbr",
#             pdt."Education_Level",
#             pdt."Enrollment_Status",
#             pdt."Enterprise_Premises",
#             pdt."Existing_Loan_Number",
#             pdt."Existing_Loan_Limit",
#             pdt."Existing_Loan_Status",
#             pdt."Existing_Outstanding_Loan_Schedules",
#             pdt."Experiense_Start_Date",
#             pdt."Family_Monthly_Income",
#             pdt."Father_Husband_Name",
#             pdt."Gender",
#             pdt."KF_Remarks",
#             pdt."Loan_Amount",
#             pdt."Loan_Cycle",
#             pdt."LoanProductCode",
#             pdt."Loan_Status",
#             pdt."Monthly_Repayment_Capacity",
#             pdt."Nature_Of_Business",
#             pdt."No_Of_Family_Members",
#             pdt."Permanent_Residencial",
#             pdt."Premises",
#             pdt."Purpose_Of_Loan",
#             pdt."Requested_Loan_Amount",
#             pdt."Residance_Type",
#             pdt."Student_Name",
#             pdt."Student_Co_Borrower_Gender",
#             pdt."Student_Relation_With_Borrower",
#             pdt."Tenor_Of_Month",
#             pdt."Type_of_Business",
#             pdt.Existing_Loan_Exposure_Per_ECIB,
#             pdt.KFT_Approved_Loan_Limit,
#             pdt."annual_income",
#             pdt."notes",
#             pdt."status",
#             pdt."uploaded_date",
#             pdt.reviewed_date,
#             pdt."approved_date",
#             pdt."rejected_date",
#             pdt."email_status",
#             u1."name" AS uploaded_by,
#             u2."name" AS approved_by,
#             u3."name" AS reviewed_by,
#             u4."name" AS rejected_by,
#             b.branch,
#             tbr.branch_role_name as role,
#             b.email,
#             bd.bank_name,
#             pdt."markup_rate",
#             pdt."repayment_frequency",
#             pdt."loan_officer",
#             pdt."appraised_date",
#             pdt."verfied_date_date",
#             pdt."loan_per_exposure",
#             pdt."client_dob",
#             pdt."co_borrower_dob",
#             pdt."relationship_ownership",
#             pdt."other_bank_loans_os"
#         FROM
#             tbl_pre_disbursement_temp pdt
#         {sql_part_temp}
#     """
#     print(query)
#     result = fetch_records(query)
#     # print(result)
#     return result


def get_all_pre_disbursement_temp():
    sql_part_temp = ''

    # Executive ('5') sees the same assigned-branch applications as an Approver; that includes the ones
    # awaiting executive approval, since those are always Agreed/Disagreed statuses.
    if get_current_user_role() in ['1', '2', '5']:
        sql_part_temp = f"""
            INNER JOIN tbl_branches b ON pdt."Branch_Name" LIKE CONCAT('%', b.branch_code, '%') AND b.live_branch = '1'
            INNER JOIN tbl_users u ON b.role = ANY (u.assigned_branch) AND u.active = '1' and u.user_id = '{str(get_current_user_id())}'
            INNER JOIN tbl_branch_role tbr ON tbr.branch_role_id = b.role
            LEFT JOIN tbl_users u1 ON u1.user_id = pdt.uploaded_by
            LEFT JOIN tbl_users u2 ON u2.user_id = pdt.approved_by
            LEFT JOIN tbl_users u3 ON u3.user_id = pdt.reviewed_by
            LEFT JOIN tbl_users u4 ON u4.user_id = pdt.rejected_by
            LEFT JOIN tbl_users u5 ON u5.user_id = pdt.exec_approved_by
            LEFT JOIN tbl_bank_details bd ON bd.bank_id = b.bank_id AND bd.status = '1'
            WHERE pdt.status IN {("('1', '5', '6', '7', '8')" if get_current_user_role() == '1' else "('2', '3', '5', '6', '7', '8', '9', '10')")}
        """
    else:
        sql_part_temp = """
            LEFT JOIN tbl_branches b ON pdt."Branch_Name" LIKE CONCAT('%', b.branch_code, '%') AND b.live_branch = '1'
            LEFT JOIN tbl_branch_role tbr ON tbr.branch_role_id = b.role
            LEFT JOIN tbl_users u1 ON u1.user_id = pdt.uploaded_by
            LEFT JOIN tbl_users u2 ON u2.user_id = pdt.approved_by
            LEFT JOIN tbl_users u3 ON u3.user_id = pdt.reviewed_by
            LEFT JOIN tbl_users u4 ON u4.user_id = pdt.rejected_by
            LEFT JOIN tbl_users u5 ON u5.user_id = pdt.exec_approved_by
            LEFT JOIN tbl_bank_details bd ON bd.bank_id = b.bank_id AND bd.status = '1'
        """

    query = f"""
        SELECT 
            {"DISTINCT" if get_current_user_role() in ['1', '2', '5'] else ""}
            pdt."pre_disb_temp_id",
            pdt."Application_No",
            pdt."Annual_Business_Incomes",
            pdt."Annual_Disposable_Income",
            pdt."Annual_Expenses",
            pdt."ApplicationDate",
            pdt."Bcc_Approval_Date",
            pdt."Borrower_Name",
            pdt."Branch_Area",
            pdt."Branch_Name",
            pdt."Business_Expense_Description",
            pdt."Business_Experiense_Since",
            pdt."Business_Premises",
            pdt."CNIC",
            pdt."Collage_Univeristy",
            pdt."Collateral_Type",
            pdt."Contact_No",
            pdt."Credit_History_Ecib",
            pdt."Current_Residencial",
            pdt."Dbr",
            pdt."Education_Level",
            pdt."Enrollment_Status",
            pdt."Enterprise_Premises",
            pdt."Existing_Loan_Number",
            pdt."Existing_Loan_Limit",
            pdt."Existing_Loan_Status",
            pdt."Existing_Outstanding_Loan_Schedules",
            pdt."Experiense_Start_Date",
            pdt."Family_Monthly_Income",
            pdt."Father_Husband_Name",
            pdt."Gender",
            pdt."KF_Remarks",
            pdt."Loan_Amount",
            pdt."Loan_Cycle",
            pdt."LoanProductCode",
            pdt."Loan_Status",
            pdt."Monthly_Repayment_Capacity",
            pdt."Nature_Of_Business",
            pdt."No_Of_Family_Members",
            pdt."Permanent_Residencial",
            pdt."Premises",
            pdt."Purpose_Of_Loan",
            pdt."Requested_Loan_Amount",
            pdt."Residance_Type",
            pdt."Student_Name",
            pdt."Student_Co_Borrower_Gender",
            pdt."Student_Relation_With_Borrower",
            pdt."Tenor_Of_Month",
            pdt."Type_of_Business",
            pdt.Existing_Loan_Exposure_Per_ECIB,
            pdt.KFT_Approved_Loan_Limit,
            pdt.annual_income,
            pdt.notes,
            pdt.status,
            pdt.uploaded_date,
            pdt.reviewed_date,
            pdt.approved_date,
            pdt.rejected_date,
            pdt.email_status,
            u1.name AS uploaded_by,
            u2.name AS approved_by,
            u3.name AS reviewed_by,
            u4.name AS rejected_by,
            b.branch,
            tbr.branch_role_name AS role,
            b.email,
            bd.bank_name,
            pdt.markup_rate,
            pdt.repayment_frequency,
            pdt.loan_officer,
            pdt.appraised_date,
            pdt.verfied_date_date,
            pdt.loan_per_exposure,
            pdt.client_dob,
            pdt.co_borrower_dob,
            pdt.relationship_ownership,
            pdt.other_bank_loans_os,
            {ALLOW_EXCEPTIONAL_APPROVAL_SQL} AS allow_exceptional_approval,
            u5.name AS exec_approved_by,
            pdt.exec_approved_date,
            pdt.exec_approval_pending
        FROM
            tbl_pre_disbursement_temp pdt
        {sql_part_temp}
    """
    print(query)
    result = fetch_records(query)
    return result


# Product flag for an application: '1' = needs executive approval before the email goes out.
# Prefers the product row matching the applicant's gender, falls back to any row with the same code.
ALLOW_EXCEPTIONAL_APPROVAL_SQL = """
    COALESCE((
        SELECT CAST(lp.allow_exceptional_approval AS VARCHAR)
        FROM tbl_loan_products lp
        WHERE lp.product_code = pdt."LoanProductCode" AND lp.status = '1'
        ORDER BY CASE WHEN lp.gender = pdt."Gender" THEN 0 ELSE 1 END
        LIMIT 1
    ), '2')
"""


def requires_executive_approval(pre_disb_temp_id):
    query = f"""
        SELECT {ALLOW_EXCEPTIONAL_APPROVAL_SQL} AS allow_exceptional_approval
        FROM tbl_pre_disbursement_temp pdt
        WHERE CAST(pdt.pre_disb_temp_id AS VARCHAR) = %s
    """
    result = fetch_records(query, params=(str(pre_disb_temp_id),))
    return bool(result) and str(result[0].get('allow_exceptional_approval')) == '1'



def view_all_rejected_application():

    query = f"""
        SELECT 
            pdt."pre_disb_temp_id",
            pdt."Application_No",
            pdt."Annual_Business_Incomes",
            pdt."Annual_Disposable_Income",
            pdt."Annual_Expenses",
            pdt."ApplicationDate",
            pdt."Bcc_Approval_Date",
            pdt."Borrower_Name",
            pdt."Branch_Area",
            pdt."Branch_Name",
            pdt."Business_Expense_Description",
            pdt."Business_Experiense_Since",
            pdt."Business_Premises",
            pdt."CNIC",
            pdt."Collage_Univeristy",
            pdt."Collateral_Type",
            pdt."Contact_No",
            pdt."Credit_History_Ecib",
            pdt."Current_Residencial",
            pdt."Dbr",
            pdt."Education_Level",
            pdt."Enrollment_Status",
            pdt."Enterprise_Premises",
            pdt."Existing_Loan_Number",
            pdt."Existing_Loan_Limit",
            pdt."Existing_Loan_Status",
            pdt."Existing_Outstanding_Loan_Schedules",
            pdt."Experiense_Start_Date",
            pdt."Family_Monthly_Income",
            pdt."Father_Husband_Name",
            pdt."Gender",
            pdt."KF_Remarks",
            pdt."Loan_Amount",
            pdt."Loan_Cycle",
            pdt."LoanProductCode",
            pdt."Loan_Status",
            pdt."Monthly_Repayment_Capacity",
            pdt."Nature_Of_Business",
            pdt."No_Of_Family_Members",
            pdt."Permanent_Residencial",
            pdt."Premises",
            pdt."Purpose_Of_Loan",
            pdt."Requested_Loan_Amount",
            pdt."Residance_Type",
            pdt."Student_Name",
            pdt."Student_Co_Borrower_Gender",
            pdt."Student_Relation_With_Borrower",
            pdt."Tenor_Of_Month",
            pdt."Type_of_Business",
            pdt.reviewed_date,
            pdt.Existing_Loan_Exposure_Per_ECIB,
            pdt.KFT_Approved_Loan_Limit,
            pdt."annual_income",
            pdt."notes",
            pdt."status",
            pdt."uploaded_date",
            pdt."approved_date",
            pdt."email_status",
            u1."name" AS rejected_by,
            pdr.created_date as rejected_date,
            u2."name" as uploaded_by,
            u3."name" as approved_by,
            u4."name" as reviewed_by
        FROM 
            tbl_pre_disbursement_temp pdt
        inner join tbl_pre_disb_rejected_app pdr on pdr.post_disb_id = pdt.pre_disb_temp_id
        LEFT JOIN tbl_users u1 ON u1."user_id" = pdr.created_by
        LEFT JOIN tbl_users u2 ON u2."user_id" = pdt."uploaded_by"
        LEFT JOIN tbl_users u3 ON u3."user_id" = pdt."approved_by"
        LEFT JOIN tbl_users u4 ON u4."user_id" = pdt."reviewed_by"
    """
    print(query)
    result = fetch_records(query)

    return result


def get_all_pre_disbursement_temp_by_id(id):
    query = f"""
        SELECT 
            pdt."pre_disb_temp_id",
            pdt."Application_No",
            pdt."Annual_Business_Incomes",
            pdt."Annual_Disposable_Income",
            pdt."Annual_Expenses",
            pdt."ApplicationDate",
            pdt."Bcc_Approval_Date",
            pdt."Borrower_Name",
            pdt."Branch_Area",
            pdt."Branch_Name",
            pdt."Business_Expense_Description",
            pdt."Business_Experiense_Since",
            pdt."Business_Premises",
            pdt."CNIC",
            pdt."Collage_Univeristy",
            pdt."Collateral_Type",
            pdt."Contact_No",
            pdt."Credit_History_Ecib",
            pdt."Current_Residencial",
            pdt."Dbr",
            pdt."Education_Level",
            pdt."Enrollment_Status",
            pdt."Enterprise_Premises",
            pdt."Existing_Loan_Number",
            pdt."Existing_Loan_Limit",
            pdt."Existing_Loan_Status",
            pdt."Existing_Outstanding_Loan_Schedules",
            pdt."Experiense_Start_Date",
            pdt."Family_Monthly_Income",
            pdt."Father_Husband_Name",
            pdt."Gender",
            pdt."KF_Remarks",
            pdt."Loan_Amount",
            pdt."Loan_Cycle",
            pdt."LoanProductCode",
            pdt."Loan_Status",
            pdt."Monthly_Repayment_Capacity",
            pdt."Nature_Of_Business",
            pdt."No_Of_Family_Members",
            pdt."Permanent_Residencial",
            pdt."Premises",
            pdt."Purpose_Of_Loan",
            pdt."Requested_Loan_Amount",
            pdt."Residance_Type",
            pdt."Student_Name",
            pdt."Student_Co_Borrower_Gender",
            pdt."Student_Relation_With_Borrower",
            pdt."Tenor_Of_Month",
            pdt."Type_of_Business",
            pdt."annual_income",
            pdt."notes",
            pdt."status",
            pdt."uploaded_date",
            pdt."approved_date"
        FROM 
            tbl_pre_disbursement_temp pdt
        WHERE
        CAST(pdt."pre_disb_temp_id" AS VARCHAR) = %s
    """
    result = fetch_records(query, params=(str(id),))
    # print(result)
    return result


def get_all_pre_disbursement_main():
    sql_part_main = ''

    if get_current_user_role() != 'ADMIN':
        sql_part_main = """
            INNER JOIN tbl_branches b on pdt.Branch_Name LIKE CONCAT('%', b.branch_code, '%') AND b.live_branch = '1'
            INNER JOIN tbl_users u on u.role = b.role and u.active = '1'
            LEFT JOIN tbl_users u1 ON u1.user_id = pdt.uploaded_by
            LEFT JOIN tbl_users u2 ON u2.user_id = pdt.approved_by
            WHERE u.role = '""" + str(get_current_user_role()) + """'
        """
    else:
        sql_part_main = """
            LEFT JOIN tbl_users u1 ON u1.user_id = pdt.uploaded_by
            LEFT JOIN tbl_users u2 ON u2.user_id = pdt.approved_by
        """

    query = f"""
        SELECT 
            pdm.pre_disb_main_id,
            pdm.pre_disb_temp_id,
            pdt.Application_No,
            pdt.Annual_Business_Incomes,
            pdt.Annual_Disposable_Income,
            pdt.Annual_Expenses,
            pdt.ApplicationDate,
            pdt.Bcc_Approval_Date,
            pdt.Borrower_Name,
            pdt.Branch_Area,
            pdt.Branch_Name,
            pdt.Business_Expense_Description,
            pdt.Business_Experiense_Since,
            pdt.Business_Premises,
            pdt.CNIC,
            pdt.Collage_Univeristy,
            pdt.Collateral_Type,
            pdt.Contact_No,
            pdt.Credit_History_Ecib,
            pdt.Current_Residencial,
            pdt.Dbr,
            pdt.Education_Level,
            pdt.Enrollment_Status,
            pdt.Enterprise_Premises,
            pdt.Existing_Loan_Number,
            pdt.Existing_Loan_Limit,
            pdt.Existing_Loan_Status,
            pdt.Existing_Outstanding_Loan_Schedules,
            pdt.Experiense_Start_Date,
            pdt.Family_Monthly_Income,
            pdt.Father_Husband_Name,
            pdt.Gender,
            pdt.KF_Remarks,
            pdt.Loan_Amount,
            pdt.Loan_Cycle,
            pdt.LoanProductCode,
            pdt.Loan_Status,
            pdt.Monthly_Repayment_Capacity,
            pdt.Nature_Of_Business,
            pdt.No_Of_Family_Members,
            pdt.Permanent_Residencial,
            pdt.Premises,
            pdt.Purpose_Of_Loan,
            pdt.Requested_Loan_Amount,
            pdt.Residance_Type,
            pdt.Student_Name,
            pdt.Student_Co_Borrower_Gender,
            pdt.Student_Relation_With_Borrower,
            pdt.Tenor_Of_Month,
            pdt.Type_of_Business,
            pdt.annual_income,
            pdm.notes,
            pdm.status,
            u2.name as approved_by,
            pdm.approved_date
        FROM 
            tbl_pre_disbursement_main pdm
        INNER JOIN 
            tbl_pre_disbursement_temp pdt 
        ON 
            pdm.pre_disb_temp_id = pdt.pre_disb_temp_id
        {sql_part_main}
    """
    print(query)
    result = fetch_records(query)
    # print(result)
    return result





# ---------------------------------------------------------------------------------------------
# Exception report (task 002): applications decided with an exception status.
#   9 = Agreed (With Exception), 10 = Disagreed (With Exception)
#   7 / 8 = Recommended for Agreement / Disagreement (With Exception), only when include_recommended
# Reviewer / Approver / Executive see their assigned branches; Executive Approver and Admin see all.
# ---------------------------------------------------------------------------------------------
EXCEPTION_FINAL_STATUSES = ('9', '10')
EXCEPTION_RECOMMENDED_STATUSES = ('7', '8')

# Who made the decision and when, per status (status 2/3 are used for the "share of all decisions" figure)
_EXC_DECIDED_BY_SQL = """CASE WHEN pdt.status IN ('2', '9') THEN pdt.approved_by
                              WHEN pdt.status IN ('3', '10') THEN pdt.rejected_by
                              ELSE pdt.reviewed_by END"""
_EXC_DECISION_DATE_SQL = """CASE WHEN pdt.status IN ('2', '9') THEN pdt.approved_date
                                 WHEN pdt.status IN ('3', '10') THEN pdt.rejected_date
                                 ELSE pdt.reviewed_date END"""
_EXC_AMOUNT_SQL = """NULLIF(regexp_replace(COALESCE({col}, ''), '[^0-9.]', '', 'g'), '')::numeric"""

_EXC_FROM_SQL = """
    FROM tbl_pre_disbursement_temp pdt
    LEFT JOIN LATERAL (
        SELECT b.branch_id, b.branch, b.role
        FROM tbl_branches b
        WHERE pdt."Branch_Name" LIKE CONCAT('%%', b.branch_code, '%%') AND b.live_branch = '1'
        ORDER BY LENGTH(b.branch_code) DESC
        LIMIT 1
    ) b ON TRUE
    LEFT JOIN tbl_branch_role tbr ON tbr.branch_role_id = b.role
"""


def _exception_report_where(filters, statuses):
    """WHERE clause + params shared by the report rows and the total-decisions figure."""
    filters = filters or {}
    where = ["pdt.status IN %s"]
    params = [tuple(statuses)]

    # Branch scope (same rule as Loan Application Analysis)
    if get_current_user_role() in ['1', '2', '5']:
        where.append("""EXISTS (SELECT 1 FROM tbl_users su
                                WHERE su.user_id = %s AND su.active = '1' AND b.role = ANY (su.assigned_branch))""")
        params.append(int(get_current_user_id()))

    if filters.get('date_from'):
        where.append(f"({_EXC_DECISION_DATE_SQL}) >= %s::date")
        params.append(filters['date_from'])
    if filters.get('date_to'):
        where.append(f"({_EXC_DECISION_DATE_SQL}) < %s::date + INTERVAL '1 day'")
        params.append(filters['date_to'])
    if filters.get('region'):
        where.append("CAST(b.role AS VARCHAR) = %s")
        params.append(str(filters['region']))
    if filters.get('branch'):
        where.append("CAST(b.branch_id AS VARCHAR) = %s")
        params.append(str(filters['branch']))
    if filters.get('product'):
        where.append('pdt."LoanProductCode" = %s')
        params.append(filters['product'])
    return where, params


def get_exception_report(filters=None):
    """Rows for the Exception Report; all values are passed as query parameters."""
    filters = filters or {}
    status = str(filters.get('status') or '')
    if status in EXCEPTION_FINAL_STATUSES:
        statuses = (status,)
    else:
        statuses = EXCEPTION_FINAL_STATUSES + (EXCEPTION_RECOMMENDED_STATUSES if filters.get('include_recommended') else ())

    where, params = _exception_report_where(filters, statuses)

    if filters.get('decided_by'):
        where.append(f"CAST(({_EXC_DECIDED_BY_SQL}) AS VARCHAR) = %s")
        params.append(str(filters['decided_by']))
    if filters.get('reviewed_by'):
        where.append("CAST(pdt.reviewed_by AS VARCHAR) = %s")
        params.append(str(filters['reviewed_by']))
    if filters.get('limit_min') not in (None, ''):
        where.append("COALESCE(pdt.KFT_Approved_Loan_Limit, 0) >= %s")
        params.append(float(filters['limit_min']))
    if filters.get('limit_max') not in (None, ''):
        where.append("COALESCE(pdt.KFT_Approved_Loan_Limit, 0) <= %s")
        params.append(float(filters['limit_max']))
    if filters.get('email') == 'sent':
        where.append("pdt.email_status = 2")
    elif filters.get('email') == 'not_sent':
        where.append("COALESCE(pdt.email_status, 0) <> 2")

    query = f"""
        SELECT
            pdt.pre_disb_temp_id,
            pdt."Application_No" AS application_no,
            pdt."Borrower_Name" AS borrower_name,
            pdt."Father_Husband_Name" AS father_husband_name,
            pdt."CNIC" AS cnic,
            pdt."Gender" AS gender,
            pdt."Contact_No" AS contact_no,
            pdt."Branch_Name" AS branch_name_raw,
            b.branch_id,
            b.branch,
            b.role AS region_id,
            tbr.branch_role_name AS region,
            pdt."LoanProductCode" AS product,
            pdt."Purpose_Of_Loan" AS purpose,
            pdt."Loan_Cycle" AS loan_cycle,
            pdt."Tenor_Of_Month" AS tenor,
            {_EXC_AMOUNT_SQL.format(col='pdt."Requested_Loan_Amount"')} AS requested_amount,
            {_EXC_AMOUNT_SQL.format(col='pdt."Loan_Amount"')} AS loan_amount,
            pdt.KFT_Approved_Loan_Limit AS approved_limit,
            pdt.status,
            {_EXC_DECIDED_BY_SQL} AS decided_by_id,
            ud.name AS decided_by,
            {_EXC_DECISION_DATE_SQL} AS decision_date,
            pdt.reviewed_by AS reviewed_by_id,
            ur.name AS reviewed_by,
            pdt.reviewed_date,
            ue.name AS exec_approved_by,
            pdt.exec_approved_date,
            pdt.exec_approval_pending,
            pdt.email_status,
            pdt.notes,
            pdt."ApplicationDate" AS application_date,
            pdt.uploaded_date
        {_EXC_FROM_SQL}
        LEFT JOIN tbl_users ud ON ud.user_id = {_EXC_DECIDED_BY_SQL}
        LEFT JOIN tbl_users ur ON ur.user_id = pdt.reviewed_by
        LEFT JOIN tbl_users ue ON ue.user_id = pdt.exec_approved_by
        WHERE {' AND '.join(where)}
        ORDER BY decision_date DESC NULLS LAST
    """
    return fetch_records(query, is_print=False, params=tuple(params))


def get_exception_report_total_decisions(filters=None):
    """Final decisions (Agreed / Disagreed, with or without exception) in the same scope, period, area and product."""
    where, params = _exception_report_where(filters, ('2', '3', '9', '10'))
    query = f"SELECT COUNT(*) AS total {_EXC_FROM_SQL} WHERE {' AND '.join(where)}"
    result = fetch_records(query, is_print=False, params=tuple(params))
    return int(result[0]['total']) if result else 0


# ---------------------------------------------------------------------------------------------
# Awaiting Services (dashboard button): every application by stage.
#   Pending   = 1 Under review, 5/7 and 6/8 Recommended for agreement / disagreement (without / with
#               exception), and any final decision held for the executive (exec_approval_pending = 1).
#   Agreed    = 2 / 9 (without / with exception), Disagreed = 3 / 10, once no executive approval is pending.
# Admin, Executive Approver and other permitted users see all; Reviewer / Approver / Executive see
# only the applications of their assigned branches.
# ---------------------------------------------------------------------------------------------
AWAITING_PENDING_STATUSES = ('1', '5', '6', '7', '8')
AWAITING_ALL_STATUSES = AWAITING_PENDING_STATUSES + ('2', '3', '9', '10')
AWAITING_SCOPED_ROLES = ('1', '2', '5')
_AW_EXEC_PENDING_SQL = "COALESCE(CAST(pdt.exec_approval_pending AS VARCHAR), '') = '1'"
_AW_DECIDED_BY_SQL = """CASE WHEN pdt.status IN ('2', '9') THEN pdt.approved_by
                             WHEN pdt.status IN ('3', '10') THEN COALESCE(pdt.rejected_by, pdt.approved_by) END"""
_AW_DECISION_DATE_SQL = """CASE WHEN pdt.status IN ('2', '9') THEN pdt.approved_date
                                WHEN pdt.status IN ('3', '10') THEN COALESCE(pdt.rejected_date, pdt.approved_date) END"""
_AW_FROM_SQL = """
    FROM tbl_pre_disbursement_temp pdt
    LEFT JOIN LATERAL (
        SELECT b.branch_id, b.branch, b.role, b.national_council_distribution
        FROM tbl_branches b
        WHERE pdt."Branch_Name" LIKE CONCAT('%%', b.branch_code, '%%') AND b.live_branch = '1'
        ORDER BY LENGTH(b.branch_code) DESC
        LIMIT 1
    ) b ON TRUE
"""


def _awaiting_scope(where, params):
    if str(get_current_user_role()) in AWAITING_SCOPED_ROLES:
        where.append("""EXISTS (SELECT 1 FROM tbl_users su
                                WHERE su.user_id = %s AND su.active = '1' AND b.role = ANY (su.assigned_branch))""")
        params.append(int(get_current_user_id()))


def get_awaiting_services_rows():
    """One row per application (pending, agreed or disagreed) in the current user's scope."""
    where = ["pdt.status IN %s"]
    params = [AWAITING_ALL_STATUSES]
    _awaiting_scope(where, params)
    query = f"""
        SELECT
            pdt.pre_disb_temp_id AS id,
            pdt."Application_No" AS app_no,
            pdt."Borrower_Name" AS borrower,
            pdt."CNIC" AS cnic,
            pdt."LoanProductCode" AS product,
            {_EXC_AMOUNT_SQL.format(col='pdt."Requested_Loan_Amount"')} AS amount,
            pdt.status,
            CASE WHEN {_AW_EXEC_PENDING_SQL} THEN 1 ELSE 0 END AS exec_pending,
            b.branch,
            ncd.national_council_distribution_name AS council,
            pdt.uploaded_date,
            pdt.reviewed_date,
            ur.name AS reviewed_by,
            {_AW_DECISION_DATE_SQL} AS decision_date,
            ud.name AS decided_by
        {_AW_FROM_SQL}
        LEFT JOIN tbl_national_council_distribution ncd
            ON ncd.national_council_distribution_id = b.national_council_distribution
        LEFT JOIN tbl_users ur ON ur.user_id = pdt.reviewed_by
        LEFT JOIN tbl_users ud ON ud.user_id = {_AW_DECIDED_BY_SQL}
        WHERE {' AND '.join(where)}
    """
    return fetch_records(query, is_print=False, params=tuple(params))


def get_awaiting_pending_count():
    """Dashboard badge: pending applications only, in the current user's scope."""
    where = [f"(pdt.status IN %s OR {_AW_EXEC_PENDING_SQL})"]
    params = [AWAITING_PENDING_STATUSES]
    _awaiting_scope(where, params)
    query = f"SELECT COUNT(*) AS total {_AW_FROM_SQL} WHERE {' AND '.join(where)}"
    result = fetch_records(query, is_print=False, params=tuple(params))
    return int(result[0]['total']) if result else 0

