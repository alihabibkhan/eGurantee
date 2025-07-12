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


def get_all_budget_info_grouped_by_branch():
    query = """
        select b.mis_date ,z."role", Z.branch_name , sum(b.amount) AMT
        from public.tbl_budget b 
        inner join public.tbl_branches z on b.branch_code = z.branch_code
        group by b.mis_date ,z."role",  Z.branch_name
        order by 1 ASC
    """
    result = fetch_records(query)
    # print(result)
    return result
