from imports import *


def get_all_branch_roles():
    query = """
        SELECT br.branch_role_id, br.branch_role_name, br.is_active, br.status, 
               u.name AS created_by, br.created_date
        FROM tbl_branch_role br
        LEFT JOIN tbl_users u ON u.user_id = br.created_by AND u.active = '1'
        WHERE br.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result