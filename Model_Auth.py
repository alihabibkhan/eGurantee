from imports import *


# Figures shown on the public login page. Cached for an hour so page views don't query the database each time.
_LOGIN_STATS_CACHE = {'at': 0, 'data': None}


def get_login_stats():
    if _LOGIN_STATS_CACHE['data'] and time.time() - _LOGIN_STATS_CACHE['at'] < 3600:
        return _LOGIN_STATS_CACHE['data']
    stats = {'years': datetime.now().year - 2010, 'councils': 9, 'loans': '—'}  # fallback while the database is unavailable
    try:
        councils = fetch_records("""
            SELECT COUNT(*) AS n FROM tbl_national_council_distribution
            WHERE is_active = 1 AND status = 1
        """, is_print=False)
        if councils and councils[0]['n']:
            stats['councils'] = int(councils[0]['n'])
        # Task 004: number of loans instead of beneficiaries - same figure as the "Loans" card on the new dashboard
        # (one row per loan from the latest MIS month, loans with a booked-on date; see Model_KFT_Dashboard)
        loans = fetch_records("""
            SELECT COUNT(*) AS n FROM (
                SELECT DISTINCT ON (loan_no) booked_on FROM tbl_post_disbursement
                WHERE DATE_TRUNC('month', mis_date) = (SELECT DATE_TRUNC('month', MAX(mis_date)) FROM tbl_post_disbursement)
                ORDER BY loan_no, id
            ) t WHERE t.booked_on IS NOT NULL
        """, is_print=False)
        if loans and loans[0]['n']:
            stats['loans'] = f"{int(loans[0]['n']):,}"
        if councils and loans:  # only cache real figures; retry next time if the database was unavailable
            _LOGIN_STATS_CACHE.update(at=time.time(), data=stats)
    except Exception as e:
        print('login stats exception:- ', str(e))
    return stats


def get_all_user_data():
    query = f"""
        select u.user_id, u."name", u.email, u.rights,
        u.signature
        from tbl_users u
        where u.user_id = '{str(get_current_user_id())}'
    """

    result = fetch_records(query)

    if result:
        return result[0]

    return None


def get_profile_details(user_id):
    """Read-only details for the profile page: volunteer info, manager name and assigned branch roles."""
    query = """
        SELECT u.volunteer_id, u.phone, u.country_of_residence, u.date_of_joining, u.orientation_completed_on,
               m.name AS manager_name,
               (SELECT STRING_AGG(br.branch_role_name, ', ' ORDER BY br.branch_role_name)
                  FROM tbl_branch_role br
                 WHERE br.branch_role_id = ANY (u.assigned_branch)) AS assigned_branches
        FROM tbl_users u
        LEFT JOIN tbl_users m ON CAST(m.user_id AS VARCHAR) = CAST(u.manager_id AS VARCHAR)
        WHERE CAST(u.user_id AS VARCHAR) = %s
    """
    result = fetch_records(query, is_print=False, params=(str(user_id),))
    return result[0] if result else {}


# def set_user_session(user_data):
#     """
#     Set user session data after successful login
#     Args:
#         user_data (dict): Dictionary containing user data from database
#     """
#     if not user_data or not isinstance(user_data, dict):
#         raise ValueError("Invalid user data provided")
#
#     # Set individual session variables (better than storing entire user object)
#     session['user_id'] = user_data.get('user_id')
#     session['email'] = user_data.get('email')
#     session['name'] = user_data.get('name')
#     session['role'] = user_data.get('role')
#     session['IsLoggedIn'] = True  # Explicit login flag
#
#     # Set last login time
#     session['last_login'] = datetime.now().isoformat()



def set_user_session(user_data):
    print(user_data)
    """
    Set user session data after successful login
    Args:
        user_data (dict): Dictionary containing user data from database
    """
    if not user_data or not isinstance(user_data, dict):
        raise ValueError("Invalid user data provided")

    # Set individual session variables (better than storing entire user object)
    session['user_id'] = user_data.get('user_id')
    session['email'] = user_data.get('email')
    session['name'] = user_data.get('name')
    session['rights'] = user_data.get('rights')
    session['volunteer_id'] = user_data.get('volunteer_id')
    session['gender'] = user_data.get('gender')
    session['dob'] = user_data.get('dob')
    session['phone'] = user_data.get('phone')
    session['country_of_residence'] = user_data.get('country_of_residence')
    session['date_of_joining'] = user_data.get('date_of_joining')
    session['orientation_completed_on'] = user_data.get('orientation_completed_on')
    session['manager_id'] = user_data.get('manager_id')
    session['assigned_branch'] = user_data.get('assigned_branch')
    session['IsLoggedIn'] = True  # Explicit login flag

    # Set last login time
    session['last_login'] = datetime.now().isoformat()


# def clear_user_session():
#     """
#     Completely clear all user-related session data
#     """
#     # Remove all user-related session keys
#     session_keys = ['user_id', 'email', 'name', 'role', 'IsLoggedIn', 'last_login']
#
#     for key in session_keys:
#         if key in session:
#             session.pop(key)

def clear_user_session():
    """
    Completely clear all user-related session data
    """
    # Remove all user-related session keys
    session_keys = [
        'user_id', 'email', 'name', 'rights', 'volunteer_id', 'gender', 'dob', 'phone',
        'country_of_residence', 'date_of_joining', 'orientation_completed_on', 'manager_id',
        'assigned_branch', 'IsLoggedIn', 'last_login',
        'permission_routes', 'permission_loaded_at'
    ]

    for key in session_keys:
        if key in session:
            session.pop(key)


def is_login():
    if 'IsLoggedIn' in session and session['IsLoggedIn']:
        return True

    return False


def is_admin():
    if str(session['rights']) == '4':
        return True

    return False


def is_reviewer():
    if str(session['rights']) == '1':
        return True

    return False


def is_approver():
    if str(session['rights']) == '2':
        return True

    return False

def is_executive_approver():
    if str(session['rights']) == '3':
        return True

    return False


def is_executive():
    # Executive works like an Approver, and also gets the applications awaiting executive approval.
    if str(session['rights']) == '5':
        return True

    return False



def get_current_user_id():
    if 'user_id' in session and session['user_id'] not in ['', None]:
        return str(session['user_id'])
    return '-1'


def get_current_user_role():
    if session['rights']:
        return str(session['rights'])

    return '-1'


def is_user_have_sign():
    user_data = get_all_user_data()
    print('user_data')
    print(user_data)

    if user_data:
        have_signature = True if str(user_data.get('signature')) == '1' else False
        print('have_signature:- ', have_signature)

        if have_signature:
            return True

    return False
