from imports import *
from application import application


@application.route('/view_meeting_calendar')
def view_meeting_calendar():
    try:
        if not is_login():
            return redirect(url_for('login'))

        # Fetch meetings for the current user's committee and current month
       # mandatory_meetings = get_user_committee_meetings_current_month()
        schedule_meetings = get_all_schedule_meetings(user_specific=True)

        return render_template('view_meeting_calendar.html',
                              result={
                                  #'mandatory_meetings': mandatory_meetings,
                                  'schedule_meetings': schedule_meetings
                              })
    except Exception as e:
        print('view meeting calender exception:- ', str(e))
        print('view meeting calender exception:- ', str(e.__dict__))
        return redirect(url_for('login'))


@application.route('/view-my-meetings')
def view_my_meetings():
    try:
        if not is_login():
            return redirect(url_for('login'))

        meetings = get_all_schedule_meetings(user_specific=True)
        return render_template('view_my_meetings.html', result={'schedule_meetings': meetings})
    except Exception as e:
        print('view_my_meetings exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/view-schedule-meetings')
def view_schedule_meetings():
    try:
        if not is_login():
            return redirect(url_for('login'))

        mandatory_meetings = get_user_committee_meetings_current_month()
        return render_template('view_schedule_meetings.html', result={'mandatory_meetings': mandatory_meetings})
    except Exception as e:
        print('view_schedule_meetings exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/post-meeting-action-items')
def post_meeting_action_items():
    try:
        if not is_login():
            return redirect(url_for('login'))

        meetings = get_all_schedule_meetings()

        # Fetch dropdown data with IDs
        priorities = get_all_meeting_action_items_priorities()

        query = """
            select distinct u.user_id, u.name, up.committee from tbl_users u
            inner join tbl_user_privileges up on up.user_id = u.user_id
        """
        assignees = fetch_records(query)

        statuses = get_all_meeting_action_items_status()
        return render_template('post_meeting_action_item.html', result={'schedule_meetings': meetings}, priorities=priorities, assignees=assignees, statuses=statuses)
    except Exception as e:
        print('view_my_action_items exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/save-action-item', methods=['POST'])
def save_action_item():
    try:
        schedule_meeting_id = request.form.get('schedule_meeting_id')
        action_item_id = request.form.get('action_item_id')  # For editing
        action_items = request.form.get('action_items')
        action_item_priority = request.form.get('action_item_priority')
        assigned_to = request.form.get('assigned_to')
        target_completion_date = request.form.get('target_completion_date')
        action_item_status = request.form.get('action_item_status')
        notes_followup = request.form.get('notes_followup')
        date_followup = request.form.get('date_followup')
        date_completed = request.form.get('date_completed')

        # Validate required fields
        if not all([schedule_meeting_id, action_items, action_item_priority, assigned_to, target_completion_date, action_item_status]):
            return jsonify({'success': False, 'message': 'All required fields must be filled.'})

        created_by = get_current_user_id()  # Replace with actual user (e.g., from session)
        created_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        modified_by = created_by if action_item_id else None
        modified_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if action_item_id else None

        print('is action_item_id available? :- ', action_item_id)

        if action_item_id:
            # Preprocess values using if/else without ternary operators
            if action_item_priority:
                action_item_priority = int(action_item_priority)
            else:
                action_item_priority = 'NULL'

            if assigned_to:
                assigned_to = int(assigned_to)
            else:
                assigned_to = 'NULL'

            if action_item_status:
                action_item_status = int(action_item_status)
            else:
                action_item_status = 'NULL'

            if notes_followup:
                notes_followup = "'" + notes_followup + "'"
            else:
                notes_followup = 'NULL'

            if date_followup:
                date_followup = "'" + date_followup + "'::date"
            else:
                date_followup = 'NULL'

            if date_completed:
                date_completed = "'" + date_completed + "'::date"
            else:
                date_completed = 'NULL'

            # Construct the UPDATE query using string concatenation
            query = """
                UPDATE tbl_post_meeting_updates
                SET action_items = '""" + action_items + """',
                    action_item_priority = """ + str(action_item_priority) + """,
                    assigned_to = """ + str(assigned_to) + """,
                    target_completion_date = '""" + target_completion_date + """'::date,
                    action_item_status = """ + str(action_item_status) + """,
                    notes_followup = """ + notes_followup + """,
                    date_followup = """ + date_followup + """,
                    date_completed = """ + date_completed + """,
                    modified_by = '""" + modified_by + """',
                    modified_date = '""" + modified_date + """'
                WHERE post_meeting_id = """ + str(int(action_item_id)) + """ AND status = 1
            """
        else:
            # Preprocess values to handle NULLs and conditionals in Python
            if action_item_priority:
                action_item_priority = int(action_item_priority)
            else:
                action_item_priority = 'NULL'

            if assigned_to:
                assigned_to = int(assigned_to)
            else:
                assigned_to = 'NULL'

            if action_item_status:
                action_item_status = int(action_item_status)
            else:
                action_item_status = 'NULL'

            if notes_followup:
                notes_followup = "'" + notes_followup + "'"
            else:
                notes_followup = 'NULL'

            if date_followup:
                date_followup = "'" + date_followup + "'::date"
            else:
                date_followup = 'NULL'

            if date_completed:
                date_completed = "'" + date_completed + "'::date"
            else:
                date_completed = 'NULL'

            # Construct the SQL query
            query = f"""
                INSERT INTO tbl_post_meeting_updates (
                    schedule_meeting_id, action_items, action_item_priority, assigned_to,
                    target_completion_date, action_item_status, notes_followup, date_followup,
                    date_completed, status, created_by, created_date, modified_by, modified_date
                ) VALUES (
                    {int(schedule_meeting_id)},
                    '{action_items}',
                    {action_item_priority},
                    {assigned_to},
                    '{target_completion_date}'::date,
                    {action_item_status},
                    {notes_followup},
                    {date_followup},
                    {date_completed},
                    1,
                    '{created_by}',
                    '{created_date}',
                    '{created_by}',
                    '{created_date}'
                )
            """

        execute_command(query)
        return jsonify({'success': True, 'message': 'Action item saved successfully.'})
    except Exception as e:
        print('save_action_item exception:- ', str(e))
        return jsonify({'success': False, 'message': str(e)})

