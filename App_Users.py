from imports import *
from application import application


def generate_random_password():
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(11))
    return password


@application.route('/manage_users')
def manage_users():
    try:
        if is_login() and is_admin():
            content = {
                'get_all_user_data': get_all_user_data(),
                'get_all_branches_info': get_all_branches_info()
            }
            return render_template('manage_users.html', result=content)
    except Exception as e:
        print('manage users exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/add-edit-user', methods=['GET', 'POST'])
@application.route('/add-edit-user/<int:user_id>', methods=['GET', 'POST'])
def add_edit_user(user_id=None):
    try:
        if not is_login() or not is_admin():
            return redirect(url_for('login'))

        user = None

        print('user_id:- ', user_id)

        if user_id:
            query = f"""
                SELECT u.name, u.email, u.role, u.signature, u.scan_sign, u.active, u.created_by, u.created_date
                FROM tbl_users u 
                WHERE u.user_id = '{user_id}' AND u.active = '1'
            """
            print(query)
            user = fetch_records(query)
            user = user[0] if user else None

            print('user record')
            print(user)

        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            role = request.form.get('role')
            signature = request.form.get('signature')
            active = request.form.get('active')
            scan_sign = request.files.get('scan_sign')

            scan_sign_data = None
            if scan_sign and scan_sign.filename:
                # Convert uploaded file to BYTEA (binary)
                scan_sign_data = scan_sign.read()
                scan_sign_data = psycopg2.Binary(scan_sign_data)

            if user_id:
                # Update existing user
                if scan_sign_data:
                    update_query = f"""
                        UPDATE tbl_users 
                        SET name = '{name}', email = '{email}', role = '{role}', 
                            signature = '{signature}', active = '{active}', scan_sign = %s
                        WHERE user_id = '{user_id}'
                    """
                    execute_command(update_query)
                else:
                    update_query = f"""
                        UPDATE tbl_users 
                        SET name = '{name}', email = '{email}', role = '{role}', 
                            signature = '{signature}', active = '{active}'
                        WHERE user_id = '{user_id}'
                    """
                    execute_command(update_query)
                flash('User updated successfully.', 'success')
            else:
                # Add new user
                password = generate_random_password()
                hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

                if scan_sign_data:
                    insert_query = f"""
                        INSERT INTO tbl_users (
                            name, email, role, password, signature, scan_sign, active, created_by, created_date
                        ) VALUES (
                            '{name}', '{email}', '{role}', '{hashed_password}', '{signature}', %s, 
                            '{active}', '{str(get_current_user_id())}', '{str(datetime.now())}'
                        )
                    """
                    execute_command(insert_query)
                else:
                    insert_query = f"""
                        INSERT INTO tbl_users (
                            name, email, role, password, signature, scan_sign, active, created_by, created_date
                        ) VALUES (
                            '{name}', '{email}', '{role}', '{password}', '{signature}', NULL, 
                            '{active}', '{str(get_current_user_id())}', '{str(datetime.now())}'
                        )
                    """
                    execute_command(insert_query)

                    # Email content
                    url = "https://egurantee-3.onrender.com/"
                    subject = "Welcome to eGurantee System"
                    html_message = f"""
                               <h3>Here are your credentials</h3>
                               <p>Email: {email}</p>
                               <p>Email: {password}</p>
                               <a href="{url}">You can login through this link.</a>
                               """

                    from Model_Email import send_email

                    # Send email using provided function
                    send_email(subject, [email], None, html_message=html_message)

                flash('User added successfully. Password has been sent to the user.', 'success')


            return redirect(url_for('manage_users'))

        content = {
            'get_all_user_data': get_all_user_data(),
            'get_all_branches_info': get_all_branches_info(),
            'user': user,
            'user_id': user_id
        }
        return render_template('add_edit_user.html', result=content)

    except Exception as e:
        print('add_edit_user exception:- ', str(e))
        flash('An error occurred while processing the user.', 'danger')
        return redirect(url_for('manage_users'))


@application.route('/delete-user', methods=['GET'])
def delete_user():
    try:
        if not is_login() or not is_admin():
            return redirect(url_for('login'))

        user_id = request.args.get('user_id')
        if user_id:
            delete_query = f"""
                UPDATE tbl_users 
                SET active = '0'
                WHERE user_id = '{user_id}'
            """
            execute_command(delete_query)

            flash('User deleted successfully.', 'success')
        else:
            flash('Invalid user ID.', 'danger')

        return redirect(url_for('manage_users'))

    except Exception as e:
        print('delete_user exception:- ', str(e))
        flash('An error occurred while deleting the user.', 'danger')
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