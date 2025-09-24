from imports import *
from application import application
s = URLSafeTimedSerializer(application.config['SECRET_KEY'])


@application.route('/Login', methods=['GET', 'POST'])
@application.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if 'IsLoggedIn' in session and session['IsLoggedIn']:
            return redirect(url_for('index'))
        elif request.method == 'POST':
            email = str(request.form.get('email'))
            password = str(request.form.get('password'))

            query = f"select * from tbl_users u where u.email = '{email}' "
            user = fetch_records(query)
            print(user)

            if user and check_password_hash(user[0]['password'], password):
                print('setting user sessions.')
                set_user_session(user[0])
                print('user sessions has been set.')
                flash(f"Welcome, {user[0]['name']}!", 'success')
                return redirect(url_for('index'))
            else:
                flash(f"Invalid email or password!", 'danger')
                return render_template("Login.html")

    except Exception as e:
        print('login page exception:- ', str(e))

    return render_template("Login.html")


@application.route('/profile', methods=['GET', 'POST'])
def profile():
    try:
        if is_login():
            # query = f"""
            #     SELECT u.name, u.email, u.signature, u.scan_sign
            #     FROM tbl_users u
            #     WHERE u.active = '1' AND u.user_id = '{get_current_user_id()}'
            # """

            query = f"""
                SELECT u."name", u."email", u."signature", u."scan_sign" 
                FROM tbl_users u 
                WHERE u."active" = '1' AND u."user_id" = '{get_current_user_id()}'
            """
            user = fetch_records(query)
            if not user:
                abort(404, description="User not found")
            user = user[0]

            if request.method == 'POST':
                name = request.form['name']
                sql_part = ''

                new_password = request.form.get('password', '')
                if new_password:
                    new_password = generate_password_hash(new_password)
                    # sql_part = f", u.password = '{new_password}'"
                    sql_part = f", \"password\" = '{new_password}'"


                # Handle image upload
                image = request.files.get('image')
                image_data = None
                if image and image.filename:
                    # image_data = binascii.hexlify(image.read()).decode('utf-8')  # Convert to hex string
                    image_data = image.read()
                    
                # query = f"""
                #     UPDATE tbl_users u
                #     SET u.name = '{name}'
                # """
                query = f"""
                    UPDATE tbl_users
                    SET "name" = '{name}'
                """

                if image_data:
                    # query += f", u.scan_sign = 0x{image_data}"  # Prefix with 0x for BLOB
                    query += f', "scan_sign" = {psycopg2.Binary(image_data)}'  # Prefix with 0x for BLOB
                if sql_part:
                    query += sql_part
                # query += f"""
                #     WHERE u.user_id = '{get_current_user_id()}' AND u.active = '1'
                # """
                query += f"""
                    WHERE "user_id" = '{get_current_user_id()}' AND "active" = '1'
                """
                print(query)
                execute_command(query)

                session['name'] = name
                flash("Profile updated successfully.", 'success')
                return redirect(url_for('index'))

            # Convert scan_sign BLOB to base64 for display if it exists
            image_base64 = None
            if user['scan_sign']:
                image_base64 = base64.b64encode(user['scan_sign']).decode('utf-8')

            content = {
                'is_user_have_sign': is_user_have_sign(),
                'user': user,
                'image_base64': image_base64,
            }

            return render_template('profile.html', result=content)
    except Exception as e:
        print('profile page exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/Logout')
@application.route('/logout')
def logout():
    clear_user_session()
    flash("You have been logged out.", 'info')
    return redirect(url_for('login'))


@application.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # Fetch user record using provided query structure
        query = f"""
            SELECT u.name, u.email, u.signature, u.scan_sign 
            FROM tbl_users u 
            WHERE u.active = '1' AND u.email = '{email}'
        """
        user = fetch_records(query)

        if user:
            # Generate reset token
            token = s.dumps(email, salt='password-reset-salt')
            print('token:- ', token)
            reset_url = url_for('reset_password', token=token, _external=True)

            # Email content
            subject = "Password Reset Request"
            html_message = f"""
            <h3>Reset Your Password</h3>
            <p>Click the link below to reset your password. This link will expire in 10 minutes:</p>
            <a href="{reset_url}">Reset Password</a>
            <p>If you did not request a password reset, please ignore this email.</p>
            """

            from Model_Email import send_email

            # Send email using provided function
            if send_email(subject, [email], None, html_message=html_message):
                flash('A password reset link has been sent to your email. It will expire in 10 minutes.', 'success')
            else:
                flash('Failed to send reset email. Please try again.', 'danger')
        else:
            flash('Email not found. Please check your email address.', 'danger')

        return redirect(url_for('login'))

    return render_template('forgot_password.html')


@application.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=600)  # 10 minutes
    except SignatureExpired:
        flash('The password reset link has expired.', 'danger')
        return redirect(url_for('login'))
    except:
        flash('Invalid reset link.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        password = request.form.get('password')
        # Fetch user record to verify email
        query = f"""
            SELECT u.name, u.email, u.signature, u.scan_sign 
            FROM tbl_users u 
            WHERE u.active = '1' AND u.email = '{email}'
        """
        user = fetch_records(query)

        if user:
            # Update password (assuming you have a method to hash and set password)
            hashed_password = generate_password_hash(password)  # Replace with your password hashing method
            update_query = f"""
                UPDATE tbl_users 
                SET password = '{hashed_password}' 
                WHERE email = '{email}' AND active = '1'
            """

            execute_command(update_query)

            flash('Your password has been updated. Please log in.', 'success')
            return redirect(url_for('login'))

        flash('User not found.', 'danger')
        return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)  # You'll need to create this template

