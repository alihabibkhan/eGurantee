from imports import *


def get_disbursed_loan_count():
    query = """
        SELECT 
            COUNT(*) AS total_disbursements,
            SUM(pd.disbursed_amount) AS total_disbursed_amount
        FROM tbl_post_disbursement pd
        WHERE pd.disbursed_amount > 0 and DATE_TRUNC('month', pd.mis_date) = (
            SELECT DATE_TRUNC('month', MAX(mis_date)) 
            FROM tbl_post_disbursement
        );
    """
    result = fetch_records(query)
    print("get_disbursed_loan_count")
    print(result)
    return result


def get_outstanding_loans():
    query = """
        SELECT 
            COUNT(*) AS total_principal_outstanding_count,
            SUM(principal_outstanding) AS total_principal_outstanding
        FROM tbl_post_disbursement
        WHERE principal_outstanding > 0
          AND DATE_TRUNC('month', mis_date) = (
              SELECT DATE_TRUNC('month', MAX(mis_date)) FROM tbl_post_disbursement
          );
    """
    result = fetch_records(query)
    print("get_outstanding_loans")
    print(result)

    return result


def get_non_performing_loan_count():
    query = """
        SELECT 
            COUNT(*) AS non_performing_loans_count,
            SUM(principal_outstanding) AS non_performing_loans
        FROM tbl_post_disbursement
        WHERE principal_outstanding > 0
          AND loan_status NOT IN ('NORM', 'WLST')
          AND DATE_TRUNC('month', mis_date) = (
              SELECT DATE_TRUNC('month', MAX(mis_date)) FROM tbl_post_disbursement
        );

    """
    result = fetch_records(query)
    print("get_non_performing_loan_count")
    print(result)

    return result


def total_loan_beneficiary_count():
    query = """
        SELECT 
            COALESCE(pd.gender, 'Total') AS gender,
            COUNT(DISTINCT pd.cnic) AS unique_cnic_count
        FROM tbl_post_disbursement pd
        WHERE DATE_TRUNC('month', pd.mis_date) = (
            SELECT DATE_TRUNC('month', MAX(mis_date)) FROM tbl_post_disbursement
        )
        GROUP BY ROLLUP(pd.gender);
    """

    result = fetch_records(query)
    print("total_loan_beneficiary_count")
    print(result)

    return result


def get_latest_portfolio_date():
    query = """
        SELECT DATE(MAX(mis_date)) AS latest_record_date
        FROM tbl_post_disbursement;
    """
    result = fetch_records(query)

    print("get_latest_portfolio_date")
    print(result)

    return result[0]


def get_loan_details_by_national_council():
    print("get_loan_details_by_national_council")
    query = """
        SELECT 
            REGEXP_REPLACE(INITCAP(REPLACE(b.national_council_distribution, '_', ' ')), ' Rc$', ' RC') AS national_council_distribution,
            COUNT(DISTINCT pd.cnic) AS total_beneficiaries,
            COUNT(CASE WHEN pd.disbursed_amount > 0 THEN 1 END) AS disbursed_count,
            COUNT(CASE WHEN pd.principal_outstanding > 0 THEN 1 END) AS active_loan_count
        FROM tbl_post_disbursement pd
        INNER JOIN tbl_branches b
            ON pd.branch_code = b.branch_code
        WHERE 
            b.live_branch = '1'
            AND DATE_TRUNC('month', pd.mis_date) = (
                SELECT DATE_TRUNC('month', MAX(mis_date)) 
                FROM tbl_post_disbursement
            )
        GROUP BY b.national_council_distribution;
    """

    result = fetch_records(query)
    print(result)

    return result
