from imports import *
from application import application


@application.route('/manage-bank-details')
def manage_bank_details():
    try:
        if is_login() and is_admin():
            content = {'get_all_bank_details': get_all_bank_details()}
            return render_template('manage_bank_details.html', result=content)
    except Exception as e:
        print('manage bank details exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/add-bank-details', methods=['GET', 'POST'])
@application.route('/edit-bank-details/<int:bank_id>', methods=['GET', 'POST'])
def add_edit_bank_details(bank_id=None):
    try:
        if not (is_login() and is_admin()):
            return redirect(url_for('login'))

        bank_details = None
        if bank_id:
            # Fetch existing record for editing
            query = f"""
                SELECT bank_id, bank_name, currency, date_account_opened, bank_code, branch_of_account, IBAN, account_title, date_account_closed
                FROM tbl_bank_details 
                WHERE bank_id = {bank_id} AND status != 3
            """
            bank_details = fetch_records(query)[0] if fetch_records(query) else None
            if not bank_details:
                return redirect(url_for('manage_bank_details'))

        if request.method == 'POST':
            # Get form data
            bank_code = request.form['bank_code']
            bank_name = request.form['bank_name']
            branch_of_account = request.form['branch_of_account']
            currency = request.form['currency']
            IBAN = request.form['IBAN']
            account_title = request.form['account_title']
            status = request.form['status']
            date_account_closed = request.form['date_account_closed'] or None
            date_account_opened = request.form['date_account_opened'] or None
            current_user_id = get_current_user_id()  # Assumed function to get logged-in user ID
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Escape string inputs to prevent SQL injection
            bank_code_escaped = escape_sql_string(bank_code)
            branch_of_account_escaped = escape_sql_string(branch_of_account)
            IBAN_escaped = escape_sql_string(IBAN)
            account_title_escaped = escape_sql_string(account_title)
            date_account_closed_escaped = escape_sql_string(date_account_closed)

            if bank_id:
                # Update existing record
                query = f"""
                    UPDATE tbl_bank_details 
                    SET bank_code = {bank_code_escaped},
                        bank_name = '{bank_name}', 
                        branch_of_account = {branch_of_account_escaped},
                        currency = '{currency}',
                        IBAN = {IBAN_escaped}, 
                        account_title = {account_title_escaped},
                        date_account_opened = '{str(date_account_opened)}' ,
                        date_account_closed = {date_account_closed_escaped},
                        status = '{status}',
                        modifed_by = {current_user_id}, 
                        modified_date = '{current_time}'
                    WHERE bank_id = {bank_id}
                """
                execute_command(query)
            else:
                # Insert new record
                query = f"""
                    INSERT INTO tbl_bank_details 
                    (bank_code, branch_of_account, IBAN, account_title, date_account_closed, 
                     status, created_by, created_date, modifed_by, modified_date, currency, date_account_opened, bank_name)
                    VALUES ({bank_code_escaped}, {branch_of_account_escaped}, {IBAN_escaped}, 
                            {account_title_escaped}, {date_account_closed_escaped}, 
                            1, {current_user_id}, '{current_time}', {current_user_id}, '{current_time}', '{currency}', '{date_account_opened}', '{bank_name}')
                    RETURNING bank_id
                """
                execute_command(query)
            return redirect(url_for('manage_bank_details'))

        # Render form for GET request
        return render_template('add_edit_bank_details.html', result={'bank_details': bank_details})
    except Exception as e:
        print('add/edit bank details exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-bank-details/<int:bank_id>', methods=['POST'])
def delete_bank_details(bank_id):
    try:
        if not (is_login() and is_admin()):
            return redirect(url_for('login'))

        current_user_id = get_current_user_id()  # Assumed function to get logged-in user ID
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            UPDATE tbl_bank_details 
            SET status = 3, modifed_by = {current_user_id}, modified_date = '{current_time}'
            WHERE bank_id = {bank_id}
        """
        execute_command(query)
        return redirect(url_for('manage_bank_details'))
    except Exception as e:
        print('delete bank details exception:- ', str(e))
        return redirect(url_for('login'))