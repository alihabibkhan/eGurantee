from imports import *


def get_disbursed_loan_count():
    query = """
        SELECT 
            "LoanProductCode",
            COUNT(*) AS Count
        FROM 
            tbl_pre_disbursement_temp
        WHERE 
            Status = '7'
        GROUP BY 
            "LoanProductCode"
        ORDER BY 
            "LoanProductCode";
    """
    result = fetch_records(query)

    return result


def get_active_loan_count():
    query = """
        SELECT 
            "LoanProductCode",
            COUNT(*) AS Count
        FROM 
            tbl_pre_disbursement_temp
        WHERE 
            Status IN ('5', '2', '1')
        GROUP BY 
            "LoanProductCode"
        ORDER BY 
            "LoanProductCode";
    """
    result = fetch_records(query)

    return result


def get_non_performing_loan_count():
    query = """
        SELECT 
            "LoanProductCode",
            COUNT(*) AS Count
        FROM 
            tbl_pre_disbursement_temp
        WHERE 
            Status IN ('3', '6')
        GROUP BY 
            "LoanProductCode"
        ORDER BY 
            "LoanProductCode";
    """
    result = fetch_records(query)

    return result


def total_loan_beneficiary_count():
    query = """
        SELECT 
            "Gender",
            COUNT(*) AS Count
        FROM 
            tbl_pre_disbursement_temp
        WHERE 
            "Gender" != ''
        GROUP BY 
            "Gender"
        ORDER BY 
            "Gender";
    """

    result = fetch_records(query)

    return result


def get_loan_details_by_branch_area():
    query = """
        SELECT 
            b.role, b.Area_Name, 
            COUNT(CASE WHEN pdt."Gender" IS NOT NULL THEN 1 END) AS Beneficiary_COUNT,
            COUNT(CASE WHEN pdt."status" = '7' THEN 1 END) AS Disbursed_Count,
            COUNT(CASE WHEN pdt."status" IN ('1', '5', '2') THEN 1 END) AS Active_Count
        FROM 
            tbl_pre_disbursement_temp pdt
        INNER JOIN tbl_branches b 
            ON pdt."Branch_Name" LIKE CONCAT('%', b."branch_code", '%') 
            AND b."live_branch" = '1'
        WHERE 
            pdt."pre_disb_temp_id" != 0
        GROUP BY 
           b.role, b.Area_Name;
    """

    result = fetch_records(query)

    return result
