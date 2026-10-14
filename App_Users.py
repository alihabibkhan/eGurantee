from imports import *
from application import application


def generate_random_password():
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(11))
    return password


@application.route('/manage_users')
def manage_users():
    try:
        if is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/manage_users")):
            content = {
                'get_all_user_data': get_all_user_data(),
                'get_all_branches_info': get_all_branches_info(),
                'get_all_user_privileges': get_all_user_privileges()
            }
            return render_template('manage_users.html', result=content)
    except Exception as e:
        print('manage users exception:- ', str(e))
    return redirect(url_for('login'))


# @application.route('/add-edit-user', methods=['GET', 'POST'])
# @application.route('/add-edit-user/<int:user_id>', methods=['GET', 'POST'])
# def add_edit_user(user_id=None):
#     try:
#         print(f"Entering add_edit_user with user_id: {user_id}")
#
#         # Check if user is logged in and is admin
#         if not (is_login() and (is_admin() or is_executive_approver())):
#             print("User not logged in or not an admin, redirecting to login")
#             return redirect(url_for('login'))
#
#         user = None
#         print("Initialized user as None")
#
#         # Fetch user data if user_id is provided
#         if user_id:
#             query = f"""
#                 SELECT u.name, u.email, u.rights, u.signature, u.scan_sign, u.active, u.created_by, u.created_date,
#                        u.volunteer_id, u.gender, u.dob, u.phone, u.country_of_residence, u.date_of_joining,
#                        u.orientation_completed_on, u.manager_id, u.assigned_branch, u.date_of_retirement, u.reason
#                 FROM tbl_users u
#                 WHERE u.user_id = '{user_id}'
#             """
#             print(f"Executing query to fetch user: {query}")
#             user = fetch_records(query)
#             print(f"Fetched user records: {user}")
#             user = user[0] if user else None
#             print(f"Selected user record: {user}")
#
#         print(f"Current user_id: {user_id}")
#
#         # Handle POST request for adding or editing user
#         if request.method == 'POST':
#             print("Processing POST request")
#             name = request.form.get('name')
#             print(f"Form data - name: {name}")
#             email = request.form.get('email')
#             print(f"Form data - email: {email}")
#             rights = request.form.get('rights')  # Now an integer
#             print(f"Form data - rights: {rights}")
#             signature = request.form.get('signature')
#             print(f"Form data - signature: {signature}")
#             active = request.form.get('active')
#             print(f"Form data - active: {active}")
#             gender = request.form.get('gender')
#             print(f"Form data - gender: {gender}")
#             dob = request.form.get('dob')  # Expected in YYYY-MM-DD format
#             print(f"Form data - dob: {dob}")
#             phone = request.form.get('phone')
#             print(f"Form data - phone: {phone}")
#             country_of_residence = request.form.get('country_of_residence')
#             print(f"Form data - country_of_residence: {country_of_residence}")
#             date_of_joining = request.form.get('date_of_joining')  # Expected in YYYY-MM-DD format
#             print(f"Form data - date_of_joining: {date_of_joining}")
#             orientation_completed_on = request.form.get('orientation_completed_on')  # Expected in YYYY-MM-DD format
#             print(f"Form data - orientation_completed_on: {orientation_completed_on}")
#             manager_id = request.form.get('manager_id')
#             print(f"Form data - manager_id: {manager_id}")
#             assigned_branch = request.form.get('assigned_branch')
#             print(f"Form data - assigned_branch: {assigned_branch}")
#             date_of_retirement = request.form.get('date_of_retirement')
#             print(f"Form data - date_of_retirement: {date_of_retirement}")
#             reason = request.form.get('reason')
#             print(f"Form data - reason: {reason}")
#             scan_sign = request.files.get('scan_sign')
#             print(f"Form data - scan_sign filename: {scan_sign.filename if scan_sign else None}")
#
#             # Handle NULL values for optional fields
#             gender = f"'{gender}'" if gender else 'NULL'
#             print(f"Processed gender: {gender}")
#             dob = f"'{dob}'" if dob else 'NULL'
#             print(f"Processed dob: {dob}")
#             phone = f"'{phone}'" if phone else 'NULL'
#             print(f"Processed phone: {phone}")
#             country_of_residence = f"'{country_of_residence}'" if country_of_residence else 'NULL'
#             print(f"Processed country_of_residence: {country_of_residence}")
#             date_of_joining = f"'{date_of_joining}'" if date_of_joining else 'NULL'
#             print(f"Processed date_of_joining: {date_of_joining}")
#             orientation_completed_on = f"'{orientation_completed_on}'" if orientation_completed_on else 'NULL'
#             print(f"Processed orientation_completed_on: {orientation_completed_on}")
#             manager_id = f"'{manager_id}'" if manager_id else 'NULL'
#             print(f"Processed manager_id: {manager_id}")
#             assigned_branch = f"'{assigned_branch}'" if assigned_branch else 'NULL'
#             print(f"Processed assigned_branch: {assigned_branch}")
#             rights = rights if rights else 'NULL'  # Integer, no quotes
#             print(f"Processed rights: {rights}")
#             signature = f"'{signature}'" if signature else 'NULL'
#             print(f"Processed signature: {signature}")
#             active = f"'{active}'" if active else 'NULL'
#             print(f"Processed active: {active}")
#             date_of_retirement = f"'{date_of_retirement}'" if date_of_retirement else 'NULL'
#             print(f"Processed date_of_retirement: {date_of_retirement}")
#             reason = f"'{reason}'" if reason else 'NULL'
#             print(f"Processed reason: {reason}")
#
#             scan_sign_data = None
#             if scan_sign and scan_sign.filename:
#                 # Convert uploaded file to BYTEA (binary)
#                 scan_sign_data = scan_sign.read()
#                 print(f"Read scan_sign file, size: {len(scan_sign_data)} bytes")
#                 scan_sign_data = psycopg2.Binary(scan_sign_data)
#                 print("Converted scan_sign to psycopg2.Binary")
#
#             if user_id:
#                 # Update existing user
#                 print(f"Updating user with user_id: {user_id}")
#                 if scan_sign_data:
#                     update_query = f"""
#                         UPDATE tbl_users
#                         SET name = '{name}', email = '{email}', rights = {rights}, signature = {signature},
#                             active = {active}, scan_sign = {scan_sign_data}, gender = {gender}, dob = {dob}, phone = {phone},
#                             country_of_residence = {country_of_residence}, date_of_joining = {date_of_joining},
#                             orientation_completed_on = {orientation_completed_on}, manager_id = {manager_id},
#                             date_of_retirement = {date_of_retirement}, reason = {reason},
#                             assigned_branch = {assigned_branch}
#                         WHERE user_id = '{user_id}'
#                     """
#                     print(f"Executing update query with scan_sign: {update_query}")
#                     execute_command(update_query)
#                 else:
#                     update_query = f"""
#                         UPDATE tbl_users
#                         SET name = '{name}', email = '{email}', rights = {rights}, signature = {signature},
#                             active = {active}, gender = {gender}, dob = {dob}, phone = {phone},
#                             country_of_residence = {country_of_residence}, date_of_joining = {date_of_joining},
#                             orientation_completed_on = {orientation_completed_on}, manager_id = {manager_id},
#                             date_of_retirement = {date_of_retirement}, reason = {reason},
#                             assigned_branch = {assigned_branch}
#                         WHERE user_id = '{user_id}'
#                     """
#                     print(f"Executing update query without scan_sign: {update_query}")
#                     execute_command(update_query)
#                 print("User update query executed")
#                 flash('User updated successfully.', 'success')
#                 print("Flashed success message for user update")
#             else:
#                 # Add new user
#                 print("Adding new user")
#                 password = generate_random_password()
#                 print(f"Generated random password: {password}")
#                 hashed_password = generate_password_hash(password)
#                 print("Generated hashed password")
#
#                 if scan_sign_data:
#                     insert_query = f"""
#                         INSERT INTO tbl_users (
#                             name, email, rights, password, signature, scan_sign, active, created_by, created_date,
#                             gender, dob, phone, country_of_residence, date_of_joining, orientation_completed_on,
#                             manager_id, assigned_branch, date_of_retirement, reason
#                         ) VALUES (
#                             '{name}', '{email}', {rights}, '{hashed_password}', {signature}, {scan_sign_data}, {active},
#                             '{str(get_current_user_id())}', '{str(datetime.now())}', {gender}, {dob}, {phone},
#                             {country_of_residence}, {date_of_joining}, {orientation_completed_on},
#                             {manager_id}, {assigned_branch}, {date_of_retirement}, {reason}
#                         )
#                     """
#                     print(f"Executing insert query with scan_sign: {insert_query}")
#                     execute_command(insert_query)
#                 else:
#                     insert_query = f"""
#                         INSERT INTO tbl_users (
#                             name, email, rights, password, signature, active, created_by, created_date,
#                             gender, dob, phone, country_of_residence, date_of_joining, orientation_completed_on,
#                             manager_id, assigned_branch, date_of_retirement, reason
#                         ) VALUES (
#                             '{name}', '{email}', {rights}, '{hashed_password}', {signature}, {active},
#                             '{str(get_current_user_id())}', '{str(datetime.now())}', {gender}, {dob}, {phone},
#                             {country_of_residence}, {date_of_joining}, {orientation_completed_on},
#                             {manager_id}, {assigned_branch}, {date_of_retirement}, {reason}
#                         )
#                     """
#                     print(f"Executing insert query without scan_sign: {insert_query}")
#                     execute_command(insert_query)
#                 print("User insert query executed")
#
#                 # Email content
#                 url = "https://egurantee-hlut.onrender.com/"
#                 subject = "Welcome to eGurantee System"
#                 html_message = f"""
#                            <h3>Here are your credentials</h3>
#                            <p>Email: {email}</p>
#                            <p>Password: {password}</p>
#                            <a href="{url}">You can login through this link.</a>
#                            """
#                 print(f"Prepared email content for {email}")
#
#                 from Model_Email import send_email
#
#                 # Send email using provided function
#                 send_email(subject, [email], None, html_message=html_message)
#                 print(f"Sent email to {email}")
#
#                 flash('User added successfully. Password has been sent to the user.', 'success')
#                 print("Flashed success message for user addition")
#
#             print("Redirecting to manage_users")
#             return redirect(url_for('manage_users'))
#
#         # Handle GET request
#         print("Processing GET request")
#         content = {
#             'get_all_user_data': get_all_user_data(),
#             'get_all_user_privileges': get_all_user_privileges(),
#             'get_all_user_service_terms': get_all_user_service_terms(),
#             'get_all_branch_roles': get_all_branch_roles(),
#             'user': user,
#             'user_id': user_id
#         }
#         print(f"Prepared template content: {content}")
#         return render_template('add_edit_user.html', result=content)
#
#     except Exception as e:
#         print(f"Exception in add_edit_user: {str(e)}")
#         flash('An error occurred while processing the user.', 'danger')
#         print("Flashed error message")
#         return redirect(url_for('manage_users'))


