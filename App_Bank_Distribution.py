from imports import *
from application import application


# Bank Distribution Routes
@application.route('/add-bank-distribution', methods=['GET', 'POST'])
@application.route('/edit-bank-distribution/<int:bank_distribution_id>', methods=['GET', 'POST'])
def add_edit_bank_distribution(bank_distribution_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        bank_distribution_details = None

        if bank_distribution_id:
            query = f"""
                SELECT bank_distribution_id, bank_distribution_name, is_active, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_bank_distribution 
                WHERE bank_distribution_id = {bank_distribution_id} AND status != 3
            """
            result = fetch_records(query)
            bank_distribution_details = result[0] if result else None

            if not bank_distribution_details:
                return redirect(url_for('manage_branches') + "#bank-distributions")

        if request.method == 'POST':
            bank_distribution_name = request.form.get('bank_distribution_name')
            is_active = request.form.get('is_active')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            bank_distribution_name_escaped = escape_sql_string(bank_distribution_name)

            if bank_distribution_id:
                query = f"""
                    UPDATE tbl_bank_distribution 
                    SET bank_distribution_name = {bank_distribution_name_escaped},
                        is_active = {is_active},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE bank_distribution_id = {bank_distribution_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_bank_distribution 
                    (bank_distribution_name, is_active, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({bank_distribution_name_escaped}, {is_active}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING bank_distribution_id
                """
                execute_command(query)
            return redirect(url_for('manage_branches') + "#bank-distributions")

        return render_template('add_edit_bank_distribution.html',
                             result={'bank_distribution_details': bank_distribution_details,
                                    'get_all_bank_distributions': get_all_bank_distributions()})
    except Exception as e:
        print('add/edit bank distribution exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-bank-distribution/<int:bank_distribution_id>', methods=['POST', 'GET'])
def delete_bank_distribution(bank_distribution_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_bank_distribution 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE bank_distribution_id = {bank_distribution_id}
        """
        execute_command(query)
        return redirect(url_for('manage_branches') + "#bank-distributions")
    except Exception as e:
        print('delete bank distribution exception:- ', str(e))
        return redirect(url_for('login'))
