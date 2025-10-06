from imports import *
from application import application


@application.route('/manage-bank-entries')
def manage_bank_entries():
    try:
        if is_login() and (is_admin() or is_executive_approver()):
            content = {
                'get_all_bank_details': get_all_bank_details(),
                'get_all_bank_entries_info': get_all_bank_entries_info()
            }
            return render_template('manage_bank_entries.html', result=content)
    except Exception as e:
        print('manage bank entries exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/add-bank-entry', methods=['POST'])
def add_bank_entry():
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return jsonify({'error': 'Unauthorized access'}), 401

        data = request.get_json()
        bank_id = data.get('bank_id')
        date_posted = data.get('date_posted')
        mode = data.get('mode')
        general_ledger = data.get('general_ledger')
        nature_of_transaction = data.get('nature_of_transaction')
        withdrawal = data.get('withdrawal')
        deposit = data.get('deposit')
        balance = data.get('balance')
        date_reconciled = data.get('date_reconciled')
        status = data.get('status', '1')
        created_by = get_current_user_id()
        created_date = datetime.now()

        # Validate bank_id exists in tbl_bank_details
        check_query = f"SELECT bank_id FROM tbl_bank_details WHERE bank_id = {bank_id} AND status = '1'"
        bank_exists = fetch_records(check_query)
        if not bank_exists:
            return jsonify({'error': 'Invalid bank ID'}), 400

        # Validate nature_of_transaction
        valid_nature = ['Withdrawal', 'Deposit']
        if nature_of_transaction not in valid_nature:
            return jsonify({'error': 'Invalid nature of transaction'}), 400

        query = f"""
            INSERT INTO tbl_bank_entry_management (
                bank_id, date_posted, mode, general_ledger, nature_of_transaction, 
                withdrawal, deposit, balance, date_reconciled, status, created_by, created_date, modified_by, modified_date
            ) VALUES (
                {bank_id}, '{date_posted}', '{mode}', '{general_ledger}', '{nature_of_transaction}', 
                {withdrawal or 0}, {deposit or 0}, {balance or 0}, '{date_reconciled or 'NULL'}', 
                {status}, {created_by}, '{created_date}', {created_by}, '{created_date}'
            ) RETURNING bank_entry_id
        """
        result = execute_command(query)

        if result:
            bank_entry_id = result  # Get the last inserted ID
            return jsonify({'message': 'Bank entry added successfully', 'bank_entry_id': bank_entry_id}), 200
        else:
            return jsonify({'error': 'Failed to add bank entry'}), 500

    except Exception as e:
        print('Add bank entry exception:', str(e))
        return jsonify({'error': 'Server error'}), 500


@application.route('/edit-bank-entry/<string:bank_entry_id>', methods=['POST', 'GET'])
def edit_bank_entry(bank_entry_id):
    try:
        print('edit_bank_entry triggered!!!')
        if not (is_login() and (is_admin() or is_executive_approver())):
            return jsonify({'error': 'Unauthorized access'}), 401

        data = request.get_json()
        bank_id = data.get('bank_id')
        date_posted = data.get('date_posted')
        mode = data.get('mode')
        general_ledger = data.get('general_ledger')
        nature_of_transaction = data.get('nature_of_transaction')
        withdrawal = data.get('withdrawal')
        deposit = data.get('deposit')
        balance = data.get('balance')
        date_reconciled = data.get('date_reconciled')
        status = data.get('status', '1')
        modified_by = get_current_user_id()
        modified_date = datetime.now()

        # Validate bank_id exists
        check_query = f"SELECT bank_id FROM tbl_bank_details WHERE bank_id = {bank_id} AND status = '1'"
        bank_exists = fetch_records(check_query)
        if not bank_exists:
            return jsonify({'error': 'Invalid bank ID'}), 400

        # Validate nature_of_transaction
        valid_nature = ['Withdrawal', 'Deposit']
        if nature_of_transaction not in valid_nature:
            return jsonify({'error': 'Invalid nature of transaction'}), 400

        # Check if bank_entry_id exists
        check_entry_query = f"SELECT bank_entry_id FROM tbl_bank_entry_management WHERE bank_entry_id = {bank_entry_id}"
        entry_exists = fetch_records(check_entry_query)
        if not entry_exists:
            return jsonify({'error': 'Bank entry not found'}), 404

        query = f"""
            UPDATE tbl_bank_entry_management
            SET bank_id = {bank_id}, 
                date_posted = '{date_posted}', 
                mode = '{mode}', 
                general_ledger = '{general_ledger}', 
                nature_of_transaction = '{nature_of_transaction}', 
                withdrawal = {withdrawal or 0}, 
                deposit = {deposit or 0}, 
                balance = {balance or 0}, 
                date_reconciled = '{date_reconciled or 'NULL'}', 
                status = {status}, 
                modified_by = {modified_by}, 
                modified_date = '{modified_date}'
            WHERE bank_entry_id = {bank_entry_id}
        """

        execute_command(query)

        return jsonify({'message': 'Bank entry updated successfully'}), 200
    except Exception as e:
        print('Edit bank entry exception:', str(e))
        return jsonify({'error': 'Server error'}), 500


@application.route('/delete-bank-entry/<int:bank_entry_id>', methods=['POST'])
def delete_bank_entry(bank_entry_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return jsonify({'error': 'Unauthorized access'}), 401

        # Check if bank_entry_id exists
        check_query = f"SELECT bank_entry_id FROM tbl_bank_entry_management WHERE bank_entry_id = {bank_entry_id}"
        entry_exists = fetch_records(check_query)
        if not entry_exists:
            return jsonify({'error': 'Bank entry not found'}), 404

        # query = f"DELETE FROM tbl_bank_entry_management WHERE bank_entry_id = {bank_entry_id}"
        query = f"""
            update tbl_bank_entry_management
            set
            status = 2,
            modified_by = '{str(get_current_user_id())}',
            modified_date = '{str(datetime.now())}'
            where
            bank_entry_id = '{str(bank_entry_id)}'
        """
        result = execute_command(query)

        return jsonify({'message': 'Bank entry deleted successfully'}), 200

    except Exception as e:
        print('Delete bank entry exception:', str(e))
        return jsonify({'error': 'Server error'}), 500