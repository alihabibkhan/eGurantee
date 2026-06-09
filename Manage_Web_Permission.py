from imports import *
from application import application


# ====================== MANAGE WEB PERMISSIONS ======================
@application.route('/manage-web-permissions')
def manage_web_permissions():
    try:
        if not (is_login() and is_admin()):   # Only Admin should manage permissions
            return redirect(url_for('login'))

        query = """
            SELECT web_permission_id, category, title, route, permission_key, description, 
                   status, created_date, modified_date
            FROM tbl_web_permissions 
            ORDER BY title ASC
        """
        permissions = fetch_records(query)

        content = {'permissions': permissions}
        return render_template('manage_web_permissions.html', result=content)

    except Exception as e:
        print('manage_web_permissions exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/add-web-permission', methods=['GET', 'POST'])
@application.route('/edit-web-permission/<int:permission_id>', methods=['GET', 'POST'])
def add_edit_web_permission(permission_id=None):
    try:
        if not (is_login() and is_admin()):
            return redirect(url_for('login'))

        permission = None
        if permission_id:
            query = f"""
                SELECT web_permission_id, category, title, route, permission_key, description, status
                FROM tbl_web_permissions 
                WHERE web_permission_id = {permission_id}
            """
            result = fetch_records(query)
            permission = result[0] if result else None
            if not permission:
                return redirect(url_for('manage_web_permissions'))

        if request.method == 'POST':
            category = request.form['category']
            title = request.form['title']
            route = request.form['route']
            permission_key = request.form['permission_key']
            description = request.form.get('description', '')
            status = request.form['status']

            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Escape strings safely
            category_esc = escape_sql_string(category)
            title_esc = escape_sql_string(title)
            route_esc = escape_sql_string(route)
            permission_key_esc = escape_sql_string(permission_key)
            description_esc = escape_sql_string(description)

            if permission_id:
                # Update
                query = f"""
                    UPDATE tbl_web_permissions 
                    SET category = {category_esc},
                        title = {title_esc},
                        route = {route_esc},
                        permission_key = {permission_key_esc},
                        description = {description_esc},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE web_permission_id = {permission_id}
                """
                execute_command(query)
            else:
                # Insert
                query = f"""
                    INSERT INTO tbl_web_permissions 
                    (category, title, route, permission_key, description, status, 
                     created_by, created_date, modified_by, modified_date)
                    VALUES ({category_esc}, {title_esc}, {route_esc}, {permission_key_esc}, {description_esc}, 
                            {status}, {current_user_id}, '{current_time}', 
                            {current_user_id}, '{current_time}')
                    RETURNING web_permission_id
                """
                execute_command(query)

            return redirect(url_for('manage_web_permissions'))

        return render_template('add_edit_web_permission.html', result={'permission': permission})

    except Exception as e:
        print('add_edit_web_permission exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-web-permission/<int:permission_id>', methods=['POST'])
def delete_web_permission(permission_id):
    try:
        if not (is_login() and is_admin()):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        query = f"""
            UPDATE tbl_web_permissions 
            SET status = 0, 
                modified_by = {current_user_id}, 
                modified_date = '{current_time}'
            WHERE web_permission_id = {permission_id}
        """
        execute_command(query)

        return redirect(url_for('manage_web_permissions'))

    except Exception as e:
        print('delete_web_permission exception:- ', str(e))
        return redirect(url_for('login'))