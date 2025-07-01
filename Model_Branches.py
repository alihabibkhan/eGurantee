from imports import *


def get_all_branches_info():
    query = """
        select b.branch_id, b.branch_code, b.role, b.branch_name, b.area, b.email, u.name as createdBy, b.created_date 
        from tbl_branches b 
        left join tbl_users u on u.user_id = b.created_by and u.active = '1'
        where b.live_branch = '1'
    """
    result = fetch_records(query)
    print(result)
    return result

