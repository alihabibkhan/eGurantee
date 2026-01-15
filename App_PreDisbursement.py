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


@application.route('/view-rejected-applications')
def view_rejected_applications():
    try:
        if is_login():
            content = {
                'get_temp_pre_disbursement': view_all_rejected_application(),
                'is_user_have_sign': is_user_have_sign(),
                'occupation_list': get_all_occupations(),
                'experience_ranges_list': get_all_experience_ranges(),
                'get_all_loan_metrics': get_all_loan_metrics(),
                'is_reviewer': is_reviewer(),
                'is_approver': is_approver(),
                'is_executive_approver': is_executive_approver(),
                'is_admin': is_admin()
            }
            return render_template('view_rejected_applications.html', result=content)
    except Exception as e:
        print('view-rejected-applications exception:- ', str(e.__dict__))
        print('view-rejected-applications exception:- ', str(e))

    return redirect(url_for('login'))



@application.route('/update-pre-disbursement-temp', methods=['POST'])
def update_pre_disbursement_temp():
    """
    Update pre-disbursement temporary record based on status using f-strings.
    """
    try:
        # Check if user is authenticated
        if not is_login():
            print("Unauthorized access attempt")
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        # Get JSON data from request
        data = request.get_json()
        print(f"Received data: {data}")

        # Extract required fields
        pre_disb_temp_id = data.get('pre_disb_temp_id')
        status = str(data.get('status'))
        notes = data.get('Notes')
        amount_accepted = data.get('amount_accepted')
        print(f"Extracted: id={pre_disb_temp_id}, status={status}, notes={notes}, amount={amount_accepted}")

        # Validate required fields
        if not pre_disb_temp_id or not status:
            print("Missing required fields")
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Get current user and timestamp
        approved_by = str(get_current_user_id())
        approved_date = str(datetime.now())
        print(f"User: {approved_by}, Date: {approved_date}")

        # Define status-to-field mapping
        status_fields = {
            '2': ('approved_by', 'approved_date'),
            '5': ('reviewed_by', 'reviewed_date'),
            '6': ('reviewed_by', 'reviewed_date'),
            '3': ('rejected_by', 'rejected_date')
        }

        # Validate status
        if status not in status_fields:
            print(f"Invalid status: {status}")
            return jsonify({'success': False, 'error': 'Invalid status'}), 400

        # Prepare update query with f-strings
        update_field, date_field = status_fields[status]
        query = f"""
            UPDATE tbl_pre_disbursement_temp
            SET status = '{status}', Notes = '{notes}', KFT_Approved_Loan_Limit = '{amount_accepted}',
                {update_field} = '{approved_by}', {date_field} = '{approved_date}'
            WHERE pre_disb_temp_id = '{pre_disb_temp_id}'
        """

        # Execute update query
        execute_command(query)
        print(f"Executed update query for pre_disb_temp_id: {pre_disb_temp_id}")

        # Handle rejected status (status = '3')
        if status == '3':
            insert_query = f"""
                INSERT INTO tbl_pre_disb_rejected_app (
                    post_disb_id,
                    application_status,
                    status,
                    created_by,
                    created_date,
                    modified_by,
                    modified_date
                )
                SELECT
                    '{pre_disb_temp_id}',
                    '{status}',
                    1,
                    '{approved_by}',
                    '{approved_date}',
                    '{approved_by}',
                    '{approved_date}'
                WHERE NOT EXISTS (
                    SELECT 1 FROM tbl_pre_disb_rejected_app WHERE post_disb_id = '{pre_disb_temp_id}'
                )
            """
            execute_command(insert_query)
            print(f"Inserted rejected app record for post_disb_id: {pre_disb_temp_id}")

        # Return success response
        print("Update completed successfully")
        return jsonify({'success': True, 'status': str(status)}), 200

    except Exception as e:
        # Log error and return failure response
        print(f"Error occurred: {str(e)}")
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
            SELECT "Borrower_Name", "Application_No", "Loan_Amount", KFT_Approved_Loan_Limit, "ApplicationDate", "Father_Husband_Name", "CNIC", "approved_date", "email_status" 
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



@application.route('/get_application_images')
def get_application_images():
    application_no = request.args.get('application_no')
    if not application_no:
        return jsonify({'success': False, 'error': 'Missing application_no'}), 400

    # Using f-string as requested (but note: not ideal for security)
    # In production, strongly prefer parameterized queries
    images = fetch_records(f"""
        SELECT 
            pd_ai_id,
            cnic,
            customer_name,
            created_date
        FROM tbl_pre_disbursement_application_images
        WHERE application_no = '{application_no}'
        ORDER BY created_date DESC
    """)

    result = []
    for img in images or []:
        result.append({
            'url': url_for('serve_pre_image', image_id=img['pd_ai_id']),
            'filename': f"{img['customer_name'] or 'Customer'}_{img['cnic'] or 'Unknown'}_{img['pd_ai_id']}.jpg",
            'uploaded': img['created_date'].strftime('%Y-%m-%d %H:%M') if img.get('created_date') else None,
            'cnic': img.get('cnic'),
            'customer_name': img.get('customer_name')
        })

    return jsonify({
        'success': True,
        'images': result
    })


@application.route('/pre_image/<int:image_id>')
def serve_pre_image(image_id):
    # Again using f-string as requested
    rows = fetch_records(f"""
        SELECT image_data
        FROM tbl_pre_disbursement_application_images
        WHERE pd_ai_id = {image_id}
    """)

    if not rows or not rows[0].get('image_data'):
        return "Image not found", 404

    image_data = rows[0]['image_data']

    # Handle possible memoryview (common when bytea is fetched)
    if isinstance(image_data, memoryview):
        image_data = image_data.tobytes()

    # Or if it's already bytes, use directly
    if not isinstance(image_data, bytes):
        return "Invalid image data format", 500

    return send_file(
        io.BytesIO(image_data),
        mimetype='image/jpeg',          # Adjust if you know the actual format
        as_attachment=False,
        download_name=f"pre_image_{image_id}.jpg"
    )