@application.route('/get-action-items/<int:schedule_meeting_id>')
def get_action_items(schedule_meeting_id):
    try:
        print('schedule_meeting_id:- ', schedule_meeting_id)
        query = f"""
            SELECT pmu.post_meeting_id, pmu.action_items, pmu.target_completion_date,
                   maip.maip_name AS priority_name, u.name AS assignee_name,
                   mais.mais_name AS status_name, date_followup, notes_followup, date_completed
            FROM tbl_post_meeting_updates pmu
            LEFT JOIN tbl_meeting_action_items_priorities maip ON pmu.action_item_priority = maip.maip_id
            LEFT JOIN tbl_users u ON pmu.assigned_to = u.user_id
            LEFT JOIN tbl_meeting_action_items_status mais ON pmu.action_item_status = mais.mais_id
            WHERE pmu.schedule_meeting_id = {schedule_meeting_id} AND pmu.status = 1
        """
        print(query)
        result = fetch_records(query)  # Assuming it returns a list of rows
        print(result)

        return jsonify({'success': True, 'action_items': result})
    except Exception as e:
        print('get_action_items exception:- ', str(e))
        return jsonify({'success': False, 'message': str(e)})

@application.route('/get-action-item/<int:post_meeting_id>')
def get_action_item(post_meeting_id):
    try:
        print('post_meeting_id:- ', post_meeting_id)
        query = f"""
            SELECT pmu.post_meeting_id, pmu.action_items, pmu.action_item_priority,
                   pmu.assigned_to, pmu.target_completion_date, pmu.action_item_status,
                   pmu.notes_followup, pmu.date_followup, pmu.date_completed
            FROM tbl_post_meeting_updates pmu
            WHERE pmu.post_meeting_id = {post_meeting_id} AND pmu.status = 1
        """
        result = fetch_records(query)  # Assuming it returns a single row or list

        if result:
            return jsonify({'success': True, 'action_item': result[0]})

        return jsonify({'success': False, 'message': 'Action item not found.'})
    except Exception as e:
        print('get_action_item exception:- ', str(e))
        return jsonify({'success': False, 'message': str(e)})

