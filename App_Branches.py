from imports import *
from application import application


@application.route('/manage-branches')
def manage_branches():
    try:
        if is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/manage-branches")):
            content = {
                'get_all_branches_info': get_all_branches_info(),
                'get_all_bank_distributions': get_all_bank_distributions(),
                'get_all_national_council_distributions': get_all_national_council_distributions(),
                'get_all_kft_distributions': get_all_kft_distributions(),
                'get_all_branch_roles': get_all_branch_roles()
            }
            return render_template('manage_branches.html', result=content)
    except Exception as e:
        print('manage branches exception:- ', str(e))
        print('manage branches exception:- ', str(e.__dict__))
    return redirect(url_for('login'))


@application.route('/add-branch', methods=['GET', 'POST'])
@application.route('/edit-branch/<int:branch_id>', methods=['GET', 'POST'])
def add_edit_branch(branch_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/add-branch"))):
            return redirect(url_for('login'))

        branch_details = None
        bank_details = get_all_bank_details()  # Fetch all active banks for dropdown
        if branch_id:
            # Fetch existing record for editing
            query = f"""
                SELECT branch_id, branch, branch_code, branch_name, role, area, area_name, branch_manager, email, bank_id, 
                       bank_distribution, kft_distribution, national_council_distribution, 
                       live_branch, created_by, created_date, modified_by, modified_date
                FROM tbl_branches 
                WHERE branch_id = {branch_id} AND live_branch != 3
            """
            result = fetch_records(query)
            branch_details = result[0] if result else None
            if not branch_details:
                return redirect(url_for('manage_branches'))

        if request.method == 'POST':
            # Get form data
            branch = request.form['branch']
            branch_code = request.form['branch_code']
            branch_name = request.form['branch_name']
            role = request.form['role']
            area = request.form['area']
            area_name = request.form['area_name']
            branch_manager = request.form['branch_manager']
            email = request.form['email']
            bank_id = request.form['bank_id']
            bank_distribution = request.form['bank_distribution'] or None
            kft_distribution = request.form['kft_distribution'] or None
            national_council_distribution = request.form['national_council_distribution'] or None
            live_branch = request.form['live_branch']
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Values are passed as parameters (never pasted into the SQL) to prevent SQL injection
            if branch_id:
                # Update existing record
                query = """
                    UPDATE tbl_branches
                    SET branch_code = %s, branch = %s, branch_name = %s, role = %s, area = %s, area_name = %s,
                        branch_manager = %s, email = %s, bank_id = %s, bank_distribution = %s, kft_distribution = %s,
                        national_council_distribution = %s, live_branch = %s, modified_by = %s, modified_date = %s
                    WHERE branch_id = %s
                """
                execute_command(query, params=(branch_code, branch, branch_name, role, area, area_name, branch_manager, email,
                                               bank_id, bank_distribution, kft_distribution, national_council_distribution,
                                               live_branch, current_user_id, current_time, branch_id))
            else:
                # Insert new record
                query = """
                    INSERT INTO tbl_branches
                    (branch_code, branch_name, role, area, email, bank_id, bank_distribution,
                     kft_distribution, national_council_distribution, live_branch,
                     created_by, created_date, modified_by, modified_date, area_name, branch, branch_manager)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING branch_id
                """
                execute_command(query, params=(branch_code, branch_name, role, area, email, bank_id, bank_distribution,
                                               kft_distribution, national_council_distribution, live_branch,
                                               current_user_id, current_time, current_user_id, current_time,
                                               area_name, branch, branch_manager))
            return redirect(url_for('manage_branches'))

        content = {
            'branch_details': branch_details,
            'get_all_branches_info': get_all_branches_info(),
            'get_all_bank_distributions': get_all_bank_distributions(),
            'get_all_national_council_distributions': get_all_national_council_distributions(),
            'get_all_kft_distributions': get_all_kft_distributions(),
            'get_all_branch_roles': get_all_branch_roles(),
            'bank_details': bank_details
        }

        # Render form for GET request
        return render_template('add_edit_branch.html', result=content)
    except Exception as e:
        print('add/edit branch exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-branch/<int:branch_id>', methods=['POST', 'GET'])
def delete_branch(branch_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/delete-branch"))):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_branches 
            SET live_branch = 3, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE branch_id = {branch_id}
        """
        execute_command(query)
        return redirect(url_for('manage_branches'))
    except Exception as e:
        print('delete branch exception:- ', str(e))
        return redirect(url_for('login'))