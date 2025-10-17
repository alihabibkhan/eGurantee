from imports import *


def get_all_user_service_hours():
    print('executing get_all_user_service_hours method.')
    query = """
        SELECT ush.user_service_hours_id, ush.user_id, ush.service_hours, ush.service_category, 
               ush.description, ush.status, 
               u1.name AS created_by_name, ush.created_date, 
               u2.name AS modified_by_name, ush.modified_date
        FROM tbl_user_service_hours ush
        LEFT JOIN tbl_users u1 ON u1.user_id = ush.created_by AND u1.active = '1'
        LEFT JOIN tbl_users u2 ON u2.user_id = ush.modified_by AND u2.active = '1'
        WHERE ush.status = '1'
    """
    result = fetch_records(query, is_print=True)
    print('printing result of get_all_user_service_hours')
    return result


def get_user_service_hours_by_user_id(user_id):
    print('executing get_user_service_hours_by_user_id method.')
    query = f"""
        SELECT ush.user_service_hours_id, ush.user_id, ush.service_hours, ush.service_category, 
               ush.description, ush.status, 
               u1.name AS created_by_name, ush.created_date, 
               u2.name AS modified_by_name, ush.modified_date
        FROM tbl_user_service_hours ush
        LEFT JOIN tbl_users u1 ON u1.user_id = ush.created_by AND u1.active = '1'
        LEFT JOIN tbl_users u2 ON u2.user_id = ush.modified_by AND u2.active = '1'
        WHERE ush.user_id = {user_id} AND ush.status = '1'
    """
    result = fetch_records(query, is_print=True)
    print('printing result of get_user_service_hours_by_user_id')
    print(result)
    return result


def get_user_reporting_period_by_user_id(user_id):
    print('executing get_user_reporting_period_by_user_id method.')
    query = f"""
        SELECT urp.user_reporting_period_id, urp.user_id, urp.reporting_date, urp.status, 
               u1.name AS created_by_name, urp.created_date, 
               u2.name AS modified_by_name, urp.modified_date
        FROM tbl_user_reporting_period urp
        LEFT JOIN tbl_users u1 ON u1.user_id = urp.created_by AND u1.active = '1'
        LEFT JOIN tbl_users u2 ON u2.user_id = urp.modified_by AND u2.active = '1'
        WHERE urp.user_id = {user_id} AND urp.status = '1'
    """
    result = fetch_records(query, is_print=True)
    print('printing result of get_user_reporting_period_by_user_id')
    print(result)
    return result  # Return the entire list

