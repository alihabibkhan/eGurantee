from imports import *


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
        'assigned_branch', 'IsLoggedIn', 'last_login'
    ]

    for key in session_keys:
        if key in session:
            session.pop(key)


def is_login():
    if session['IsLoggedIn']:
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



def get_current_user_id():
    if session['user_id']:
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
