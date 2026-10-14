from imports import *
from application import application
from decimal import Decimal


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
                # Executive gets the same screen options as an Approver
                'is_approver': is_approver() or is_executive(),
                'is_executive': is_executive(),
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
                'is_approver': is_approver() or is_executive(),
                'is_executive_approver': is_executive_approver(),
                'is_admin': is_admin()
            }
            return render_template('view_rejected_applications.html', result=content)
    except Exception as e:
        print('view-rejected-applications exception:- ', str(e.__dict__))
        print('view-rejected-applications exception:- ', str(e))

    return redirect(url_for('login'))


# Exception Report (task 002): Approver, Executive Approver, Admin, Executive, or anyone with the page permission
def can_view_exception_report():
    return is_login() and (get_current_user_role() in ['2', '3', '4', '5']
                           or PermissionHelper.has_permission(get_current_user_id(), "/exception-report"))


def _exception_report_filters(data):
    keys = ['date_from', 'date_to', 'status', 'decided_by', 'reviewed_by', 'region', 'branch', 'product',
            'limit_min', 'limit_max', 'email']
    filters = {k: str(data.get(k)).strip() for k in keys if data.get(k) not in (None, '')}
    for k in ['limit_min', 'limit_max']:
        if k in filters:
            try:
                float(filters[k])
            except ValueError:
                filters.pop(k)
    filters['include_recommended'] = str(data.get('include_recommended')).lower() in ['1', 'true', 'yes', 'on']
    return filters


@application.route('/exception-report')
def exception_report():
    try:
        if can_view_exception_report():
            # Filter lists come from every exception row the user can see (including recommended ones)
            rows = get_exception_report({'include_recommended': True})
            options = lambda id_key, name_key: sorted({(str(r[id_key]), r[name_key]) for r in rows if r[id_key] is not None and r[name_key]},
                                                      key=lambda x: x[1])
            content = {
                'deciders': options('decided_by_id', 'decided_by'),
                'reviewers': options('reviewed_by_id', 'reviewed_by'),
                'regions': options('region_id', 'region'),
                'branches': options('branch_id', 'branch'),
                'products': sorted({r['product'] for r in rows if r['product']}),
            }
            return render_template('exception_report.html', result=content)
        if is_login():
            return redirect(url_for('index'))
    except Exception as e:
        print('exception-report exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/exception-report/data', methods=['POST'])
