from imports import *


def get_all_loan_metrics():
    # JOIN tbl_branches b ON lm.branch_id = b.branch_id
    query = f"""
        SELECT lm.loan_metric_id, lp.name as product_name, lp.gender, o.name as occupation_name,
               er.label as experience_label, lm.global_loan_ceiling,
               lm.repeat_increment, lm.required_paid_off, lm.interest_rate, lm.is_active, lm.status, uc.name as created_by, um.name as modified_by, lm.created_date, lm.modified_date
        FROM tbl_loan_metrics lm
        JOIN tbl_loan_products lp ON lm.product_id = lp.product_id
        JOIN tbl_occupations o ON lm.occupation_id = o.occupation_id
        JOIN tbl_experience_ranges er ON lm.experience_id = er.experience_range_id
        LEFT JOIN tbl_users uc on uc.user_id = lm.created_by
        LEFT JOIN tbl_users um on um.user_id = lm.modified_by
        WHERE lm.is_active = '1' AND lm.status = '1'
    """
    print(query)
    result = fetch_records(query)
    return result


def get_loan_metrics_by_occupation_and_experience(occupation=None, experience=None):
    sql_part = ''
    if occupation:
        sql_part = f"AND o.name = '{occupation}'"

    if experience:
        sql_part += f" AND er.label = '{experience}'"

    query = f"""
        SELECT lm.loan_metric_id, lp.name as product_name, lp.gender, o.name as occupation_name,
               er.label as experience_label, er.min_years, er.max_years, b.branch_name as branch_name, lm.global_loan_ceiling,
               lm.repeat_increment, lm.interest_rate, lm.required_paid_off, lm.is_active, lm.status, uc.name as created_by, um.name as modified_by, lm.created_date, lm.modified_date
        FROM tbl_loan_metrics lm
        JOIN tbl_loan_products lp ON lm.product_id = lp.product_id
        JOIN tbl_occupations o ON lm.occupation_id = o.occupation_id
        JOIN tbl_experience_ranges er ON lm.experience_id = er.experience_range_id
        JOIN tbl_branches b ON lm.branch_id = b.branch_id
        LEFT JOIN tbl_users uc on uc.user_id = lm.created_by
        LEFT JOIN tbl_users um on um.user_id = lm.modified_by
        WHERE lm.is_active = '1' AND lm.status = '1' {sql_part}
    """
    print(query)
    result = fetch_records(query)
    return result


