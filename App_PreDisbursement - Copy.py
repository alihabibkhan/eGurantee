from imports import *
from application import application


@application.route('/manage-pre-disbursement')
def manage_pre_disbursement():
    try:
        if is_login():

            return render_template('manage_pre_disbursement.html')
    except Exception as e:
        print('manage pre-disbursement exception:- ', str(e.__dict__))
    return redirect(url_for('login'))


# Route to get data for DataTables
@application.route('/get_pre_disbursement_data', methods=['POST'])
def get_pre_disbursement_data():
    try:
        if is_login():
            record_type = request.form.get('record_type', 'temp')

            # Get pagination parameters from DataTables
            start = int(request.form.get('start', 0))
            length = int(request.form.get('length', 10))
            search_value = request.form.get('search[value]', '')

            sql_part_temp = ''
            sql_part_main = ''

            if get_current_user_role() != 'ADMIN':
                sql_part_temp ="""
                    INNER JOIN tbl_branches b on pdt.Branch_Name LIKE CONCAT('%', b.branch_code, '%') AND b.live_branch = '1'
                    INNER JOIN tbl_users u on u.role = b.role and u.active = '1'
                    LEFT JOIN tbl_users u1 ON u1.user_id = pdt.uploaded_by
                    WHERE u.role = '"""+str(get_current_user_role())+"""'
                """

                sql_part_main = """
                    INNER JOIN tbl_branches b on pdm.Branch_Name LIKE CONCAT('%', b.branch_code, '%') AND b.live_branch = '1'
                    INNER JOIN tbl_users u on u.role = b.role and u.active = '1'
                    LEFT JOIN tbl_users u1 ON u1.user_id = pdt.approved_by
                    WHERE u.role = '"""+str(get_current_user_role())+"""'
                """
            else:
                sql_part_temp = """
                    LEFT JOIN tbl_users u ON u.user_id = pdt.uploaded_by
                """

                sql_part_main = """
                    LEFT JOIN tbl_users u ON u.user_id = pdm.approved_by    
                """

            # Base query
            if record_type == 'temp':
                query = """
                    SELECT pdt.*, """+("u.name as createdBy" if get_current_user_role() == 'ADMIN' else "u1.name as createdBy")+""" 
                    FROM tbl_pre_disbursement_temp pdt
                    """+str(sql_part_temp)+"""
                """
                count_query = "SELECT COUNT(*) FROM tbl_pre_disbursement_temp"
            else:
                query = """
                    SELECT pdm.*, pdt.*, u.name as createdBy 
                    FROM tbl_pre_disbursement_main pdm
                    JOIN tbl_pre_disbursement_temp pdt ON pdm.pre_disb_temp_id = pdt.pre_disb_temp_id
                    """+str(sql_part_temp)+"""
                """
                count_query = "SELECT COUNT(*) FROM tbl_pre_disbursement_main"

            print(query)

            # Add search filter if provided
            if search_value:
                search_term = f"%{search_value}%"
                query += f""+('WHERE ' if get_current_user_role() == 'ADMIN' else 'AND ')+f"pdt.Application_No LIKE '{search_term}'"
                params = (search_term, search_term, search_term)
            else:
                params = ()

            # Add pagination
            query += f" LIMIT {start}, {length}"

            print(query)

            # Execute queries
            records = fetch_records(query)
            total_records = fetch_records(count_query)[0]

            return jsonify({
                "draw": int(request.form.get('draw', 1)),
                "recordsTotal": int(total_records.get('COUNT(*)')),
                "recordsFiltered": int(total_records.get('COUNT(*)')),
                "data": records
            })
        return jsonify({"error": "Unauthorized"}), 401
    except Exception as e:
        print(f"Error in get_pre_disbursement_data: {str(e)}")
        return jsonify({"error": str(e)}), 500