def exception_report_data():
    if not can_view_exception_report():
        return jsonify({'success': False, 'error': 'Not allowed'}), 403
    try:
        filters = _exception_report_filters(request.get_json(silent=True) or {})
        records = get_exception_report(filters)
        for r in records:
            for k, v in r.items():
                if isinstance(v, (datetime, date)):
                    r[k] = v.isoformat() if v.year > 1900 else None
                elif isinstance(v, Decimal):
                    r[k] = float(v)
        return jsonify({'success': True, 'records': records,
                        'total_decisions': get_exception_report_total_decisions(filters)})
    except Exception as e:
        print('exception-report/data exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not load the report'}), 500


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
            '3': ('rejected_by', 'rejected_date'),

            '5': ('reviewed_by', 'reviewed_date'),
            '6': ('reviewed_by', 'reviewed_date'),

            '7': ('reviewed_by', 'reviewed_date'),
            '8': ('reviewed_by', 'reviewed_date'),

            '9': ('approved_by', 'approved_date'),
            '10': ('rejected_by', 'rejected_date')
        }

        # Validate status
        if status not in status_fields:
            print(f"Invalid status: {status}")
            return jsonify({'success': False, 'error': 'Invalid status'}), 400

        # Prepare update query with f-strings
        update_field, date_field = status_fields[status]
        # update_field / date_field come from the fixed status_fields map above (never from the request);
        # all values are passed as parameters to prevent SQL injection.
        query = f"""
            UPDATE tbl_pre_disbursement_temp
            SET status = %s, Notes = %s, KFT_Approved_Loan_Limit = %s,
                {update_field} = %s, {date_field} = %s
            WHERE CAST(pre_disb_temp_id AS VARCHAR) = %s
        """

        # Execute update query
        execute_command(query, params=(status, notes, amount_accepted, approved_by, approved_date, str(pre_disb_temp_id)))
        print(f"Executed update query for pre_disb_temp_id: {pre_disb_temp_id}")

        # Handle rejected status (status = '3')
        if status in ['3', '10']:
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
                SELECT %s, %s, 1, %s, %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM tbl_pre_disb_rejected_app WHERE CAST(post_disb_id AS VARCHAR) = %s
                )
            """
            execute_command(insert_query, params=(str(pre_disb_temp_id), status, approved_by, approved_date,
                                                  approved_by, approved_date, str(pre_disb_temp_id)))
            print(f"Inserted rejected app record for post_disb_id: {pre_disb_temp_id}")

        # Exceptional-approval products: reviewer/approver decisions go to the executive approver,
        # who sends the email when they confirm the decision.
        is_exceptional_product = requires_executive_approval(pre_disb_temp_id)
        awaiting_executive = get_current_user_role() in ['1', '2'] and is_exceptional_product
        if awaiting_executive:
            print(f"Email held for executive approval: {pre_disb_temp_id}")

        if is_exceptional_product:
            # Executive approver / executive / admin confirming a final decision records the executive approval.
            # A reviewer/approver final decision puts the application in the executive's queue
            # (exec_approval_pending = 1); any other change takes it out until it is decided again.
            if get_current_user_role() in ['3', '4', '5'] and status in ['2', '3', '9', '10']:
                exec_query = """
                    UPDATE tbl_pre_disbursement_temp
                    SET exec_approved_by = %s, exec_approved_date = %s,
                        exec_approval_pending = NULL
                    WHERE CAST(pre_disb_temp_id AS VARCHAR) = %s
                """
                exec_params = (approved_by, approved_date, str(pre_disb_temp_id))
            else:
                pending = 1 if awaiting_executive and status in ['2', '3', '9', '10'] else None
                exec_query = """
                    UPDATE tbl_pre_disbursement_temp
                    SET exec_approved_by = NULL, exec_approved_date = NULL,
                        exec_approval_pending = %s
                    WHERE CAST(pre_disb_temp_id AS VARCHAR) = %s
                """
                exec_params = (pending, str(pre_disb_temp_id))
            execute_command(exec_query, params=exec_params)

        if status in ['3', '10'] and not awaiting_executive:
            from Model_Email import send_email
            query = """
                select pdt."Application_No", pdt."Borrower_Name", pdt."Requested_Loan_Amount", pdt."LoanProductCode", u1.email as reviewed_by_email, u2.email as rejected_by_email,
                b.email, b.branch, b.branch_name
                from tbl_pre_disbursement_temp pdt
                INNER JOIN tbl_branches b ON pdt."Branch_Name" LIKE CONCAT('%%', b.branch_code, '%%') AND b.live_branch = '1'
                LEFT JOIN tbl_users u1 ON u1.user_id = pdt.reviewed_by
                LEFT JOIN tbl_users u2 ON u2.user_id = pdt.rejected_by
                where CAST(pdt.pre_disb_temp_id AS VARCHAR) = %s and pdt.status IN ('3', '10')
            """
            result = fetch_records(query, params=(str(pre_disb_temp_id),))

            if len(result) > 0:
                result = result[0]
                reference_no = result.get('Application_No', None)
                Borrower_Name = result.get('Borrower_Name', None)
                Requested_Loan_Amount = result.get('Requested_Loan_Amount', None)
                LoanProductCode = result.get('LoanProductCode', None)
                reviewed_by_email = result.get('reviewed_by_email', None)
                rejected_by_email = result.get('rejected_by_email', None)
                branch_email = result.get('email', None)
                branch = result.get('branch', None)
                branch_name = result.get('branch_name', None)

                # ==================== HTML EMAIL TEMPLATE ====================
                html_body = f"""
                    <!DOCTYPE html>
                    <html lang="en">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>Query Raised - Loan Application</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                            .container {{ max-width: 650px; margin: 0 auto; padding: 20px; }}
                            .header {{ background-color: #d32f2f; color: white; padding: 15px; text-align: center; }}
                            .content {{ padding: 20px; border: 1px solid #ddd; }}
                            .footer {{ text-align: center; font-size: 12px; color: #777; margin-top: 20px; }}
                            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
                            th {{ background-color: #f5f5f5; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="header">
                                <h2>Query Raised – Loan Application Review</h2>
                            </div>

                            <div class="content">
                                <p>Dear Manager <strong>{branch_name} BRANCH</strong>,</p>

                                <p>This is with reference to the subject case forwarded for our review. During the assessment, a few clarifications are required from the branch before we may proceed further with the approval process.</p>

                                <table>
                                    <tr>
                                        <th>Application Reference No</th>
                                        <td>{reference_no}</td>
                                    </tr>
                                    <tr>
                                        <th>Applicant Name</th>
                                        <td>{Borrower_Name}</td>
                                    </tr>
                                    <tr>
                                        <th>Requested Amount</th>
                                        <td>PKR {Requested_Loan_Amount}/-</td>
                                    </tr>
                                    <tr>
                                        <th>Product</th>
                                        <td>{LoanProductCode}</td>
                                    </tr>
                                </table>

                                <h3>Queries / Clarifications Required:</h3>
                                <p style="background-color: #fff3e0; padding: 15px; border-left: 4px solid #ff9800;">
                                    {notes if notes else 'No specific notes provided.'}
                                </p>

                                <p>We request you to share the above information and supporting documents at the earliest so that we may proceed with the final evaluation of the case.</p>

                                <p>Thank you for your cooperation and continued support.</p>
                            </div>

                            <div class="footer">
                                <p>Kind regards,<br>
                                <strong>Khushali Foundation</strong><br>
                                </p>
                            </div>
                        </div>
                    </body>
                    </html>
                """

                # ==================== SEND EMAIL ====================
                subject = f"Query Raised – Loan Application Review (Ref: {reference_no}, borrower name: {Borrower_Name})"

                # Prepare recipient list
                email_list = [branch_email] if branch_email else []

                # Prepare CC list
                cc_list = []
                if reviewed_by_email:
                    cc_list.append(reviewed_by_email)
                if rejected_by_email and rejected_by_email != reviewed_by_email:
                    cc_list.append(rejected_by_email)

                # Send email using your existing method
                email_sent = send_email(
                    subject=subject,
                    email_list=email_list,
                    message="",  # Plain text version (optional)
                    html_message=html_body,  # HTML version
                    add_cc_list=True,
                    cc_list=cc_list
                )

                if email_sent:
                    print(f"Rejection query email sent successfully to {branch_email}")
                else:
                    print("Failed to send rejection query email")

        # Return success response
        print("Update completed successfully")
        exec_approved = is_exceptional_product and not awaiting_executive and status in ['2', '3', '9', '10']
        return jsonify({
            'success': True,
            'status': str(status),
            'awaiting_executive': awaiting_executive,
            'exec_approval_pending': 1 if awaiting_executive and status in ['2', '3', '9', '10'] else None,
            'exec_approved_by': session.get('name') if exec_approved else None,
            'exec_approved_date': approved_date if exec_approved else None
        }), 200

    except Exception as e:
        # Log error and return failure response
        print(f"Error occurred: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@application.route('/approval-letter/<app_no>')
def approval_letter(app_no):
    print('app_no:- ', app_no)
    try:
        if not is_login():
            return redirect(url_for('login'))
        # query = f"""
        #     SELECT Borrower_Name, Application_No, Loan_Amount, ApplicationDate, Father_Husband_Name, CNIC, approved_date
        #     FROM tbl_pre_disbursement_temp
        #     WHERE pre_disb_temp_id = '{str(app_no)}' AND status = '2'
        # """

        query = """
            SELECT "Borrower_Name", "Application_No", "Loan_Amount", KFT_Approved_Loan_Limit, "ApplicationDate", "Father_Husband_Name", "CNIC", "approved_date", "email_status" 
            FROM tbl_pre_disbursement_temp 
            WHERE CAST("pre_disb_temp_id" AS VARCHAR) = %s AND "status" IN ('2', '9')
        """
        record = fetch_records(query, params=(str(app_no),))
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
    if not is_login():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    application_no = request.args.get('application_no')
    if not application_no:
        return jsonify({'success': False, 'error': 'Missing application_no'}), 400

    images = fetch_records("""
        SELECT 
            pd_ai_id,
            cnic,
            customer_name,
            created_date
        FROM tbl_pre_disbursement_application_images
        WHERE application_no = %s
        ORDER BY created_date DESC
    """, params=(application_no,))

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
    if not is_login():
        return "Unauthorized", 401
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


@application.route('/manage-approval-letters')
def manage_approval_letters():
    """Page to list and download approval letters for approved applications"""
    try:
        if is_login():
            # Fetch all applications with status 2 or 9
            query = """
                SELECT 
                    pre_disb_temp_id,
                    "Application_No",
                    "Borrower_Name",
                    "CNIC",
                    "Requested_Loan_Amount",
                    KFT_Approved_Loan_Limit,
                    "ApplicationDate",
                    status,
                    approved_date,
                    approved_by,
                    email_status
                FROM tbl_pre_disbursement_temp 
                WHERE status IN ('2', '9')
                ORDER BY approved_date DESC
            """
            approved_applications = fetch_records(query)

            content = {
                'approved_applications': approved_applications,
                'is_admin': is_admin(),
                'is_reviewer': is_reviewer(),
                'is_approver': is_approver() or is_executive(),
                'is_executive_approver': is_executive_approver()
            }
            return render_template('manage_approval_letters.html', result=content)
    except Exception as e:
        print('manage-approval-letters exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/print-approval-letter/<app_no>')
def print_approval_letter(app_no):
    """Print-friendly version of approval letter"""
    try:
        if is_login():
            query = """
                SELECT "Borrower_Name", "Application_No", "Loan_Amount", KFT_Approved_Loan_Limit, 
                       "ApplicationDate", "Father_Husband_Name", "CNIC", "approved_date", "email_status" 
                FROM tbl_pre_disbursement_temp 
                WHERE CAST("pre_disb_temp_id" AS VARCHAR) = %s AND "status" IN ('2', '9')
            """
            record = fetch_records(query, params=(str(app_no),))

            if not record:
                abort(404, description="Approved record not found")

            # Convert logo to base64
            image_path = os.path.join(application.root_path, 'static', 'images', 'hbl_logo-removebg-preview.png')
            with open(image_path, 'rb') as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            logo_base64 = f'data:image/png;base64,{base64_image}'

            # Get user signature
            query = f"""
                SELECT u.name, u.email, u.signature, u.scan_sign 
                FROM tbl_users u 
                WHERE u.active = '1' AND u.user_id = '{get_current_user_id()}'
            """
            user = fetch_records(query)

            sign_base64 = None
            if user and user[0].get('scan_sign'):
                sign_base64 = base64.b64encode(user[0]['scan_sign']).decode('utf-8')

            return render_template('print_approval_letter.html',
                                   result=record[0],
                                   logo_base64=logo_base64,
                                   sign_base64=sign_base64)
    except Exception as e:
        print('print-approval-letter exception:- ', str(e))
        abort(500, description=str(e))


@application.route('/download-approval-letter/<app_no>')
def download_approval_letter(app_no):
    """Automatically download as PDF using browser's print-to-PDF"""
    try:
        if not is_login():
            return redirect(url_for('login'))

        # Fetch your data
        query = """
            SELECT "Borrower_Name", "Application_No", "Loan_Amount", KFT_Approved_Loan_Limit, 
                   "ApplicationDate", "Father_Husband_Name", "CNIC", "approved_date", "email_status" 
            FROM tbl_pre_disbursement_temp 
            WHERE CAST("pre_disb_temp_id" AS VARCHAR) = %s AND "status" IN ('2', '9')
        """
        record = fetch_records(query, params=(str(app_no),))

        if not record:
            return jsonify({'error': 'Record not found'}), 404

        # Convert logo to base64
        image_path = os.path.join(application.root_path, 'static', 'images', 'hbl_logo-removebg-preview.png')
        with open(image_path, 'rb') as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        logo_base64 = f'data:image/png;base64,{base64_image}'

        # Get user signature
        query = f"""
            SELECT u.name, u.email, u.signature, u.scan_sign 
            FROM tbl_users u 
            WHERE u.active = '1' AND u.user_id = '{get_current_user_id()}'
        """
        user = fetch_records(query)

        sign_base64 = None
        if user and user[0].get('scan_sign'):
            sign_base64 = base64.b64encode(user[0]['scan_sign']).decode('utf-8')

        # Return template with auto-print JavaScript
        return render_template('lien_letter_pdf.html',
                               result=record[0],
                               logo_base64=logo_base64,
                               sign_base64=sign_base64)

    except Exception as e:
        print('download-approval-letter exception:- ', str(e))
        abort(500, description=str(e))
