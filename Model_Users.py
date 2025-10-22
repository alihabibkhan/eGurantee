from imports import *


def get_all_user_data():
    query = f"""
        SELECT DISTINCT u.user_id, u.name, u.email, u.rights, u.volunteer_id, u.gender, u.dob, u.phone, 
                        u.country_of_residence, u.date_of_joining, u.orientation_completed_on, u.manager_id, 
                        br.branch_role_name as assigned_branch, u.date_of_retirement, u.reason, 
                        u1.name AS created_by_name, u.created_date, u.active 
        FROM tbl_users u 
        LEFT JOIN tbl_users u1 ON u1.user_id = u.created_by
        left join tbl_branch_role br on br.branch_role_id = u.assigned_branch
        ORDER BY u.user_id     
    """
    print(query)
    result = fetch_records(query)
    print(result)

    return result


def get_all_user_data_by_id(id):
    print('executing get_all_user_data_by_id method.')
    query = f"""
        SELECT DISTINCT u.user_id, u.name, u.email, u.rights, u.volunteer_id, u.gender, u.dob, u.phone, 
                        u.country_of_residence, u.date_of_joining, u.orientation_completed_on, u.manager_id, 
                        u.assigned_branch, u.date_of_retirement, u.reason
        FROM tbl_users u where u.user_id = '{str(id)}'
    """
    result = fetch_records(query, is_print=True)
    print('printing result of get_all_user_data_by_id')
    print(result)
    return result[0]


def get_all_user_privileges():
    """
    Fetch all active user privileges with user details from tbl_users
    Returns:
        List of dictionaries containing privilege and user data
    """
    query = f"""
        SELECT DISTINCT 
            p.id, p.user_id, p.role, p.responsibility, p.committee, p.status,
            u1.name AS created_by_name, p.created_by, p.created_date,
            u2.name AS modified_by_name, p.modified_by, p.modified_date,
            u.name AS user_name
        FROM tbl_user_privileges p
        INNER JOIN tbl_users u ON p.user_id = u.user_id
        LEFT JOIN tbl_users u1 ON p.created_by = u1.user_id
        LEFT JOIN tbl_users u2 ON p.modified_by = u2.user_id
        WHERE p.status = 1
    """
    print(query)
    result = fetch_records(query)
    return result


def get_all_user_privileges_by_user_id(user_id):
    print('executing get_all_user_privileges_by_user_id method.')
    """
    Fetch all active user privileges for a specific user_id with user details
    Args:
        user_id (str): The ID of the user to filter privileges
    Returns:
        List of dictionaries containing privilege and user data
    """
    query = f"""
        SELECT DISTINCT 
            p.id, p.user_id, p.role, p.responsibility, p.committee, p.status,
            u1.name AS created_by_name, p.created_by, p.created_date,
            u2.name AS modified_by_name, p.modified_by, p.modified_date,
            u.name AS user_name
        FROM tbl_user_privileges p
        INNER JOIN tbl_users u ON p.user_id = u.user_id
        LEFT JOIN tbl_users u1 ON p.created_by = u1.user_id
        LEFT JOIN tbl_users u2 ON p.modified_by = u2.user_id
        WHERE p.status = 1 AND p.user_id = '{user_id}'
    """
    result = fetch_records(query, is_print=True)
    print('printing result of get_all_user_privileges_by_user_id')
    print(result)

    return result


def get_all_user_service_terms():
    """
    Fetch all active user service terms with user details from tbl_users
    Returns:
        List of dictionaries containing service term and user data
    """
    query = """
        SELECT DISTINCT 
            t.id, t.user_id, t.term, t.from_date, t.to_date, t.status, t.tenure_cap, t.actual_end_date, t.month_served,
            t.created_date, t.modified_date, u2.name AS modified_by_name
        FROM tbl_user_service_terms t
        INNER JOIN tbl_users u ON t.user_id = u.user_id
        LEFT JOIN tbl_users u1 ON t.created_by = u1.user_id
        LEFT JOIN tbl_users u2 ON t.modified_by = u2.user_id
        WHERE t.status = 1
    """
    print(query)
    result = fetch_records(query)
    return result


def get_all_user_service_terms_by_user_id(user_id):
    """
    Fetch all active user service terms for a specific user_id with user details
    Args:
        user_id (str): The ID of the user to filter service terms
    Returns:
        List of dictionaries containing service term and user data
    """
    query = f"""
        SELECT DISTINCT 
            t.id, t.user_id, t.term, t.from_date, t.to_date, t.status, t.tenure_cap, t.actual_end_date, t.month_served,
            t.created_date, t.modified_date, u2.name AS modified_by_name
        FROM tbl_user_service_terms t
        INNER JOIN tbl_users u ON t.user_id = u.user_id
        LEFT JOIN tbl_users u1 ON t.created_by = u1.user_id
        LEFT JOIN tbl_users u2 ON t.modified_by = u2.user_id
        WHERE t.status = 1 AND t.user_id = '{user_id}'
    """
    print(query)
    result = fetch_records(query)
    return result