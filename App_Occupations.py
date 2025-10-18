from imports import *
from application import application


@application.route('/manage_occupations')
def manage_occupations():
    try:
        if is_login() and (is_admin() or is_executive_approver()):
            content = {
                'get_all_occupations': get_all_occupations()
            }
            return render_template('manage_occupations.html', result=content)
    except Exception as e:
        print('manage_occupations exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/add-edit-occupation', methods=['GET', 'POST'])
@application.route('/add-edit-occupation/<int:occupation_id>', methods=['GET', 'POST'])
def add_edit_occupation(occupation_id=None):
    try:
        if not is_login() or not (is_admin() or is_executive_approver()):
            return redirect(url_for('login'))

        occupation = None

        if occupation_id:
            query = f"""
                SELECT occupation_id, name, status, created_by, created_date, modified_by, modified_date
                FROM tbl_occupations 
                WHERE occupation_id = '{occupation_id}' AND status = '1'
            """
            print(query)
            occupation = fetch_records(query)
            occupation = occupation[0] if occupation else None

            print('occupation record')
            print(occupation)

        if request.method == 'POST':
            name = request.form.get('name')

            current_user_id = str(get_current_user_id())
            current_timestamp = str(datetime.now())

            if occupation_id:
                update_query = f"""
                    UPDATE tbl_occupations 
                    SET name = '{name}', status = '{str(1)}', 
                        modified_by = '{current_user_id}', modified_date = '{current_timestamp}'
                    WHERE occupation_id = '{occupation_id}'
                """
                execute_command(update_query)
                flash('Occupation updated successfully.', 'success')
            else:
                insert_query = f"""
                    INSERT INTO tbl_occupations (
                        name, status, created_by, created_date, modified_by, modified_date
                    ) VALUES (
                        '{name}', '{str(1)}', '{current_user_id}', '{current_timestamp}', 
                        '{current_user_id}', '{current_timestamp}'
                    )
                """
                execute_command(insert_query)
                flash('Occupation added successfully.', 'success')

            return redirect(url_for('manage_loan_metrics') + "#occupations")

        content = {
            'occupation': occupation,
            'occupation_id': occupation_id
        }
        return render_template('add_edit_occupation.html', result=content)

    except Exception as e:
        print('add_edit_occupation exception:- ', str(e))
        flash('An error occurred while processing the occupation.', 'danger')
        return redirect(url_for('manage_loan_metrics'))


@application.route('/delete-occupation', methods=['GET'])
def delete_occupation():
    try:
        if not is_login() or not (is_admin() or is_executive_approver()):
            return redirect(url_for('login'))

        occupation_id = request.args.get('occupation_id')
        if occupation_id:
            delete_query = f"""
                UPDATE tbl_occupations 
                SET is_active = '0', status = '0'
                WHERE occupation_id = '{occupation_id}'
            """
            execute_command(delete_query)
            flash('Occupation deleted successfully.', 'success')
        else:
            flash('Invalid occupation ID.', 'danger')

        return redirect(url_for('manage_loan_metrics') + "#occupations")

    except Exception as e:
        print('delete_occupation exception:- ', str(e))
        flash('An error occurred while deleting the occupation.', 'danger')
        return redirect(url_for('manage_occupations'))