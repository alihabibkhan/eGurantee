from imports import *
from application import application


@application.route('/manage-branches')
def manage_branches():
    try:
        if is_login() and is_admin():
            content = {'get_all_branches_info': get_all_branches_info()}
            return render_template('manage_branches.html', result=content)
    except Exception as e:
        print('manage branches exception:- ', str(e))
        print('manage branches exception:- ', str(e.__dict__))
    return redirect(url_for('login'))


@application.route('/add-branch', methods=['GET', 'POST'])
@application.route('/edit-branch/<int:branch_id>', methods=['GET', 'POST'])
def add_edit_branch(branch_id=None):
    try:
        if not (is_login() and is_admin()):
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

            # Escape string inputs to prevent SQL injection
            branch_code_escaped = escape_sql_string(branch_code)
            branch_name_escaped = escape_sql_string(branch_name)
            role_escaped = escape_sql_string(role)
            area_escaped = escape_sql_string(area)
            email_escaped = escape_sql_string(email)
            bank_distribution_escaped = escape_sql_string(bank_distribution)
            kft_distribution_escaped = escape_sql_string(kft_distribution)
            national_council_distribution_escaped = escape_sql_string(national_council_distribution)

            if branch_id:
                # Update existing record
                query = f"""
                    UPDATE tbl_branches 
                    SET branch_code = {branch_code_escaped},
                        branch = '{branch}',
                        branch_name = {branch_name_escaped},
                        role = {role_escaped},
                        area = {area_escaped},
                        area_name = '{area_name}',
                        branch_manager = '{branch_manager}',
                        email = {email_escaped},
                        bank_id = {bank_id},
                        bank_distribution = {bank_distribution_escaped},
                        kft_distribution = {kft_distribution_escaped},
                        national_council_distribution = {national_council_distribution_escaped},
                        live_branch = '{live_branch}',
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE branch_id = {branch_id}
                """
                execute_command(query)
            else:
                # Insert new record
                query = f"""
                    INSERT INTO tbl_branches 
                    (branch_code, branch_name, role, area, email, bank_id, bank_distribution, 
                     kft_distribution, national_council_distribution, live_branch, 
                     created_by, created_date, modified_by, modified_date, area_name, branch, branch_manager)
                    VALUES ({branch_code_escaped}, {branch_name_escaped}, {role_escaped}, 
                            {area_escaped}, {email_escaped}, {bank_id}, {bank_distribution_escaped}, 
                            {kft_distribution_escaped}, {national_council_distribution_escaped}, 
                            '{live_branch}', {current_user_id}, '{current_time}', 
                            {current_user_id}, '{current_time}', '{area_name}', '{branch}', '{branch_manager}')
                    RETURNING branch_id
                """
                execute_command(query)
            return redirect(url_for('manage_branches'))

        # Render form for GET request
        return render_template('add_edit_branch.html', result={'branch_details': branch_details, 'bank_details': bank_details})
    except Exception as e:
        print('add/edit branch exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-branch/<int:branch_id>', methods=['POST', 'GET'])
def delete_branch(branch_id):
    try:
        if not (is_login() and is_admin()):
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