from imports import *


def get_user_comm_svc_hours_by_user_id(user_id):
    print('executing get_user_comm_svc_hours_by_user_id method.')
    query = f"""
        SELECT ush.cum_sev_hr_id, ush.user_id, ush.hours_contributed, ush.service_category, 
               ush.brief_key_activities, ush.status, 
               u1.name AS created_by_name, TO_CHAR(ush.month_year, 'YYYY-MM') AS month_year, 
               ush.created_date, u2.name AS modified_by_name, ush.modified_date
        FROM tbl_user_comm_svc_hours ush
        LEFT JOIN tbl_users u1 ON u1.user_id = ush.created_by AND u1.active = '1'
        LEFT JOIN tbl_users u2 ON u2.user_id = ush.modified_by AND u2.active = '1'
        WHERE ush.user_id = {user_id} AND ush.status = '1' ORDER BY ush.month_year
    """
    result = fetch_records(query, is_print=True)
    print('printing result of get_user_comm_svc_hours_by_user_id')
    print(result)
    return result

