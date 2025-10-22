from imports import *


def get_all_national_council_distributions():
    query = """
        SELECT ncd.national_council_distribution_id, ncd.national_council_distribution_name, ncd.is_active, ncd.status, 
               u.name AS created_by, ncd.created_date
        FROM tbl_national_council_distribution ncd
        LEFT JOIN tbl_users u ON u.user_id = ncd.created_by AND u.active = '1'
        WHERE ncd.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result
