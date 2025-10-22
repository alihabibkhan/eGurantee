from imports import *


def get_all_bank_distributions():
    query = """
        SELECT bd.bank_distribution_id, bd.bank_distribution_name, bd.is_active, bd.status, 
               u.name AS created_by, bd.created_date
        FROM tbl_bank_distribution bd
        LEFT JOIN tbl_users u ON u.user_id = bd.created_by AND u.active = '1'
        WHERE bd.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result
