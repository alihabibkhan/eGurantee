# helpers/permission_helper.py
from imports import *

class PermissionHelper:
    @staticmethod
    def has_permission(user_id, route):
        """
        Check if user has access to a specific route
        Returns True if user has permission via role or direct user permission
        """
        try:
            # First check direct user permission (highest priority)
            user_perm_query = f"""
                SELECT 1 FROM tbl_user_permissions up
                JOIN tbl_web_permissions wp ON up.web_permission_id = wp.web_permission_id
                WHERE up.user_id = {user_id} 
                  AND up.status = 1 
                  AND wp.status = 1 
                  AND wp.route = '{route}'
            """
            if fetch_records(user_perm_query):
                return True

            # TODO: Later you can add role-based check here if needed
            # For now, we're only using dynamic user permissions as requested

            return False

        except Exception as e:
            print('has_permission exception:- ', str(e))
            return False


    # Optional: Check by permission_key instead of route
    @staticmethod
    def has_permission_key(user_id, permission_key):
        try:
            query = f"""
                SELECT 1 FROM tbl_user_permissions up
                JOIN tbl_web_permissions wp ON up.web_permission_id = wp.web_permission_id
                WHERE up.user_id = {user_id} 
                  AND up.status = 1 
                  AND wp.status = 1 
                  AND wp.permission_key = '{escape_sql_string(permission_key)}'
            """
            return bool(fetch_records(query))
        except:
            return False