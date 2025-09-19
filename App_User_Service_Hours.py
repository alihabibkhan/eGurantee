from imports import *
from application import application


@application.route('/manage-user-service-hours')
def manage_user_service_hours():
    try:
        if is_login() and is_admin():
            user_id = get_current_user_id()
            if not user_id:
                raise ValueError("No user_id found for current user")
            content = {
                'get_user_service_hours': get_user_service_hours_by_user_id(user_id),
                'get_all_user_privileges_by_user_id': get_all_user_privileges_by_user_id(user_id),
                'volunteer_info': get_all_user_data_by_id(user_id)
            }

            return render_template('manage_user_service_hours.html', result=content)
    except Exception as e:
        print('manage user service hours exception:- ', str(e))
        print('manage user service hours exception:- ', str(e.__dict__))
    return redirect(url_for('login'))


@application.route('/add-user-service-hours', methods=['GET', 'POST'])
@application.route('/edit-user-service-hours/<int:user_service_hours_id>', methods=['GET', 'POST'])
def add_edit_user_service_hours(user_service_hours_id=None):
    try:
        if not (is_login() and is_admin()):
            return jsonify({'error': 'Unauthorized'}), 401

        service_hours_details = None

        print('service_hours_details:- ', service_hours_details)
        print('user_service_hours_id:- ', user_service_hours_id)

        if user_service_hours_id:
            query = f"""
                SELECT user_service_hours_id, user_id, service_hours, service_category, description, 
                       status, created_by, created_date, modified_by, modified_date
                FROM tbl_user_service_hours 
                WHERE user_service_hours_id = {user_service_hours_id} AND status != '2'
            """
            result = fetch_records(query)
            service_hours_details = result[0] if result else None
            if not service_hours_details:
                return jsonify({'error': 'Record not found'}), 404

        if request.method == 'POST':
            user_id = str(get_current_user_id())
            service_hours = request.form['service_hours']
            service_category = request.form['service_category']
            description = request.form.get('description') or None
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            print(user_id, service_hours, service_category, description)

            service_category_escaped = escape_sql_string(service_category)
            description_escaped = escape_sql_string(description) if description else 'NULL'
            status_escaped = escape_sql_string(status)

            print(user_id, service_hours, service_category, description)

            user_id = int(user_id)
            service_hours = int(service_hours)
            if user_id <= 0 or service_hours < 0:
                print('Invalid user_id or service_hours')
                return jsonify({'error': 'Invalid user_id or service_hours'}), 400

            if user_service_hours_id:
                print('Updating the record.')
                query = f"""
                    UPDATE tbl_user_service_hours 
                    SET user_id = {user_id},
                        service_hours = {service_hours},
                        service_category = {service_category_escaped},
                        description = {description_escaped},
                        status = {status_escaped},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE user_service_hours_id = {user_service_hours_id}
                """
                execute_command(query)
            else:
                print('Inserting the record.')
                query = f"""
                    INSERT INTO tbl_user_service_hours 
                    (user_id, service_hours, service_category, description, status, 
                     created_by, created_date, modified_by, modified_date)
                    VALUES ({user_id}, {service_hours}, {service_category_escaped}, 
                            {description_escaped}, {status_escaped}, 
                            {current_user_id}, '{current_time}', 
                            {current_user_id}, '{current_time}')
                    RETURNING user_service_hours_id
                """
                execute_command(query)
            return jsonify({'success': 'Service hours saved'}), 200

        return render_template('add_edit_user_service_hours.html',
                              result={'service_hours_details': service_hours_details,
                                      'get_user_service_hours': get_user_service_hours_by_user_id(get_current_user_id())})
    except Exception as e:
        print('add/edit user service hours exception:- ', str(e))
        return jsonify({'error': str(e)}), 500


@application.route('/delete-user-service-hours/<int:user_service_hours_id>', methods=['POST', 'GET'])
def delete_user_service_hours(user_service_hours_id):
    try:
        if not (is_login() and is_admin()):
            return jsonify({'error': 'Unauthorized'}), 401

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_user_service_hours 
            SET status = '2', 
                modified_by = {current_user_id}, 
                modified_date = '{current_time}'
            WHERE user_service_hours_id = {user_service_hours_id}
        """
        execute_command(query)
        return jsonify({'success': 'Service hours deleted'}), 200
    except Exception as e:
        print('delete user service hours exception:- ', str(e))
        return jsonify({'error': str(e)}), 500
