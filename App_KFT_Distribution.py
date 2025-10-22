from imports import *
from application import application


# KFT Distribution Routes
@application.route('/add-kft-distribution', methods=['GET', 'POST'])
@application.route('/edit-kft-distribution/<int:kft_distribution_id>', methods=['GET', 'POST'])
def add_edit_kft_distribution(kft_distribution_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        kft_distribution_details = None
        if kft_distribution_id:
            query = f"""
                SELECT kft_distribution_id, kft_distribution_name, is_active, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_kft_distribution 
                WHERE kft_distribution_id = {kft_distribution_id} AND status != 3
            """
            result = fetch_records(query)
            kft_distribution_details = result[0] if result else None
            if not kft_distribution_details:
                return redirect(url_for('manage_branches') + "#kft-distributions")

        if request.method == 'POST':
            kft_distribution_name = request.form.get('kft_distribution_name')
            is_active = request.form.get('is_active')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            kft_distribution_name_escaped = escape_sql_string(kft_distribution_name)

            if kft_distribution_id:
                query = f"""
                    UPDATE tbl_kft_distribution 
                    SET kft_distribution_name = {kft_distribution_name_escaped},
                        is_active = {is_active},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE kft_distribution_id = {kft_distribution_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_kft_distribution 
                    (kft_distribution_name, is_active, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({kft_distribution_name_escaped}, {is_active}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING kft_distribution_id
                """
                execute_command(query)
            return redirect(url_for('manage_branches') + "#kft-distributions")

        return render_template('add_edit_kft_distribution.html',
                             result={'kft_distribution_details': kft_distribution_details,
                                    'get_all_kft_distributions': get_all_kft_distributions()})
    except Exception as e:
        print('add/edit kft distribution exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-kft-distribution/<int:kft_distribution_id>', methods=['POST', 'GET'])
def delete_kft_distribution(kft_distribution_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_kft_distribution 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE kft_distribution_id = {kft_distribution_id}
        """
        execute_command(query)
        return redirect(url_for('manage_branches') + "#kft-distributions")
    except Exception as e:
        print('delete kft distribution exception:- ', str(e))
        return redirect(url_for('login'))
