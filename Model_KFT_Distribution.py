from imports import *


def get_all_kft_distributions():
    query = """
        SELECT kd.kft_distribution_id, kd.kft_distribution_name, kd.is_active, kd.status, 
               u.name AS created_by, kd.created_date
        FROM tbl_kft_distribution kd
        LEFT JOIN tbl_users u ON u.user_id = kd.created_by AND u.active = '1'
        WHERE kd.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result
