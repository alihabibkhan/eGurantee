from imports import *
from application import application


@application.route('/manage_experience_ranges')
def manage_experience_ranges():
    try:
        if is_login() and (is_admin() or is_executive_approver()):
            content = {
                'get_all_experience_ranges': get_all_experience_ranges()
            }
            return render_template('manage_experience_ranges.html', result=content)
    except Exception as e:
        print('manage_experience_ranges exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/add-edit-experience-range', methods=['GET', 'POST'])
@application.route('/add-edit-experience-range/<int:experience_range_id>', methods=['GET', 'POST'])
def add_edit_experience_range(experience_range_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        experience_range = None

        if experience_range_id:
            query = f"""
                SELECT experience_range_id, label, min_years, max_years, status, created_by, created_date, 
                       modified_by, modified_date
                FROM tbl_experience_ranges 
                WHERE experience_range_id = '{experience_range_id}' AND status = '1'
            """
            print(query)
            experience_range = fetch_records(query)
            experience_range = experience_range[0] if experience_range else None

            print('experience_range record')
            print(experience_range)

        if request.method == 'POST':
            label = request.form.get('label')
            min_years = request.form.get('min_years')
            max_years = request.form.get('max_years')

            current_user_id = str(get_current_user_id())
            current_timestamp = str(datetime.now())

            if experience_range_id:
                update_query = f"""
                    UPDATE tbl_experience_ranges 
                    SET label = '{label}', min_years = '{min_years}', max_years = '{max_years}', 
                        status = '{str(1)}', modified_by = '{current_user_id}', modified_date = '{current_timestamp}'
                    WHERE experience_range_id = '{experience_range_id}'
                """
                execute_command(update_query)
                flash('Experience range updated successfully.', 'success')
            else:
                insert_query = f"""
                    INSERT INTO tbl_experience_ranges (
                        label, min_years, max_years, status, created_by, created_date, modified_by, modified_date
                    ) VALUES (
                        '{label}', '{min_years}', '{max_years}', '{str(1)}', '{current_user_id}', '{current_timestamp}', 
                        '{current_user_id}', '{current_timestamp}'
                    )
                """
                execute_command(insert_query)
                flash('Experience range added successfully.', 'success')

            return redirect(url_for('manage_loan_metrics') + '#experience-ranges')

        content = {
            'experience_range': experience_range,
            'experience_range_id': experience_range_id
        }
        return render_template('add_edit_experience_range.html', result=content)

    except Exception as e:
        print('add_edit_experience_range exception:- ', str(e))
        flash('An error occurred while processing the experience range.', 'danger')
        return redirect(url_for('manage_loan_metrics'))


@application.route('/delete-experience-range', methods=['GET'])
def delete_experience_range():
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        experience_range_id = request.args.get('experience_range_id')
        if experience_range_id:
            delete_query = f"""
                UPDATE tbl_experience_ranges 
                SET is_active = '0', status = '0'
                WHERE experience_range_id = '{experience_range_id}'
            """
            execute_command(delete_query)
            flash('Experience range deleted successfully.', 'success')
        else:
            flash('Invalid experience range ID.', 'danger')

        return redirect(url_for('manage_loan_metrics') + '#experience-ranges')

    except Exception as e:
        print('delete_experience_range exception:- ', str(e))
        flash('An error occurred while deleting the experience range.', 'danger')
        return redirect(url_for('manage_experience_ranges'))