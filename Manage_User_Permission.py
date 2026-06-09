from imports import *
from application import application
from datetime import datetime


# ====================== MANAGE USER PERMISSIONS ======================
@application.route('/manage-user-permissions')
def manage_user_permissions():
    try:
        if not (is_login() and is_admin()):
            return redirect(url_for('login'))

        query = """
            SELECT up.user_permission_id, u.user_id, u.name, u.email, 
                   wp.title, wp.route, wp.permission_key,
                   up.status, up.granted_date
            FROM tbl_user_permissions up
            JOIN tbl_web_permissions wp ON up.web_permission_id = wp.web_permission_id
            JOIN tbl_users u ON up.user_id = u.user_id          -- Change 'users' table name if different
            WHERE wp.status = 1 and up.Status = 1
            ORDER BY u.name, wp.title
        """
        user_permissions = fetch_records(query)

        # Get all users for dropdown
        users_query = "SELECT user_id, name, email, rights FROM tbl_users ORDER BY name"
        all_users = fetch_records(users_query)

        # Get all active web permissions for dropdown
        permissions_query = """
            SELECT web_permission_id, title, route 
            FROM tbl_web_permissions 
            WHERE status = 1 
            ORDER BY title
        """
        all_permissions = fetch_records(permissions_query)

        content = {
            'user_permissions': user_permissions,
            'all_users': all_users,
            'all_permissions': all_permissions
        }
        return render_template('manage_user_permissions.html', result=content)

    except Exception as e:
        print('manage_user_permissions exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/add-user-permission', methods=['POST'])
def add_user_permission():
    try:
        if not (is_login() and is_admin()):
            return redirect(url_for('login'))

        role_id = request.form.get('role_id')
        user_ids = request.form.getlist('user_ids')  # Multiple user IDs
        web_permission_id = request.form['web_permission_id']

        if not user_ids or not web_permission_id:
            flash('Please select users and permission', 'error')
            return redirect(url_for('manage_user_permissions'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        success_count = 0

        for user_id in user_ids:
            # Check if already exists
            check_query = f"""
                SELECT 1 FROM tbl_user_permissions 
                WHERE user_id = {user_id} AND web_permission_id = {web_permission_id}
            """
            if fetch_records(check_query):
                # Already exists → just activate it
                query = f"""
                    UPDATE tbl_user_permissions 
                    SET status = 1, granted_by = {current_user_id}, granted_date = '{current_time}'
                    WHERE user_id = {user_id} AND web_permission_id = {web_permission_id}
                """
            else:
                # Insert new
                query = f"""
                    INSERT INTO tbl_user_permissions 
                    (user_id, web_permission_id, granted_by, granted_date, status)
                    VALUES ({user_id}, {web_permission_id}, {current_user_id}, '{current_time}', 1)
                """

            try:
                execute_command(query)
                success_count += 1
            except Exception as e:
                print(f"Error assigning permission to user {user_id}: {str(e)}")

        if success_count > 0:
            flash(f'Successfully assigned permission to {success_count} user(s)', 'success')
        else:
            flash('Failed to assign permissions', 'error')

        return redirect(url_for('manage_user_permissions'))

    except Exception as e:
        print('add_user_permission exception:- ', str(e))
        flash('An error occurred while assigning permissions', 'error')
        return redirect(url_for('login'))


@application.route('/revoke-user-permissions', methods=['POST'])
def revoke_user_permissions():
    try:
        if not (is_login() and is_admin()):
            return redirect(url_for('login'))

        user_permission_ids = request.form.getlist('user_permission_ids')

        if not user_permission_ids:
            flash('No permissions selected for revocation', 'error')
            return redirect(url_for('manage_user_permissions'))

        success_count = 0
        for user_permission_id in user_permission_ids:
            query = f"""
                UPDATE tbl_user_permissions 
                SET status = 0
                WHERE user_permission_id = {user_permission_id}
            """
            try:
                execute_command(query)
                success_count += 1
            except Exception as e:
                print(f"Error revoking permission {user_permission_id}: {str(e)}")

        if success_count > 0:
            flash(f'Successfully revoked {success_count} permission(s)', 'success')
        else:
            flash('Failed to revoke permissions', 'error')

        return redirect(url_for('manage_user_permissions'))

    except Exception as e:
        print('revoke_user_permissions exception:- ', str(e))
        flash('An error occurred while revoking permissions', 'error')
        return redirect(url_for('login'))