from imports import *
from application import application


@application.route('/manage-self-update-community')
def manage_self_update_community():
    try:
        if is_login():
            user_id = get_current_user_id()
            if not user_id:
                raise ValueError("No user_id found for current user")
            content = {
                'get_user_cumm_service_hours': get_user_comm_svc_hours_by_user_id(user_id),
                'get_all_user_privileges_by_user_id': get_all_user_privileges_by_user_id(user_id),
                'volunteer_info': get_all_user_data_by_id(user_id),
            }
            return render_template('manage_self_update_community.html', result=content)
    except Exception as e:
        print('manage-self-update-community exception:- ', str(e))
        print('manage-self-update-community exception:- ', str(e.__dict__))
    return redirect(url_for('login'))

@application.route('/add-user-comm-svc-hours', methods=['GET', 'POST'])
@application.route('/edit-user-comm-svc-hours/<int:cum_sev_hr_id>', methods=['GET', 'POST'])
def add_edit_user_comm_svc_hours(cum_sev_hr_id=None):
    try:
        if not is_login():
            return jsonify({'error': 'Unauthorized'}), 401

        comm_svc_details = None

        if cum_sev_hr_id:
            query = f"""
                SELECT cum_sev_hr_id, user_id, hours_contributed, service_category, brief_key_activities, 
                       status, created_by, TO_CHAR(month_year, 'YYYY-MM') AS month_year, 
                       created_date, modified_by, modified_date
                FROM tbl_user_comm_svc_hours 
                WHERE cum_sev_hr_id = {cum_sev_hr_id} AND status != '2'
            """
            result = fetch_records(query)
            comm_svc_details = result[0] if result else None
            if not comm_svc_details:
                return jsonify({'error': 'Record not found'}), 404

        if request.method == 'POST':
            user_id = str(get_current_user_id())
            hours_contributed = request.form['hours_contributed']
            service_category = request.form['service_category']
            brief_key_activities = request.form.get('brief_key_activities') or None
            month_year = request.form.get('month_year') or None
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Convert month_year (YYYY-MM) to a valid DATE (YYYY-MM-01)
            month_year_date = f"{month_year}-01" if month_year else None

            user_id = int(user_id)
            hours_contributed = int(hours_contributed)
            if user_id <= 0 or hours_contributed < 0:
                return jsonify({'error': 'Invalid user_id or hours_contributed'}), 400
            if not month_year:
                return jsonify({'error': 'Month/Year is required'}), 400

            if cum_sev_hr_id:
                # Values are passed as parameters (never pasted into the SQL) to prevent SQL injection
                query = """
                    UPDATE tbl_user_comm_svc_hours 
                    SET user_id = %s, hours_contributed = %s, service_category = %s, brief_key_activities = %s,
                        month_year = %s, status = %s, modified_by = %s, modified_date = %s
                    WHERE cum_sev_hr_id = %s
                """
                execute_command(query, params=(user_id, hours_contributed, service_category, brief_key_activities,
                                               month_year_date, status, current_user_id, current_time, cum_sev_hr_id))
            else:
                query = """
                    INSERT INTO tbl_user_comm_svc_hours 
                    (user_id, hours_contributed, service_category, brief_key_activities, month_year, status, 
                     created_by, created_date, modified_by, modified_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING cum_sev_hr_id
                """
                execute_command(query, params=(user_id, hours_contributed, service_category, brief_key_activities,
                                               month_year_date, status, current_user_id, current_time,
                                               current_user_id, current_time))
            return jsonify({'success': 'Community service hours saved'}), 200

        return render_template('manage_self_update_community.html',
                              result={'comm_svc_details': comm_svc_details,
                                      'get_user_cumm_service_hours': get_user_comm_svc_hours_by_user_id(get_current_user_id())})
    except Exception as e:
        print('add/edit community service hours exception:- ', str(e))
        return jsonify({'error': str(e)}), 500

@application.route('/delete-user-comm-svc-hours/<int:cum_sev_hr_id>', methods=['POST', 'GET'])
def delete_user_comm_svc_hours(cum_sev_hr_id):
    try:
        if not is_login():
            return jsonify({'error': 'Unauthorized'}), 401

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_user_comm_svc_hours 
            SET status = '2', 
                modified_by = {current_user_id}, 
                modified_date = '{current_time}'
            WHERE cum_sev_hr_id = {cum_sev_hr_id}
        """
        execute_command(query)
        return jsonify({'success': 'Community service hours deleted'}), 200
    except Exception as e:
        print('delete community service hours exception:- ', str(e))
        return jsonify({'error': str(e)}), 500