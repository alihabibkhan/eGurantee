# helpers/permission_helper.py
from imports import *

# Session keys used to cache the logged-in user's permitted routes.
PERMISSION_ROUTES_SESSION_KEY = 'permission_routes'
PERMISSION_LOADED_AT_SESSION_KEY = 'permission_loaded_at'

# Permissions granted/revoked by an admin reach an already logged-in user after
# at most this many seconds (the session cache is then reloaded from the DB).
PERMISSION_CACHE_TTL_SECONDS = int(os.getenv('PERMISSION_CACHE_TTL_SECONDS', 300))


class PermissionHelper:
    @staticmethod
    def load_user_permission_routes(user_id):
        """Fetch every active route the user has direct permission for."""
        query = """
            SELECT DISTINCT wp.route FROM tbl_user_permissions up
            JOIN tbl_web_permissions wp ON up.web_permission_id = wp.web_permission_id
            WHERE up.user_id = %s
              AND up.status = 1
              AND wp.status = 1
              AND wp.route IS NOT NULL
        """
        records = fetch_records(query, is_print=False, params=(int(user_id),))
        return sorted({record['route'] for record in records})

    @staticmethod
    def cache_user_permissions(user_id):
        """Load the user's permissions once and keep them in the session (called at login)."""
        try:
            session[PERMISSION_ROUTES_SESSION_KEY] = PermissionHelper.load_user_permission_routes(user_id)
            session[PERMISSION_LOADED_AT_SESSION_KEY] = time.time()
        except Exception as e:
            print('cache_user_permissions exception:- ', str(e))
            PermissionHelper.clear_cached_permissions()

    @staticmethod
    def clear_cached_permissions():
        session.pop(PERMISSION_ROUTES_SESSION_KEY, None)
        session.pop(PERMISSION_LOADED_AT_SESSION_KEY, None)

    @staticmethod
    def get_cached_permission_routes(user_id):
        """
        Return the current user's permitted routes as a set, (re)loading the
        session cache when it is missing or older than the TTL.
        Per-request copy is kept in `g` so templates can call has_permission()
        many times without rebuilding the set.
        """
        cached = getattr(g, '_permission_routes', None)
        if cached is not None:
            return cached

        loaded_at = session.get(PERMISSION_LOADED_AT_SESSION_KEY)
        is_stale = loaded_at is None or (time.time() - float(loaded_at)) > PERMISSION_CACHE_TTL_SECONDS
        if PERMISSION_ROUTES_SESSION_KEY not in session or is_stale:
            PermissionHelper.cache_user_permissions(user_id)

        g._permission_routes = set(session.get(PERMISSION_ROUTES_SESSION_KEY, []))
        return g._permission_routes

    @staticmethod
    def has_permission(user_id, route):
        """
        Check if user has access to a specific route
        Returns True if user has permission via role or direct user permission
        """
        try:
            if user_id in [None, '', '-1', -1]:
                return False

            # Current user -> answer from the session cache (no DB round trip)
            if str(user_id) == str(session.get('user_id')):
                return route in PermissionHelper.get_cached_permission_routes(user_id)

            # Checking a different user -> query the database directly
            user_perm_query = """
                SELECT 1 FROM tbl_user_permissions up
                JOIN tbl_web_permissions wp ON up.web_permission_id = wp.web_permission_id
                WHERE up.user_id = %s
                  AND up.status = 1
                  AND wp.status = 1
                  AND wp.route = %s
            """
            if fetch_records(user_perm_query, is_print=False, params=(int(user_id), route)):
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
            query = """
                SELECT 1 FROM tbl_user_permissions up
                JOIN tbl_web_permissions wp ON up.web_permission_id = wp.web_permission_id
                WHERE up.user_id = %s
                  AND up.status = 1
                  AND wp.status = 1
                  AND wp.permission_key = %s
            """
            return bool(fetch_records(query, is_print=False, params=(int(user_id), permission_key)))
        except:
            return False