# Route to get detailed view
@application.route('/get_pre_disbursement_details/<int:record_id>/<string:record_type>')
def get_pre_disbursement_details(record_id, record_type):
    try:
        if is_login():
            print(record_id, record_type)
            if record_type == 'temp':
                query = f"""
                    SELECT pdt.*, u.name as createdBy 
                    FROM tbl_pre_disbursement_temp pdt
                    LEFT JOIN tbl_users u ON u.user_id = pdt.uploaded_by
                    WHERE pdt.pre_disb_temp_id = '{str(record_id)}'
                """
            else:
                query = f"""
                    SELECT pdm.*, pdt.*, u.name as createdBy 
                    FROM tbl_pre_disbursement_main pdm
                    JOIN tbl_pre_disbursement_temp pdt ON pdm.pre_disb_temp_id = pdt.pre_disb_temp_id
                    LEFT JOIN tbl_users u ON u.user_id = pdm.approved_by
                    WHERE pdm.pre_disb_main_id = '{str(record_id)}'
                """

            record = fetch_records(query)[0]

            if record:
                # Render a detailed HTML view (you can create a separate template for this)
                html = f"""
                <div class="row">
                    <div class="col-md-6">
                        <h5>Basic Information</h5>
                        <table class="table table-sm">
                            <tr><th>Application No:</th><td>{record.get('Application_No', 'N/A')}</td></tr>
                            <tr><th>Borrower Name:</th><td>{record.get('Borrower_Name', 'N/A')}</td></tr>
                            <tr><th>CNIC:</th><td>{record.get('CNIC', 'N/A')}</td></tr>
                            <tr><th>Contact No:</th><td>{record.get('Contact_No', 'N/A')}</td></tr>
                        </table>
                    </div>
                    <div class="col-md-6">
                        <h5>Loan Information</h5>
                        <table class="table table-sm">
                            <tr><th>Product Code:</th><td>{record.get('LoanProductCode', 'N/A')}</td></tr>
                            <tr><th>Loan Amount:</th><td>{record.get('Loan_Amount', 'N/A')}</td></tr>
                            <tr><th>Loan Cycle:</th><td>{record.get('Loan_Cycle', 'N/A')}</td></tr>
                            <tr><th>Status:</th><td>{get_status_text(record.get('status', 1))}</td></tr>
                        </table>
                    </div>
                </div>
                <div class="row mt-3">
                    <div class="col-md-12">
                        <h5>Notes</h5>
                        <p>{record.get('notes', 'No notes available')}</p>
                    </div>
                </div>
                """
                return html
            return "<div class='alert alert-warning'>Record not found</div>"
        return "<div class='alert alert-danger'>Unauthorized</div>"
    except Exception as e:
        print(f"Error in get_pre_disbursement_details: {str(e)}")
        return "<div class='alert alert-danger'>Error loading details</div>"


# Route to get current status
@application.route('/get_pre_disbursement_status/<int:record_id>/<string:record_type>')
def get_pre_disbursement_status(record_id, record_type):
    try:
        if is_login():
            if record_type == 'temp':
                query = f"SELECT status, notes FROM tbl_pre_disbursement_temp WHERE pre_disb_temp_id = '{str(record_id)}'"
            else:
                query = f"SELECT status, notes FROM tbl_pre_disbursement_main WHERE pre_disb_main_id = '{str(record_id)}"

            record = fetch_records(query)[0]

            if record:
                return jsonify({
                    "success": True,
                    "status": record['status'],
                    "notes": record['notes']
                })
            return jsonify({"success": False, "message": "Record not found"}), 404
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    except Exception as e:
        print(f"Error in get_pre_disbursement_status: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


# Route to update status
@application.route('/update_pre_disbursement_status', methods=['POST'])
def update_pre_disbursement_status():
    try:
        if is_login() and is_admin():
            record_id = request.form.get('id')
            record_type = request.form.get('type')
            new_status = int(request.form.get('status'))
            notes = request.form.get('notes')
            user_id = get_current_user_id()

            print(record_id, record_type, new_status, notes, user_id)

            if not record_id or not record_type:
                return jsonify({"success": False, "message": "Missing parameters"}), 400

            if record_type == 'temp':
                # Update temp record using execute_command
                update_query = f"""
                    UPDATE tbl_pre_disbursement_temp 
                    SET status = '{str(new_status)}', notes = '{str(notes)}',
                    approved_by = '{str(user_id)}', approved_date = '{str(datetime.now())}' 
                    WHERE pre_disb_temp_id = '{str(record_id)}'
                """
                execute_command(update_query)

                # If status is approved (2), create record in main table
                if new_status == 2:
                    # Check if record already exists in main table
                    check_query = f"""
                        SELECT COUNT(*) FROM tbl_pre_disbursement_main 
                        WHERE pre_disb_temp_id = '{str(record_id)}'
                    """
                    count_result = fetch_records(check_query)
                    count = int(count_result[0]['COUNT(*)']) if count_result else 0

                    if count == 0:
                        # Get data from temp table

                        temp_records = get_all_pre_disbursement_temp_by_id(record_id)

                        if temp_records and len(temp_records) > 0:
                            temp_record = temp_records[0]
                            # Insert into main table
                            insert_query = f"""
                                INSERT INTO tbl_pre_disbursement_main (
                                    pre_disb_temp_id, notes, status, approved_by, approved_date
                                ) VALUES ('{str(record_id)}', '{str(notes)}', '{str(new_status)}', '{str(user_id)}', '{str(datetime.now())}')
                            """
                            execute_command(insert_query)

            else:  # For main records
                update_query = f"""
                    UPDATE tbl_pre_disbursement_main 
                    SET status = '{str(new_status)}', notes = '{str(notes)}'  
                    WHERE pre_disb_main_id = '{str(record_id)}'
                """
                execute_command(update_query)

            return jsonify({"success": True})

        return jsonify({"success": False, "message": "Unauthorized"}), 401
    except Exception as e:
        print(f"Error in update_pre_disbursement_status: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


# Helper function to get status text
def get_status_text(status_code):
    status_map = {
        1: "Pending",
        2: "Approved",
        3: "Declined"
    }
    return status_map.get(status_code, "Unknown")

@application.route('/show_lean')
def show_lean():
    return render_template('show_lean.html')