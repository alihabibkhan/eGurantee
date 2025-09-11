from imports import *
from application import application


@application.route('/manage-pre-disbursement')
def manage_pre_disbursement():
    try:
        if is_login():
            content = {
                'get_temp_pre_disbursement': get_all_pre_disbursement_temp(),
                'is_user_have_sign': is_user_have_sign(),
                'occupation_list': get_all_occupations(),
                'experience_ranges_list': get_all_experience_ranges(),
                'get_all_loan_metrics': get_all_loan_metrics(),
                'is_reviewer': is_reviewer(),
                'is_approver': is_approver(),
                'is_executive_approver': is_executive_approver(),
                'is_admin': is_admin()
            }
            return render_template('manage_pre_disbursement.html', result=content)
    except Exception as e:
        print('manage pre-disbursement exception:- ', str(e.__dict__))
    return redirect(url_for('login'))



@application.route('/update-pre-disbursement-temp', methods=['POST'])
def update_pre_disbursement_temp():
    try:
        if not is_login():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        data = request.get_json()
        print(data)
        pre_disb_temp_id = data.get('pre_disb_temp_id')
        status = str(data.get('status'))
        notes = data.get('Notes')
        amount_accepted = data.get('amount_accepted')

        approved_by = str(get_current_user_id())
        approved_date = str(datetime.now())

        if not pre_disb_temp_id or not status:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        query = ''

        if status != '4':
            query = f"""
               UPDATE tbl_pre_disbursement_temp
               SET status = '{str(status)}', Notes = '{str(notes)}', KFT_Approved_Loan_Limit = '{str(amount_accepted)}',
               approved_by = '{str(approved_by)}', approved_date = '{str(approved_date)}'
               WHERE pre_disb_temp_id = '{str(pre_disb_temp_id)}'
            """
        else:
            query = f"""
               UPDATE tbl_pre_disbursement_temp
               SET status = '{str(status)}', Notes = '{str(notes)}',
               reviewed_by = '{str(approved_by)}', reviewed_date = '{str(approved_date)}'
               WHERE pre_disb_temp_id = '{str(pre_disb_temp_id)}'
            """

        execute_command(query)

        if status == '2':
            # Check if record already exists in main table
            print('status is 2 proceeding to insert record in main.')
            check_query = f"""
               SELECT COUNT(*) FROM tbl_pre_disbursement_main 
               WHERE pre_disb_temp_id = '{str(pre_disb_temp_id)}'
            """
            count_result = fetch_records(check_query)
            print('printing count result')
            print(count_result)
            # count = int(count_result[0]['COUNT(*)']) if count_result else 0
            count = int(count_result[0]['count']) if count_result else 0


            if count == 0:
                print('no record found in main table for respective temp id, inserting the record.')
                # Get data from temp table

                temp_records = get_all_pre_disbursement_temp_by_id(pre_disb_temp_id)

                if temp_records and len(temp_records) > 0:
                    print('Inserting into main table')
                    # Insert into main table
                    insert_query = f"""
                        INSERT INTO tbl_pre_disbursement_main (
                            pre_disb_temp_id, notes, status, approved_by, approved_date
                        ) VALUES ('{str(pre_disb_temp_id)}', '{str(notes)}', '{str(status)}', '{str(approved_by)}', '{str(approved_date)}')
                    """
                    execute_command(insert_query)
                    print('record has been inserted.')
            else:
                print('record exists in main, updating the existing record.')
                # query = f"""
                #     update tbl_pre_disbursement_main pdm
                #     set
                #         pdm.status = '{str(status)}',
                #         pdm.notes = '{str(notes)}',
                #         pdm.approved_by = '{str(approved_by)}',
                #         pdm.approved_date = '{str(approved_date)}'
                #     where
                #         pdm.pre_disb_temp_id = '{str(pre_disb_temp_id)}'
                # """
                # execute_command(query)

        elif status == '3':
            # Send rejection email
            print('status is 3 proceeding to send rejection email.')
            html_message = f"""
                <html>
                <body style="color: black;">
                    <p>Dear Applicant,</p>
                    <p>We regret to inform you that your loan application with Application ID: <strong>{pre_disb_temp_id}</strong> has been rejected.</p>
                    <p>The reason for rejection is as follows: <strong>{notes or 'No specific reason provided.'}</strong></p>
                    <p>If you have any questions or need further assistance, please contact our support team.</p>
                    <p>Regards,<br><strong>HBL Microfinance Bank</strong></p>
                </body>
                </html>
            """

            from Model_Email import send_email

            success = send_email(
                subject='Loan Application Rejection',
                email_list=['dali27037@gmail.com'],  # Replace with actual email if different
                message=None,
                html_message=html_message,
                attachment=None
            )
            if not success:
                return jsonify({'success': False, 'error': 'Failed to send rejection email'}), 500

        return jsonify({'success': True}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@application.route('/approval-letter/<app_no>')
def approval_letter(app_no):
    print('app_no:- ', app_no)
    try:
        # query = f"""
        #     SELECT Borrower_Name, Application_No, Loan_Amount, ApplicationDate, Father_Husband_Name, CNIC, approved_date
        #     FROM tbl_pre_disbursement_temp
        #     WHERE pre_disb_temp_id = '{str(app_no)}' AND status = '2'
        # """

        query = f"""
            SELECT "Borrower_Name", "Application_No", "Loan_Amount", "ApplicationDate", "Father_Husband_Name", "CNIC", "approved_date", "email_status" 
            FROM tbl_pre_disbursement_temp 
            WHERE "pre_disb_temp_id" = '{str(app_no)}' AND "status" = '2'
        """
        record = fetch_records(query)
        print(record)

        if not record:
            abort(404, description="Approved record not found")



        # Convert logo image to base64
        image_path = os.path.join(application.root_path, 'static', 'images', 'hbl_logo-removebg-preview.png')
        with open(image_path, 'rb') as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        logo_base64 = f'data:image/png;base64,{base64_image}'

        # Convert User sign to base64
        query = f"""
            SELECT u.name, u.email, u.signature, u.scan_sign 
            FROM tbl_users u 
            WHERE u.active = '1' AND u.user_id = '{get_current_user_id()}'
        """
        user = fetch_records(query)

        # Convert scan_sign BLOB to base64 for display if it exists
        sign_base64 = None
        if user[0]['scan_sign']:
            sign_base64 = base64.b64encode(user[0]['scan_sign']).decode('utf-8')
            # print(sign_base64)


        return render_template('approval_letter.html', result=record[0], logo_base64=logo_base64,
                               sign_base64=sign_base64)
    except Exception as e:
        abort(500, description=str(e))