@application.route('/delete-action-item/<int:post_meeting_id>', methods=['POST'])
def delete_action_item(post_meeting_id):
    try:
        modified_by = get_current_user_id()  # Replace with actual user
        modified_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_post_meeting_updates
            SET status = 2, modified_by = '{modified_by}', modified_date = '{modified_date}'
            WHERE post_meeting_id = {post_meeting_id} AND status = 1
        """
        execute_command(query)
        return jsonify({'success': True, 'message': 'Action item deleted successfully.'})
    except Exception as e:
        print('delete_action_item exception:- ', str(e))
        return jsonify({'success': False, 'message': str(e)})


@application.route('/schedule-meeting/<int:mand_meet_id>', methods=['GET', 'POST'])
def schedule_meeting(mand_meet_id):
    try:
        if not is_login():
            return redirect(url_for('login'))

        # Fetch mandatory meeting details
        mandatory_meeting = get_mandatory_meeting_details_by_id(mand_meet_id)
        if not mandatory_meeting:
            return redirect(url_for('view_meeting_calendar'))

        # Fetch existing schedule meeting data, if any
        schedule_meeting_details = get_schedule_meeting(mand_meet_id)

        if request.method == 'POST':
            meeting_title = request.form.get('meeting_title')
            meeting_aganda = request.form.get('meeting_aganda')
            schedule_date = request.form.get('schedule_date')
            pre_ms_id = request.form.get('pre_ms_id')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Escape strings to prevent SQL injection (temporary; use parameterized queries in production)
            meeting_title_escaped = escape_sql_string(meeting_title)
            meeting_aganda_escaped = escape_sql_string(meeting_aganda)

            if schedule_meeting_details:
                # Update existing schedule meeting
                query = f"""
                    UPDATE tbl_schedule_meetings 
                    SET meeting_title = {meeting_title_escaped},
                        meeting_aganda = {meeting_aganda_escaped},
                        schedule_date = '{schedule_date}',
                        pre_ms_id = {pre_ms_id},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE schedule_meeting_id = {schedule_meeting_details['schedule_meeting_id']}
                """
                execute_command(query)
            else:
                # Insert new schedule meeting
                query = f"""
                    INSERT INTO tbl_schedule_meetings 
                    (mand_meet_id, meeting_title, meeting_aganda, schedule_date, pre_ms_id, 
                     status, created_by, created_date, modified_by, modified_date)
                    VALUES ({mand_meet_id}, {meeting_title_escaped}, {meeting_aganda_escaped}, 
                            '{schedule_date}', {pre_ms_id}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING schedule_meeting_id
                """
                execute_command(query)
            return redirect(url_for('view_meeting_calendar'))

        # Pass data to template
        return render_template('schedule_meeting.html',
                              result={
                                  'schedule_meeting_details': schedule_meeting_details,
                                  'mandatory_meeting': mandatory_meeting,
                                  'get_all_pre_meeting_status': get_all_pre_meeting_status()
                              })
    except Exception as e:
        print('schedule meeting exception:- ', str(e))
        return redirect(url_for('login'))



@application.route('/manage-meeting-setup')
def manage_meeting_setup():
    try:
        if is_login() and (is_admin() or is_executive_approver()):
            content = {
                'get_all_meeting_categories': get_all_meeting_categories(),
                'get_all_meeting_frequencies': get_all_meeting_frequencies(),
                'get_all_meeting_priorities': get_all_meeting_priorities(),
                'get_all_pre_meeting_status': get_all_pre_meeting_status(),
                'get_all_post_meeting_status': get_all_post_meeting_status(),
                'get_all_meeting_action_items': get_all_meeting_action_items(),
                'get_all_meeting_action_items_priorities': get_all_meeting_action_items_priorities(),
                'get_all_meeting_action_items_status': get_all_meeting_action_items_status(),
                'get_all_mandatory_meetings': get_all_mandatory_meetings()
            }
            return render_template('manage_meeting_setup.html', result=content)
    except Exception as e:
        print('manage meeting setup exception:- ', str(e))
        print('manage meeting setup exception:- ', str(e.__dict__))
    return redirect(url_for('login'))


@application.route('/add-meeting-category', methods=['GET', 'POST'])
@application.route('/edit-meeting-category/<int:meeting_category_id>', methods=['GET', 'POST'])
def add_edit_meeting_category(meeting_category_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        meeting_category_details = None
        if meeting_category_id:
            query = f"""
                SELECT meeting_category_id, meeting_category_code, meeting_category_name, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_meeting_categories 
                WHERE meeting_category_id = {meeting_category_id} AND status != 3
            """
            result = fetch_records(query)
            meeting_category_details = result[0] if result else None
            if not meeting_category_details:
                return redirect(url_for('manage_meeting_setup') + "#meeting-categories")

        if request.method == 'POST':
            meeting_category_code = request.form.get('meeting_category_code')
            meeting_category_name = request.form.get('meeting_category_name')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            meeting_category_code_escaped = escape_sql_string(meeting_category_code)
            meeting_category_name_escaped = escape_sql_string(meeting_category_name)

            if meeting_category_id:
                query = f"""
                    UPDATE tbl_meeting_categories 
                    SET meeting_category_code = {meeting_category_code_escaped},
                        meeting_category_name = {meeting_category_name_escaped},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE meeting_category_id = {meeting_category_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_meeting_categories
                    (meeting_category_code, meeting_category_name, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({meeting_category_code_escaped}, {meeting_category_name_escaped}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING meeting_category_id
                """
                execute_command(query)
            return redirect(url_for('manage_meeting_setup') + "#meeting-categories")

        return render_template('add_edit_meeting_category.html',
                             result={'meeting_category_details': meeting_category_details,
                                    'get_all_meeting_categories': get_all_meeting_categories()})
    except Exception as e:
        print('add/edit meeting category exception:- ', str(e))
        return redirect(url_for('login'))

@application.route('/delete-meeting-category/<int:meeting_category_id>', methods=['POST', 'GET'])
def delete_meeting_category(meeting_category_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_meeting_categories 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE meeting_category_id = {meeting_category_id}
        """
        execute_command(query)
        return redirect(url_for('manage_meeting_setup') + "#meeting-categories")
    except Exception as e:
        print('delete meeting category exception:- ', str(e))
        return redirect(url_for('login'))



@application.route('/add-meeting-frequency', methods=['GET', 'POST'])
@application.route('/edit-meeting-frequency/<int:meeting_freq_id>', methods=['GET', 'POST'])
def add_edit_meeting_frequency(meeting_freq_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        meeting_freq_details = None
        if meeting_freq_id:
            query = f"""
                SELECT meeting_freq_id, meeting_freq_title, min_freq, max_freq, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_meeting_frequencies 
                WHERE meeting_freq_id = {meeting_freq_id} AND status != 3
            """
            result = fetch_records(query)
            meeting_freq_details = result[0] if result else None
            if not meeting_freq_details:
                return redirect(url_for('manage_meeting_setup') + "#meeting-frequencies")

        if request.method == 'POST':
            meeting_freq_title = request.form.get('meeting_freq_title')
            min_freq = request.form.get('min_freq')
            max_freq = request.form.get('max_freq')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            meeting_freq_title_escaped = escape_sql_string(meeting_freq_title)

            if meeting_freq_id:
                query = f"""
                    UPDATE tbl_meeting_frequencies 
                    SET meeting_freq_title = {meeting_freq_title_escaped},
                        min_freq = {min_freq},
                        max_freq = {max_freq},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE meeting_freq_id = {meeting_freq_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_meeting_frequencies 
                    (meeting_freq_title, min_freq, max_freq, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({meeting_freq_title_escaped}, {min_freq}, {max_freq}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING meeting_freq_id
                """
                execute_command(query)
            return redirect(url_for('manage_meeting_setup') + "#meeting-frequencies")

        return render_template('add_edit_meeting_frequency.html',
                             result={'meeting_freq_details': meeting_freq_details,
                                    'get_all_meeting_frequencies': get_all_meeting_frequencies()})
    except Exception as e:
        print('add/edit meeting frequency exception:- ', str(e))
        return redirect(url_for('login'))

@application.route('/delete-meeting-frequency/<int:meeting_freq_id>', methods=['POST', 'GET'])
def delete_meeting_frequency(meeting_freq_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_meeting_frequencies 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE meeting_freq_id = {meeting_freq_id}
        """
        execute_command(query)
        return redirect(url_for('manage_meeting_setup') + "#meeting-frequencies")
    except Exception as e:
        print('delete meeting frequency exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/add-meeting-priority', methods=['GET', 'POST'])
@application.route('/edit-meeting-priority/<int:meeting_priority_id>', methods=['GET', 'POST'])
def add_edit_meeting_priority(meeting_priority_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        meeting_priority_details = None
        if meeting_priority_id:
            query = f"""
                SELECT meeting_priority_id, meeting_priority_name, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_meeting_priorities 
                WHERE meeting_priority_id = {meeting_priority_id} AND status != 3
            """
            result = fetch_records(query)
            meeting_priority_details = result[0] if result else None
            if not meeting_priority_details:
                return redirect(url_for('manage_meeting_setup') + "#meeting-priorities")

        if request.method == 'POST':
            meeting_priority_name = request.form.get('meeting_priority_name')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            meeting_priority_name_escaped = escape_sql_string(meeting_priority_name)

            if meeting_priority_id:
                query = f"""
                    UPDATE tbl_meeting_priorities 
                    SET meeting_priority_name = {meeting_priority_name_escaped},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE meeting_priority_id = {meeting_priority_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_meeting_priorities 
                    (meeting_priority_name, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({meeting_priority_name_escaped}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING meeting_priority_id
                """
                execute_command(query)
            return redirect(url_for('manage_meeting_setup') + "#meeting-priorities")

        return render_template('add_edit_meeting_priority.html',
                             result={'meeting_priority_details': meeting_priority_details,
                                    'get_all_meeting_priorities': get_all_meeting_priorities()})
    except Exception as e:
        print('add/edit meeting priority exception:- ', str(e))
        return redirect(url_for('login'))

@application.route('/delete-meeting-priority/<int:meeting_priority_id>', methods=['POST', 'GET'])
def delete_meeting_priority(meeting_priority_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_meeting_priorities 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE meeting_priority_id = {meeting_priority_id}
        """
        execute_command(query)
        return redirect(url_for('manage_meeting_setup') + "#meeting-priorities")
    except Exception as e:
        print('delete meeting priority exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/add-pre-meeting-status', methods=['GET', 'POST'])
@application.route('/edit-pre-meeting-status/<int:pre_ms_id>', methods=['GET', 'POST'])
def add_edit_pre_meeting_status(pre_ms_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        pre_ms_details = None
        if pre_ms_id:
            query = f"""
                SELECT pre_ms_id, pre_ms_name, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_pre_meeting_status 
                WHERE pre_ms_id = {pre_ms_id} AND status != 3
            """
            result = fetch_records(query)
            pre_ms_details = result[0] if result else None
            if not pre_ms_details:
                return redirect(url_for('manage_meeting_setup') + "#pre-meeting-status")

        if request.method == 'POST':
            pre_ms_name = request.form.get('pre_ms_name')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            pre_ms_name_escaped = escape_sql_string(pre_ms_name)

            if pre_ms_id:
                query = f"""
                    UPDATE tbl_pre_meeting_status 
                    SET pre_ms_name = {pre_ms_name_escaped},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE pre_ms_id = {pre_ms_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_pre_meeting_status 
                    (pre_ms_name, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({pre_ms_name_escaped}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING pre_ms_id
                """
                execute_command(query)
            return redirect(url_for('manage_meeting_setup') + "#pre-meeting-status")

        return render_template('add_edit_pre_meeting_status.html',
                             result={'pre_ms_details': pre_ms_details,
                                    'get_all_pre_meeting_status': get_all_pre_meeting_status()})
    except Exception as e:
        print('add/edit pre-meeting status exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-pre-meeting-status/<int:pre_ms_id>', methods=['POST', 'GET'])
def delete_pre_meeting_status(pre_ms_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_pre_meeting_status 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE pre_ms_id = {pre_ms_id}
        """
        execute_command(query)
        return redirect(url_for('manage_meeting_setup') + "#pre-meeting-status")
    except Exception as e:
        print('delete pre-meeting status exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/add-post-meeting-status', methods=['GET', 'POST'])
@application.route('/edit-post-meeting-status/<int:post_ms_id>', methods=['GET', 'POST'])
def add_edit_post_meeting_status(post_ms_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        post_ms_details = None
        if post_ms_id:
            query = f"""
                SELECT post_ms_id, post_ms_name, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_post_meeting_status 
                WHERE post_ms_id = {post_ms_id} AND status != 3
            """
            result = fetch_records(query)
            post_ms_details = result[0] if result else None
            if not post_ms_details:
                return redirect(url_for('manage_meeting_setup') + "#post-meeting-status")

        if request.method == 'POST':
            post_ms_name = request.form.get('post_ms_name')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            post_ms_name_escaped = escape_sql_string(post_ms_name)

            if post_ms_id:
                query = f"""
                    UPDATE tbl_post_meeting_status 
                    SET post_ms_name = {post_ms_name_escaped},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE post_ms_id = {post_ms_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_post_meeting_status 
                    (post_ms_name, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({post_ms_name_escaped}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING post_ms_id
                """
                execute_command(query)
            return redirect(url_for('manage_meeting_setup') + "#post-meeting-status")

        return render_template('add_edit_post_meeting_status.html',
                             result={'post_ms_details': post_ms_details,
                                    'get_all_post_meeting_status': get_all_post_meeting_status()})
    except Exception as e:
        print('add/edit post-meeting status exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-post-meeting-status/<int:post_ms_id>', methods=['POST', 'GET'])
def delete_post_meeting_status(post_ms_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_post_meeting_status 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE post_ms_id = {post_ms_id}
        """
        execute_command(query)
        return redirect(url_for('manage_meeting_setup') + "#post-meeting-status")
    except Exception as e:
        print('delete post-meeting status exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/add-meeting-action-item', methods=['GET', 'POST'])
@application.route('/edit-meeting-action-item/<int:mai_id>', methods=['GET', 'POST'])
def add_edit_meeting_action_item(mai_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        mai_details = None
        if mai_id:
            query = f"""
                SELECT mai_id, mai_name, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_meeting_action_items 
                WHERE mai_id = {mai_id} AND status != 3
            """
            result = fetch_records(query)
            mai_details = result[0] if result else None
            if not mai_details:
                return redirect(url_for('manage_meeting_setup') + "#meeting-action-items")

        if request.method == 'POST':
            mai_name = request.form.get('mai_name')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            mai_name_escaped = escape_sql_string(mai_name)

            if mai_id:
                query = f"""
                    UPDATE tbl_meeting_action_items 
                    SET mai_name = {mai_name_escaped},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE mai_id = {mai_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_meeting_action_items 
                    (mai_name, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({mai_name_escaped}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING mai_id
                """
                execute_command(query)
            return redirect(url_for('manage_meeting_setup') + "#meeting-action-items")

        return render_template('add_edit_meeting_action_item.html',
                             result={'mai_details': mai_details,
                                    'get_all_meeting_action_items': get_all_meeting_action_items()})
    except Exception as e:
        print('add/edit meeting action item exception:- ', str(e))
        return redirect(url_for('login'))

@application.route('/delete-meeting-action-item/<int:mai_id>', methods=['POST', 'GET'])
def delete_meeting_action_item(mai_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_meeting_action_items 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE mai_id = {mai_id}
        """
        execute_command(query)
        return redirect(url_for('manage_meeting_setup') + "#meeting-action-items")
    except Exception as e:
        print('delete meeting action item exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/add-meeting-action-item-priority', methods=['GET', 'POST'])
@application.route('/edit-meeting-action-item-priority/<int:maip_id>', methods=['GET', 'POST'])
def add_edit_meeting_action_item_priority(maip_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        maip_details = None
        if maip_id:
            query = f"""
                SELECT maip_id, maip_name, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_meeting_action_items_priorities 
                WHERE maip_id = {maip_id} AND status != 3
            """
            result = fetch_records(query)
            maip_details = result[0] if result else None
            if not maip_details:
                return redirect(url_for('manage_meeting_setup') + "#meeting-action-items-priorities")

        if request.method == 'POST':
            maip_name = request.form.get('maip_name')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            maip_name_escaped = escape_sql_string(maip_name)

            if maip_id:
                query = f"""
                    UPDATE tbl_meeting_action_items_priorities 
                    SET maip_name = {maip_name_escaped},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE maip_id = {maip_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_meeting_action_items_priorities 
                    (maip_name, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({maip_name_escaped}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING maip_id
                """
                execute_command(query)
            return redirect(url_for('manage_meeting_setup') + "#meeting-action-items-priorities")

        return render_template('add_edit_meeting_action_item_priority.html',
                             result={'maip_details': maip_details,
                                    'get_all_meeting_action_items_priorities': get_all_meeting_action_items_priorities()})
    except Exception as e:
        print('add/edit meeting action item priority exception:- ', str(e))
        return redirect(url_for('login'))

@application.route('/delete-meeting-action-item-priority/<int:maip_id>', methods=['POST', 'GET'])
def delete_meeting_action_item_priority(maip_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_meeting_action_items_priorities 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE maip_id = {maip_id}
        """
        execute_command(query)
        return redirect(url_for('manage_meeting_setup') + "#meeting-action-items-priorities")
    except Exception as e:
        print('delete meeting action item priority exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/add-meeting-action-item-status', methods=['GET', 'POST'])
@application.route('/edit-meeting-action-item-status/<int:mais_id>', methods=['GET', 'POST'])
def add_edit_meeting_action_item_status(mais_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        mais_details = None
        if mais_id:
            query = f"""
                SELECT mais_id, mais_name, status, 
                       created_by, created_date, modified_by, modified_date
                FROM tbl_meeting_action_items_status 
                WHERE mais_id = {mais_id} AND status != 3
            """
            result = fetch_records(query)
            mais_details = result[0] if result else None
            if not mais_details:
                return redirect(url_for('manage_meeting_setup') + "#meeting-action-items-status")

        if request.method == 'POST':
            mais_name = request.form.get('mais_name')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            mais_name_escaped = escape_sql_string(mais_name)

            if mais_id:
                query = f"""
                    UPDATE tbl_meeting_action_items_status 
                    SET mais_name = {mais_name_escaped},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE mais_id = {mais_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_meeting_action_items_status 
                    (mais_name, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({mais_name_escaped}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING mais_id
                """
                execute_command(query)
            return redirect(url_for('manage_meeting_setup') + "#meeting-action-items-status")

        return render_template('add_edit_meeting_action_item_status.html',
                             result={'mais_details': mais_details,
                                    'get_all_meeting_action_items_status': get_all_meeting_action_items_status()})
    except Exception as e:
        print('add/edit meeting action item status exception:- ', str(e))
        return redirect(url_for('login'))

@application.route('/delete-meeting-action-item-status/<int:mais_id>', methods=['POST', 'GET'])
def delete_meeting_action_item_status(mais_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_meeting_action_items_status 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE mais_id = {mais_id}
        """
        execute_command(query)
        return redirect(url_for('manage_meeting_setup') + "#meeting-action-items-status")
    except Exception as e:
        print('delete meeting action item status exception:- ', str(e))
        return redirect(url_for('login'))



@application.route('/add-mandatory-meeting', methods=['GET', 'POST'])
@application.route('/edit-mandatory-meeting/<int:mand_meet_id>', methods=['GET', 'POST'])
def add_edit_mandatory_meeting(mand_meet_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        mand_meet_details = None
        if mand_meet_id:
            query = f"""
                SELECT mand_meet_id, meeting_category_id, meeting_freq_id, proposed_month, nc_disb_id, 
                       resp_committ, meeting_priority_id, status, created_by, created_date, modified_by, modified_date
                FROM tbl_mandatory_meetings 
                WHERE mand_meet_id = {mand_meet_id} AND status != 3
            """
            result = fetch_records(query)
            mand_meet_details = result[0] if result else None
            if not mand_meet_details:
                return redirect(url_for('manage_meeting_setup') + "#mandatory-meetings")

        if request.method == 'POST':
            meeting_category_id = request.form.get('meeting_category_id')
            meeting_freq_id = request.form.get('meeting_freq_id')
            proposed_month = request.form.get('proposed_month')
            nc_disb_id = request.form.get('nc_disb_id')
            resp_committ = request.form.get('resp_committ')
            meeting_priority_id = request.form.get('meeting_priority_id')
            status = '1'
            current_user_id = get_current_user_id()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Convert proposed_month (YYYY-MM) to a full date (YYYY-MM-01)
            if proposed_month:
                proposed_month = f"{proposed_month}-01"  # Append first day of the month
            else:
                proposed_month = None  # Handle case where proposed_month is empty

            resp_committ_escaped = escape_sql_string(resp_committ)

            if mand_meet_id:
                query = f"""
                    UPDATE tbl_mandatory_meetings 
                    SET meeting_category_id = {meeting_category_id},
                        meeting_freq_id = {meeting_freq_id},
                        proposed_month = '{proposed_month}',
                        nc_disb_id = {nc_disb_id},
                        resp_committ = {resp_committ_escaped},
                        meeting_priority_id = {meeting_priority_id},
                        status = {status},
                        modified_by = {current_user_id},
                        modified_date = '{current_time}'
                    WHERE mand_meet_id = {mand_meet_id}
                """
                execute_command(query)
            else:
                query = f"""
                    INSERT INTO tbl_mandatory_meetings 
                    (meeting_category_id, meeting_freq_id, proposed_month, nc_disb_id, resp_committ, 
                     meeting_priority_id, status, created_by, created_date, modified_by, modified_date)
                    VALUES ({meeting_category_id}, {meeting_freq_id}, '{proposed_month}', {nc_disb_id}, 
                            {resp_committ_escaped}, {meeting_priority_id}, {status}, 
                            {current_user_id}, '{current_time}', {current_user_id}, '{current_time}')
                    RETURNING mand_meet_id
                """
                execute_command(query)
            return redirect(url_for('manage_meeting_setup') + "#mandatory-meetings")

        return render_template('add_edit_mandatory_meeting.html',
                             result={'mand_meet_details': mand_meet_details,
                                    'get_all_mandatory_meetings': get_all_mandatory_meetings(),
                                    'get_all_meeting_categories': get_all_meeting_categories(),
                                    'get_all_meeting_frequencies': get_all_meeting_frequencies(),
                                    'get_all_meeting_priorities': get_all_meeting_priorities(),
                                    'get_all_national_council_distributions': get_all_national_council_distributions()})
    except Exception as e:
        print('add/edit mandatory meeting exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-mandatory-meeting/<int:mand_meet_id>', methods=['POST', 'GET'])
def delete_mandatory_meeting(mand_meet_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_mandatory_meetings 
            SET status = 2, modified_by = {current_user_id}, modified_date = '{current_time}'
            WHERE mand_meet_id = {mand_meet_id}
        """
        execute_command(query)
        return redirect(url_for('manage_meeting_setup') + "#mandatory-meetings")
    except Exception as e:
        print('delete mandatory meeting exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/master-book-action-items')
def master_book_action_items():
    try:
        if not is_login():
            return redirect(url_for('login'))

        return render_template('view_master_book_action_items.html')
    except Exception as e:
        print('view_master_book_action_items exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/get-master-book-action-items', methods=['POST'])
def get_master_book_action_items():
    try:
        filters = {
            'meetingCategoryWithCode': request.json.get('meetingCategoryWithCode', ''),
            'Frequency': request.json.get('Frequency', ''),
            'TragetRangeAnnualOfMeetings': request.json.get('TragetRangeAnnualOfMeetings', ''),
            'proposed_month': request.json.get('proposed_month', ''),
            'national_council_distribution_name': request.json.get('national_council_distribution_name', ''),
            'resp_committ': request.json.get('resp_committ', ''),
            'meeting_priority_name': request.json.get('meeting_priority_name', ''),
            'meeting_title': request.json.get('meeting_title', ''),
            'meeting_aganda': request.json.get('meeting_aganda', ''),
            'assigned_leads': request.json.get('assigned_leads', ''),
            'schedule_meeting_id': request.json.get('schedule_meeting_id', ''),
            'last_updated_by': request.json.get('last_updated_by', ''),
            'schedule_date': request.json.get('schedule_date', ''),
            'pre_ms_name': request.json.get('pre_ms_name', '')
        }

        mandatory_meetings = get_meeting_master_book_data()
        filtered_data = mandatory_meetings
        for key, value in filters.items():
            if value:
                filtered_data = [m for m in filtered_data if str(m.get(key, '')).lower().find(value.lower()) != -1]

        return jsonify({'success': True, 'records': filtered_data})
    except Exception as e:
        print('get_master_book_action_items exception:- ', str(e))
        return jsonify({'success': False, 'message': str(e)})