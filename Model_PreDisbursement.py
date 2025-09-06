from imports import *


# def get_all_pre_disbursement_temp():
#     sql_part_temp = ''
#
#     if get_current_user_role() != 'ADMIN':
#         sql_part_temp = """
#             INNER JOIN tbl_branches b on pdt.Branch_Name LIKE CONCAT('%', b.branch_code, '%') AND b.live_branch = '1'
#             INNER JOIN tbl_users u on u.role = b.role and u.active = '1'
#             LEFT JOIN tbl_users u1 ON u1.user_id = pdt.uploaded_by
#             LEFT JOIN tbl_users u2 ON u2.user_id = pdt.approved_by
#             WHERE u.role = '""" + str(get_current_user_role()) + """'
#         """
#     else:
#         sql_part_temp = """
#             LEFT JOIN tbl_users u1 ON u1.user_id = pdt.uploaded_by
#             LEFT JOIN tbl_users u2 ON u2.user_id = pdt.approved_by
#         """
#
#     query = f"""
#         SELECT
#             pdt.pre_disb_temp_id,
#             pdt.Application_No,
#             pdt.Annual_Business_Incomes,
#             pdt.Annual_Disposable_Income,
#             pdt.Annual_Expenses,
#             pdt.ApplicationDate,
#             pdt.Bcc_Approval_Date,
#             pdt.Borrower_Name,
#             pdt.Branch_Area,
#             pdt.Branch_Name,
#             pdt.Business_Expense_Description,
#             pdt.Business_Experiense_Since,
#             pdt.Business_Premises,
#             pdt.CNIC,
#             pdt.Collage_Univeristy,
#             pdt.Collateral_Type,
#             pdt.Contact_No,
#             pdt.Credit_History_Ecib,
#             pdt.Current_Residencial,
#             pdt.Dbr,
#             pdt.Education_Level,
#             pdt.Enrollment_Status,
#             pdt.Enterprise_Premises,
#             pdt.Existing_Loan_Number,
#             pdt.Existing_Loan_Limit,
#             pdt.Existing_Loan_Status,
#             pdt.Existing_Outstanding_Loan_Schedules,
#             pdt.Experiense_Start_Date,
#             pdt.Family_Monthly_Income,
#             pdt.Father_Husband_Name,
#             pdt.Gender,
#             pdt.KF_Remarks,
#             pdt.Loan_Amount,
#             pdt.Loan_Cycle,
#             pdt.LoanProductCode,
#             pdt.Loan_Status,
#             pdt.Monthly_Repayment_Capacity,
#             pdt.Nature_Of_Business,
#             pdt.No_Of_Family_Members,
#             pdt.Permanent_Residencial,
#             pdt.Premises,
#             pdt.Purpose_Of_Loan,
#             pdt.Requested_Loan_Amount,
#             pdt.Residance_Type,
#             pdt.Student_Name,
#             pdt.Student_Co_Borrower_Gender,
#             pdt.Student_Relation_With_Borrower,
#             pdt.Tenor_Of_Month,
#             pdt.Type_of_Business,
#             pdt.annual_income,
#             pdt.notes,
#             pdt.status,
#             pdt.uploaded_date,
#             pdt.approved_date,
#             u1.name as uploaded_by,
#             u2.name as approved_by
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

    if get_current_user_role() == '1':
        sql_part_temp = f"""
            INNER JOIN tbl_branches b on pdt."Branch_Name" LIKE CONCAT('%', b."branch_code", '%') AND b."live_branch" = '1'
            INNER JOIN tbl_users u on u.assigned_branch = b.role and u."active" = '1'
            LEFT JOIN tbl_users u1 ON u1."user_id" = pdt."uploaded_by"
            LEFT JOIN tbl_users u2 ON u2."user_id" = pdt."approved_by"
            pdt.status in ('1', '4')
        """
    else:
        sql_part_temp = """
            LEFT JOIN tbl_users u1 ON u1."user_id" = pdt."uploaded_by"
            LEFT JOIN tbl_users u2 ON u2."user_id" = pdt."approved_by"
        """

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
            pdt.reviewed_by,
            pdt.Existing_Loan_Exposure_Per_ECIB,
            pdt."annual_income",
            pdt."notes",
            pdt."status",
            pdt."uploaded_date",
            pdt."approved_date",
            pdt."email_status",
            u1."name" AS uploaded_by,
            u2."name" AS approved_by
        FROM 
            tbl_pre_disbursement_temp pdt
        {sql_part_temp}    
    """
    print(query)
    result = fetch_records(query)
    # print(result)
    return result


# def get_all_pre_disbursement_temp_by_id(id):
#     query = f"""
#         SELECT
#             pdt.pre_disb_temp_id,
#             pdt.Application_No,
#             pdt.Annual_Business_Incomes,
#             pdt.Annual_Disposable_Income,
#             pdt.Annual_Expenses,
#             pdt.ApplicationDate,
#             pdt.Bcc_Approval_Date,
#             pdt.Borrower_Name,
#             pdt.Branch_Area,
#             pdt.Branch_Name,
#             pdt.Business_Expense_Description,
#             pdt.Business_Experiense_Since,
#             pdt.Business_Premises,
#             pdt.CNIC,
#             pdt.Collage_Univeristy,
#             pdt.Collateral_Type,
#             pdt.Contact_No,
#             pdt.Credit_History_Ecib,
#             pdt.Current_Residencial,
#             pdt.Dbr,
#             pdt.Education_Level,
#             pdt.Enrollment_Status,
#             pdt.Enterprise_Premises,
#             pdt.Existing_Loan_Number,
#             pdt.Existing_Loan_Limit,
#             pdt.Existing_Loan_Status,
#             pdt.Existing_Outstanding_Loan_Schedules,
#             pdt.Experiense_Start_Date,
#             pdt.Family_Monthly_Income,
#             pdt.Father_Husband_Name,
#             pdt.Gender,
#             pdt.KF_Remarks,
#             pdt.Loan_Amount,
#             pdt.Loan_Cycle,
#             pdt.LoanProductCode,
#             pdt.Loan_Status,
#             pdt.Monthly_Repayment_Capacity,
#             pdt.Nature_Of_Business,
#             pdt.No_Of_Family_Members,
#             pdt.Permanent_Residencial,
#             pdt.Premises,
#             pdt.Purpose_Of_Loan,
#             pdt.Requested_Loan_Amount,
#             pdt.Residance_Type,
#             pdt.Student_Name,
#             pdt.Student_Co_Borrower_Gender,
#             pdt.Student_Relation_With_Borrower,
#             pdt.Tenor_Of_Month,
#             pdt.Type_of_Business,
#             pdt.annual_income,
#             pdt.notes,
#             pdt.status,
#             pdt.uploaded_by,
#             pdt.uploaded_date,
#             pdt.approved_by,
#             pdt.approved_date
#         FROM
#             tbl_pre_disbursement_temp pdt
#         WHERE
#         pdt.pre_disb_temp_id = '{str(id)}'
#     """
#     result = fetch_records(query)
#     # print(result)
#     return result

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
        pdt."pre_disb_temp_id" = '{str(id)}'
    """
    result = fetch_records(query)
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



