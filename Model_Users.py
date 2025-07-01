from imports import *


def get_all_user_data():
    query = f"""
        select DISTINCT u.user_id, u.name, u.email, u.role, u1.name as createdBy, u.created_date from tbl_users u 
        left join tbl_users u1 on u1.user_id = u.created_by and u.active = '1'
        where u.active = '1';            
    """
    print(query)
    result = fetch_records(query)

    return result
