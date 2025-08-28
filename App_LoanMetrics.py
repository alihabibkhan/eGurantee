from imports import *
from application import application


@application.route('/manage_loan_metrics')
def manage_loan_metrics():
    try:
        if is_login() and is_admin():
            content = {
                'get_all_loan_products': get_all_loan_products(),
                'get_all_occupations': get_all_occupations(),
                'get_all_experience_ranges': get_all_experience_ranges(),
                'get_all_loan_metrics': get_all_loan_metrics(),
                'get_all_branches_info': get_all_branches_info()
            }
            return render_template('manage_loan_metrics.html', result=content)
    except Exception as e:
        print('manage_loan_metrics exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/add-edit-loan-metric', methods=['GET', 'POST'])
@application.route('/add-edit-loan-metric/<int:loan_metric_id>', methods=['GET', 'POST'])
def add_edit_loan_metric(loan_metric_id=None):
    try:
        if not is_login() or not is_admin():
            return redirect(url_for('login'))

        loan_metric = None

        if loan_metric_id:
            query = f"""
                SELECT loan_metric_id, product_id, occupation_id, experience_id, branch_id,
                       global_loan_ceiling, repeat_increment, is_active, status,
                       created_by, created_date, modified_by, modified_date
                FROM tbl_loan_metrics 
                WHERE loan_metric_id = '{loan_metric_id}' AND is_active = '1' AND status = '1'
            """
            print(query)
            loan_metric = fetch_records(query)
            loan_metric = loan_metric[0] if loan_metric else None

            print('loan_metric record')
            print(loan_metric)

        if request.method == 'POST':
            product_id = request.form.get('product_id')
            occupation_id = request.form.get('occupation_id')
            experience_id = request.form.get('experience_id')
            branch_id = request.form.get('branch_id')
            global_loan_ceiling = request.form.get('global_loan_ceiling')
            repeat_increment = request.form.get('repeat_increment')
            is_active = request.form.get('is_active')

            current_user_id = str(get_current_user_id())
            current_timestamp = str(datetime.now())

            if loan_metric_id:
                update_query = f"""
                    UPDATE tbl_loan_metrics 
                    SET product_id = '{product_id}', occupation_id = '{occupation_id}', 
                        experience_id = '{experience_id}', branch_id = '{branch_id}', 
                        global_loan_ceiling = '{global_loan_ceiling}', repeat_increment = '{repeat_increment}', 
                        is_active = '{is_active}', status = '{str(1)}', 
                        modified_by = '{current_user_id}', modified_date = '{current_timestamp}'
                    WHERE loan_metric_id = '{loan_metric_id}'
                """
                execute_command(update_query)
                flash('Loan metric updated successfully.', 'success')
            else:
                insert_query = f"""
                    INSERT INTO tbl_loan_metrics (
                        product_id, occupation_id, experience_id, branch_id, 
                        global_loan_ceiling, repeat_increment, is_active, status, 
                        created_by, created_date, modified_by, modified_date
                    ) VALUES (
                        '{product_id}', '{occupation_id}', '{experience_id}', '{branch_id}', 
                        '{global_loan_ceiling}', '{repeat_increment}', '{is_active}', '{str(1)}', 
                        '{current_user_id}', '{current_timestamp}', '{current_user_id}', '{current_timestamp}'
                    )
                """
                execute_command(insert_query)
                flash('Loan metric added successfully.', 'success')

            return redirect(url_for('manage_loan_metrics'))

        content = {
            'get_all_loan_products': get_all_loan_products(),
            'get_all_occupations': get_all_occupations(),
            'get_all_experience_ranges': get_all_experience_ranges(),
            'get_all_branches_info': get_all_branches_info(),
            'loan_metric': loan_metric,
            'loan_metric_id': loan_metric_id
        }
        return render_template('add_edit_loan_metric.html', result=content)

    except Exception as e:
        print('add_edit_loan_metric exception:- ', str(e))
        flash('An error occurred while processing the loan metric.', 'danger')
        return redirect(url_for('manage_loan_metrics'))


@application.route('/delete-loan-metric', methods=['GET'])
def delete_loan_metric():
    try:
        if not is_login() or not is_admin():
            return redirect(url_for('login'))

        loan_metric_id = request.args.get('loan_metric_id')
        if loan_metric_id:
            delete_query = f"""
                UPDATE tbl_loan_metrics 
                SET is_active = '0', status = '0'
                WHERE loan_metric_id = '{loan_metric_id}'
            """
            execute_command(delete_query)
            flash('Loan metric deleted successfully.', 'success')
        else:
            flash('Invalid loan metric ID.', 'danger')

        return redirect(url_for('manage_loan_metrics'))

    except Exception as e:
        print('delete_loan_metric exception:- ', str(e))
        flash('An error occurred while deleting the loan metric.', 'danger')
        return redirect(url_for('manage_loan_metrics'))



@application.route('/check_record_against_loan_metrics', methods=['POST'])
def check_record_against_loan_metrics():
    try:
        if is_login():
            # Extract data from request
            data = request.get_json()
            pre_disb_temp_id = data.get('pre_disb_temp_id')
            nature_of_business = data.get('nature_of_business')
            experience = data.get('experience')
            loan_amount = float(data.get('loan_amount')) if data.get('loan_amount') else None

            # Fetch the pre_disb_temp record
            pre_disb_record = get_all_pre_disbursement_temp_by_id(pre_disb_temp_id)
            if not pre_disb_record:
                return jsonify({'success': False, 'message': 'Record not found'}), 404

            # Fetch all loan metrics
            loan_metrics = get_loan_metrics_by_occupation_and_experience(occupation=nature_of_business, experience=experience)

            # Filter loan metrics based on record and request data
            matching_metrics = []
            for metric in loan_metrics:
                matches = True
                if pre_disb_record.get('LoanProductCode') and metric.get('product_name') != pre_disb_record.get('LoanProductCode'):
                    matches = False
                if nature_of_business and nature_of_business != '' and metric.get('occupation_name') != nature_of_business:
                    matches = False
                if experience and experience != '':
                    min_years = metric.get('min_years')
                    max_years = metric.get('max_years')
                    if not (metric.get('experience_label') and any(str(min_years) in label and str(max_years) in label for label in metric.get('experience_label', '').split(','))):
                        matches = False
                if matches:
                    matching_metrics.append(metric)

            if not matching_metrics:
                return jsonify({'success': False, 'message': 'No matching loan metrics found'}), 404

            # Use the first matching metric for comparison
            loan_metric = matching_metrics[0]
            loan_ceiling = float(loan_metric.get('global_loan_ceiling', 0))
            if loan_metric.get('repeat_increment'):
                loan_ceiling += float(loan_metric.get('repeat_increment', 0))

            message = ''
            if loan_amount is None or loan_amount == '':
                message = 'Please enter a loan amount to check.'
            elif loan_amount > loan_ceiling:
                message = f'Loan amount ({loan_amount}) exceeds the ceiling of {loan_ceiling}.'
            elif loan_amount <= loan_ceiling:
                message = f'Loan amount ({loan_amount}) is within the valid ceiling of {loan_ceiling}.'
            else:
                min_loan_amount = float(loan_metric.get('min_loan_amount', 0)) if loan_metric.get('min_loan_amount') else loan_ceiling
                message = f'Loan amount ({loan_amount}) is below the expected minimum of {min_loan_amount}.'

            return jsonify({'success': True, 'message': message}), 200
        else:
            return jsonify({'success': False, 'message': 'Unauthorized access'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
