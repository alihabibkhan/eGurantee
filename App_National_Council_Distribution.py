from imports import *
from application import application


# National Council Distribution Routes
@application.route('/add-national-council-distribution', methods=['GET', 'POST'])
@application.route('/edit-national-council-distribution/<int:national_council_distribution_id>', methods=['GET', 'POST'])
def add_edit_national_council_distribution(national_council_distribution_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/add-national-council-distribution"))):
            return redirect(url_for('login'))

        national_council_distribution_details = None
        if national_council_distribution_id:
            query = f"""
                SELECT national_council_distribution_id, national_council_distribution_name, is_active, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_national_council_distribution 
                WHERE national_council_distribution_id = {national_council_distribution_id} AND status != 3
            """
            result = fetch_records(query)
            national_council_distribution_details = result[0] if result else None
            if not national_council_distribution_details:
                return redirect(url_for('manage_branches') + "#national-council-distributions")

        if request.method == 'POST':
            national_council_distribution_name = request.form.get('national_council_distribution_name')
            is_active = request.form.get('is_active')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if national_council_distribution_id:
                query = """
                    UPDATE tbl_national_council_distribution 
                    SET national_council_distribution_name = %s, is_active = %s, status = %s,
                        modified_by = %s, modified_date = %s
                    WHERE national_council_distribution_id = %s
                """
                execute_command(query, params=(national_council_distribution_name, is_active, status, current_user_id, current_time, national_council_distribution_id))
            else:
                query = """
                    INSERT INTO tbl_national_council_distribution 
                    (national_council_distribution_name, is_active, status, created_by, created_date, modified_by, modified_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING national_council_distribution_id
                """
                execute_command(query, params=(national_council_distribution_name, is_active, status, current_user_id, current_time, current_user_id, current_time))
            return redirect(url_for('manage_branches') + "#national-council-distributions")

        return render_template('add_edit_national_council_distribution.html',
                             result={'national_council_distribution_details': national_council_distribution_details,
                                    'get_all_national_council_distributions': get_all_national_council_distributions()})
    except Exception as e:
        print('add/edit national council distribution exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-national-council-distribution/<int:national_council_distribution_id>', methods=['POST', 'GET'])
def delete_national_council_distribution(national_council_distribution_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/delete-national-council-distribution"))):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_national_council_distribution 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE national_council_distribution_id = {national_council_distribution_id}
        """
        execute_command(query)
        return redirect(url_for('manage_branches') + "#national-council-distributions")
    except Exception as e:
        print('delete national council distribution exception:- ', str(e))
        return redirect(url_for('login'))
