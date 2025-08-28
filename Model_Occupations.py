from imports import *


def get_all_occupations():
    query = f"""
        SELECT op.occupation_id, op.name, op.status, uc.name as created_by, um.name as modified_by, op.modified_date 
        FROM tbl_occupations op
        LEFT JOIN tbl_users uc on uc.user_id = op.created_by
        LEFT JOIN tbl_users um on um.user_id = op.modified_by
        WHERE op.status = '1'
    """
    print(query)
    result = fetch_records(query)
    return result