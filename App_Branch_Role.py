from imports import *
from application import application


# Branch Role Routes
@application.route('/add-branch-role', methods=['GET', 'POST'])
@application.route('/edit-branch-role/<int:branch_role_id>', methods=['GET', 'POST'])
def add_edit_branch_role(branch_role_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        branch_role_details = None
        if branch_role_id:
            query = f"""
                SELECT branch_role_id, branch_role_name, is_active, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_branch_role 
                WHERE branch_role_id = {branch_role_id} AND status != 3
            """
            result = fetch_records(query)
            branch_role_details = result[0] if result else None
            if not branch_role_details:
                return redirect(url_for('manage_branches') + "#branch-roles")

        if request.method == 'POST':
            branch_role_name = request.form.get('branch_role_name')
            is_active = request.form.get('is_active')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            branch_role_name_escaped = escape_sql_string(branch_role_name)

            if branch_role_id:
                query = f"""
                    UPDATE tbl_branch_role 
                    SET branch_role_name = {branch_role_name_escaped},
                        is_active = {is_active},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE branch_role_id = {branch_role_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_branch_role 
                    (branch_role_name, is_active, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({branch_role_name_escaped}, {is_active}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING branch_role_id
                """
                execute_command(query)
            return redirect(url_for('manage_branches') + "#branch-roles")

        return render_template('add_edit_branch_role.html',
                             result={'branch_role_details': branch_role_details,
                                    'get_all_branch_roles': get_all_branch_roles()})
    except Exception as e:
        print('add/edit branch role exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-branch-role/<int:branch_role_id>', methods=['POST', 'GET'])
def delete_branch_role(branch_role_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_branch_role 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE branch_role_id = {branch_role_id}
        """
        execute_command(query)
        return redirect(url_for('manage_branches') + "#branch-roles")
    except Exception as e:
        print('delete branch role exception:- ', str(e))
        return redirect(url_for('login'))
