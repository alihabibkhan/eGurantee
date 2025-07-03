from imports import *
from application import application


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
            # print(user)

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

            return render_template('profile.html', user=user, image_base64=image_base64)
    except Exception as e:
        print('profile page exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/logout')
def logout():
    clear_user_session()
    flash("You have been logged out.", 'info')
    return redirect(url_for('login'))

