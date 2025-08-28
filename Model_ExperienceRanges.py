from imports import *


def get_all_experience_ranges():
    query = f"""
        SELECT er.experience_range_id,er. label, er.min_years, er.max_years, er.status, uc.name as created_by, um.name as modified_by,
               er.modified_date
        FROM tbl_experience_ranges er
        LEFT JOIN tbl_users uc on uc.user_id = er.created_by
        LEFT JOIN tbl_users um on um.user_id = er.modified_by
        WHERE er.status = '1'
    """
    print(query)
    result = fetch_records(query)
    return result