@application.route('/add-edit-user', methods=['GET', 'POST'])
@application.route('/add-edit-user/<int:user_id>', methods=['GET', 'POST'])
def add_edit_user(user_id=None):
    try:
        print(f"Entering add_edit_user with user_id: {user_id}")

        # Check if user is logged in and is admin
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/add-edit-user"))):
            print("User not logged in or not an admin, redirecting to login")
            return redirect(url_for('login'))

        user = None
        print("Initialized user as None")

        # Fetch user data if user_id is provided
        if user_id:
            query = f"""
                SELECT u.name, u.email, u.rights, u.signature, u.scan_sign, u.active, u.created_by, u.created_date,
                       u.volunteer_id, u.gender, u.dob, u.phone, u.country_of_residence, u.date_of_joining,
                       u.orientation_completed_on, u.manager_id, u.assigned_branch, u.date_of_retirement, u.reason
                FROM tbl_users u 
                WHERE u.user_id = '{user_id}'
            """
            print(f"Executing query to fetch user: {query}")
            user = fetch_records(query)
            print(f"Fetched user records: {user}")
            user = user[0] if user else None
            print(f"Selected user record: {user}")

        print(f"Current user_id: {user_id}")

        # Handle POST request for adding or editing user
        if request.method == 'POST':
            print("Processing POST request")
            name = request.form.get('name')
            print(f"Form data - name: {name}")
            email = request.form.get('email')
            print(f"Form data - email: {email}")
            rights = request.form.get('rights')  # Now an integer
            print(f"Form data - rights: {rights}")
            signature = request.form.get('signature')
            print(f"Form data - signature: {signature}")
            active = request.form.get('active')
            print(f"Form data - active: {active}")
            gender = request.form.get('gender')
            print(f"Form data - gender: {gender}")
            dob = request.form.get('dob')  # Expected in YYYY-MM-DD format
            print(f"Form data - dob: {dob}")
            phone = request.form.get('phone')
            print(f"Form data - phone: {phone}")
            country_of_residence = request.form.get('country_of_residence')
            print(f"Form data - country_of_residence: {country_of_residence}")
            date_of_joining = request.form.get('date_of_joining')  # Expected in YYYY-MM-DD format
            print(f"Form data - date_of_joining: {date_of_joining}")
            orientation_completed_on = request.form.get('orientation_completed_on')  # Expected in YYYY-MM-DD format
            print(f"Form data - orientation_completed_on: {orientation_completed_on}")
            manager_id = request.form.get('manager_id')
            print(f"Form data - manager_id: {manager_id}")
            # Get multiple assigned_branch values
            assigned_branches = request.form.getlist('assigned_branch')
            print(f"Form data - assigned_branch: {assigned_branches}")
            date_of_retirement = request.form.get('date_of_retirement')
            print(f"Form data - date_of_retirement: {date_of_retirement}")
            reason = request.form.get('reason')
            print(f"Form data - reason: {reason}")
            scan_sign = request.files.get('scan_sign')
            print(f"Form data - scan_sign filename: {scan_sign.filename if scan_sign else None}")

            # Empty optional fields are stored as NULL. All values are passed as parameters
            # (never pasted into the SQL) to prevent SQL injection.
            def _or_none(v):
                return v if v else None
            gender, dob, phone = _or_none(gender), _or_none(dob), _or_none(phone)
            country_of_residence, date_of_joining = _or_none(country_of_residence), _or_none(date_of_joining)
            orientation_completed_on, manager_id = _or_none(orientation_completed_on), _or_none(manager_id)
            rights, signature, active = _or_none(rights), _or_none(signature), _or_none(active)
            date_of_retirement, reason = _or_none(date_of_retirement), _or_none(reason)
            # integer[] column: psycopg2 sends a Python list as a PostgreSQL array
            assigned_branch = [int(b) for b in assigned_branches] if assigned_branches else None

            scan_sign_data = None
            if scan_sign and scan_sign.filename:
                # Convert uploaded file to BYTEA (binary)
                scan_sign_data = psycopg2.Binary(scan_sign.read())

            if user_id:
                # Update existing user
                sign_sql = 'scan_sign = %s, ' if scan_sign_data else ''
                update_query = f"""
                    UPDATE tbl_users 
                    SET name = %s, email = %s, rights = %s, signature = %s, active = %s, {sign_sql}
                        gender = %s, dob = %s, phone = %s, country_of_residence = %s, date_of_joining = %s,
                        orientation_completed_on = %s, manager_id = %s, date_of_retirement = %s, reason = %s,
                        assigned_branch = %s
                    WHERE user_id = %s
                """
                params = ((name, email, rights, signature, active) + ((scan_sign_data,) if scan_sign_data else ()) +
                          (gender, dob, phone, country_of_residence, date_of_joining, orientation_completed_on,
                           manager_id, date_of_retirement, reason, assigned_branch, user_id))
                execute_command(update_query, params=params)
                print("User update query executed")
                flash('User updated successfully.', 'success')
            else:
                # Add new user
                password = generate_random_password()
                hashed_password = generate_password_hash(password)

                insert_query = """
                    INSERT INTO tbl_users (
                        name, email, rights, password, signature, scan_sign, active, created_by, created_date,
                        gender, dob, phone, country_of_residence, date_of_joining, orientation_completed_on,
                        manager_id, assigned_branch, date_of_retirement, reason
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                execute_command(insert_query, params=(
                    name, email, rights, hashed_password, signature, scan_sign_data, active,
                    str(get_current_user_id()), str(datetime.now()), gender, dob, phone, country_of_residence,
                    date_of_joining, orientation_completed_on, manager_id, assigned_branch, date_of_retirement, reason))
                print("User insert query executed")

                # Email content
                url = "https://egurantee-hlut.onrender.com/"
                subject = "Welcome to eGurantee System"
                html_message = f"""
                           <h3>Here are your credentials</h3>
                           <p>Email: {email}</p>
                           <p>Password: {password}</p>
                           <a href="{url}">You can login through this link.</a>
                           """
                print(f"Prepared email content for {email}")

                from Model_Email import send_email

                # Send email using provided function
                send_email(subject, [email], None, html_message=html_message)
                print(f"Sent email to {email}")

                flash('User added successfully. Password has been sent to the user.', 'success')
                print("Flashed success message for user addition")

            print("Redirecting to manage_users")
            return redirect(url_for('manage_users'))

        # Handle GET request
        print("Processing GET request")
        content = {
            'get_all_user_data': get_all_user_data(),
            'get_all_user_privileges': get_all_user_privileges(),
            'get_all_user_service_terms': get_all_user_service_terms(),
            'get_all_branch_roles': get_all_branch_roles(),
            'user': user,
            'user_id': user_id
        }
        print(f"Prepared template content: {content}")
        return render_template('add_edit_user.html', result=content)

    except Exception as e:
        print(f"Exception in add_edit_user: {str(e)}")
        flash('An error occurred while processing the user.', 'danger')
        print("Flashed error message")
        return redirect(url_for('manage_users'))



@application.route('/add-edit-user-privilege', methods=['GET', 'POST'])
@application.route('/add-edit-user-privilege/<int:privilege_id>', methods=['GET', 'POST'])
def add_edit_user_privilege(privilege_id=None):
    user_id = request.args.get('user_id') or request.form.get('hdn_user_id')
    print('user_id:- ', user_id)

    user_data = get_all_user_data_by_id(user_id)
    user_name = user_data.get('name', '')

    if request.method == 'POST':
        user_id = request.form.get('hdn_user_id')
        role = request.form.get('role')
        responsibility = request.form.get('responsibility')
        committee = request.form.get('committee')
        status = request.form.get('status')
        created_by = str(get_current_user_id())
        modified_by = str(get_current_user_id())
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if privilege_id:
            query = """
                UPDATE tbl_user_privileges
                SET user_id = %s, role = %s, responsibility = %s, committee = %s, status = %s,
                    modified_by = %s, modified_date = %s
                WHERE id = %s
            """
            params = (user_id, role, responsibility, committee, status, modified_by, current_time, privilege_id)
        else:
            query = """
                INSERT INTO tbl_user_privileges (user_id, role, responsibility, committee, status, created_by, created_date, modified_by, modified_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (user_id, role, responsibility, committee, status, created_by, current_time, modified_by, current_time)
        execute_command(query, params=params)
        flash('User privilege saved successfully.', 'success')
        return redirect(url_for('add_edit_user', user_id=user_id) + '#user-privileges')

    privilege = None
    if privilege_id:
        query = f"SELECT * FROM tbl_user_privileges WHERE id = '{privilege_id}' AND status = 1"
        privilege = fetch_records(query)[0] if fetch_records(query) else None

    return render_template('add_edit_user_privilege.html', result={
        'privilege': privilege,
        'privilege_id': privilege_id,
        'hdn_user_id': user_id,
        'user_name': user_name
    })


@application.route('/add_edit_user_service_term', methods=['GET', 'POST'])
@application.route('/add_edit_user_service_term/<int:term_id>', methods=['GET', 'POST'])
def add_edit_user_service_term(term_id=None):

    user_id = request.args.get('user_id') or request.form.get('hdn_user_id')
    print('user_id:- ', user_id)

    user_data = get_all_user_data_by_id(user_id)
    print(user_data)
    user_name = user_data.get('name', '')

    print('user_id:- ', user_id)
    if request.method == 'POST':
        user_id = request.form.get('hdn_user_id')
        term = request.form.get('term')
        tenure_cap = request.form.get('tenure_cap')
        actual_end_date = request.form.get('actual_end_date')
        month_served = request.form.get('month_served')
        from_date = request.form.get('from_date')
        to_date = request.form.get('to_date')
        status = request.form.get('status', 1)  # Default to 1 if not provided
        created_by = str(get_current_user_id())
        modified_by = str(get_current_user_id())
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if term_id:
            query = """
                UPDATE tbl_user_service_terms
                SET user_id = %s, term = %s, from_date = %s, to_date = %s, status = %s,
                    modified_by = %s, modified_date = %s, tenure_cap = %s, actual_end_date = %s, month_served = %s
                WHERE id = %s
            """
            params = (user_id, term, from_date, to_date or None, status, modified_by, current_time,
                      tenure_cap, actual_end_date, month_served, term_id)
        else:
            query = """
                INSERT INTO tbl_user_service_terms (user_id, term, from_date, to_date, status, created_by, created_date, modified_by, modified_date, tenure_cap, actual_end_date, month_served)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (user_id, term, from_date, to_date or None, status, created_by, current_time, modified_by,
                      current_time, tenure_cap, actual_end_date, month_served)
        execute_command(query, params=params)
        flash('User service term saved successfully.', 'success')
        return redirect(url_for('add_edit_user', user_id=user_id) + '#user-service-terms')

    term = None
    if term_id:
        query = f"SELECT * FROM tbl_user_service_terms WHERE id = '{term_id}' AND status = 1"
        term = fetch_records(query)[0] if fetch_records(query) else None

    return render_template('add_edit_user_service_term.html', result={
        'term': term,
        'term_id': term_id,
        'hdn_user_id': user_id,
        'user_name': user_name
    })



@application.route('/delete-user', methods=['GET'])
def delete_user():
    try:
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/delete-user"))):
            return redirect(url_for('login'))

        user_id = request.args.get('user_id')
        if user_id:
            delete_query = """
                UPDATE tbl_users 
                SET active = '0'
                WHERE user_id = %s
            """
            execute_command(delete_query, params=(user_id,))

            flash('User deleted successfully.', 'success')
        else:
            flash('Invalid user ID.', 'danger')

        return redirect(url_for('manage_users'))

    except Exception as e:
        print('delete_user exception:- ', str(e))
        flash('An error occurred while deleting the user.', 'danger')
        return redirect(url_for('manage_users'))


@application.route('/delete-user-privilege', methods=['GET'])
def delete_user_privilege():
    """
    Soft-delete a user privilege by setting status to 0
    """
    try:
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/delete-user-privilege"))):
            return redirect(url_for('login'))

        privilege_id = request.args.get('privilege_id')
        user_id = request.args.get('user_id')

        if privilege_id:
            delete_query = """
                UPDATE tbl_user_privileges 
                SET status = 0
                WHERE id = %s
            """
            execute_command(delete_query, params=(privilege_id,))

            flash('User privilege deleted successfully.', 'success')
        else:
            flash('Invalid privilege ID.', 'danger')

        return redirect(url_for('add_edit_user', user_id=user_id) + '#user-privileges')

    except Exception as e:
        print('delete_user_privilege exception:- ', str(e))
        flash('An error occurred while deleting the user privilege.', 'danger')
        return redirect(url_for('manage_users'))


@application.route('/delete-user-service-term', methods=['GET'])
def delete_user_service_term():
    """
    Soft-delete a user service term by setting status to 0
    """
    try:
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/delete-user-service-term"))):
            return redirect(url_for('login'))

        term_id = request.args.get('term_id')
        user_id = request.args.get('user_id')

        if term_id:
            delete_query = """
                UPDATE tbl_user_service_terms 
                SET status = 0
                WHERE id = %s
            """
            execute_command(delete_query, params=(term_id,))

            flash('User service term deleted successfully.', 'success')
        else:
            flash('Invalid term ID.', 'danger')

        return redirect(url_for('add_edit_user', user_id=user_id) + '#user-service-terms')

    except Exception as e:
        print('delete_term exception:- ', str(e))
        flash('An error occurred while deleting the user service term.', 'danger')
        return redirect(url_for('manage_users'))


@application.route('/get-user-signature/<int:user_id>')
def get_user_signature(user_id):
    try:
        query = f"""
            SELECT scan_sign 
            FROM tbl_users 
            WHERE user_id = '{user_id}' AND active = '1'
        """
        result = fetch_records(query)
        if result and result[0]['scan_sign']:
            # Serve the BYTEA data as an image
            return send_file(
                BytesIO(result[0]['scan_sign']),
                mimetype='image/jpeg',  # Adjust based on your image format (e.g., image/png)
                as_attachment=False
            )
        else:
            return send_file('static/images/placeholder.png', mimetype='image/png')
    except Exception as e:
        print('get_user_signature exception:- ', str(e))
        return send_file('static/images/placeholder.png', mimetype='image/png')