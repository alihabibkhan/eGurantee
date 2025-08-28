from imports import *


def get_all_loan_products():
    query = f"""
        SELECT lp.product_id, lp.name, lp.product_code, lp.gender, lp.description, lp.status, uc.name as created_by, um.name as modified_by, lp.created_date, lp.modified_date 
        FROM tbl_loan_products lp
        LEFT JOIN tbl_users uc on uc.user_id = lp.created_by
        LEFT JOIN tbl_users um on um.user_id = lp.modified_by
        WHERE lp.status = '1'
    """
    print(query)
    result = fetch_records(query)
    return result