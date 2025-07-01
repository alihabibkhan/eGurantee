from imports import *


def get_all_pre_disbursement_temp():
    query = """
        SELECT 
            pdt.pre_disb_temp_id,
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
            pdt.notes,
            pdt.status,
            pdt.uploaded_by,
            pdt.uploaded_date,
            pdt.approved_by,
            pdt.approved_date
        FROM 
            tbl_pre_disbursement_temp pdt
    """
    result = fetch_records(query)
    # print(result)
    return result


def get_all_pre_disbursement_main():
    query = """
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
            pdm.approved_by,
            pdm.approved_date
        FROM 
            tbl_pre_disbursement_main pdm
        INNER JOIN 
            tbl_pre_disbursement_temp pdt 
        ON 
            pdm.pre_disb_temp_id = pdt.pre_disb_temp_id
    """
    result = fetch_records(query)
    # print(result)
    return result



