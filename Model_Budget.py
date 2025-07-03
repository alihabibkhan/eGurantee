from imports import *


def get_all_budget_info():
    query = """
        select b.budget_id, b.mis_date, b.branch_code, b.amount, u.name as createdBy, b.created_date from tbl_budget b 
        left join tbl_users u on u.user_id = b.created_by
        where
        u.active = '1'
    """
    result = fetch_records(query)
    # print(result)
    return result
