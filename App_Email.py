from imports import *
from application import application


# @application.route('/send-email', methods=['POST'])
# def send_email():
#     try:
#         if not is_login() and not (is_admin() or is_executive_approver() or is_approver()):
#             return jsonify({'success': False, 'error': 'Unauthorized'}), 401
#         data = request.get_json()
#         pre_disb_temp_id = data.get('app_no')
#         recipient_email = data.get('recipient_email')
#
#         if not pre_disb_temp_id or not recipient_email or '@' not in recipient_email:
#             return jsonify({'success': False, 'error': 'Invalid application number or email'}), 400
#
#         query = f"""
#             SELECT DISTINCT "Borrower_Name", "Application_No", "Loan_Amount", "ApplicationDate",
#             "Father_Husband_Name", "CNIC", "approved_date",
#             KFT_Approved_Loan_Limit, "Collage_Univeristy", "Student_Name", "LoanProductCode", b.branch_name, b.branch_manager
#             FROM tbl_pre_disbursement_temp
#             LEFT JOIN tbl_branches b on "Branch_Name" LIKE CONCAT('%', b."branch_code", '%') AND b."live_branch" = '1'
#             WHERE "pre_disb_temp_id" = '{str(pre_disb_temp_id)}' AND "status" = '2'
#         """
#         record = fetch_records(query)
#
#         if not record:
#             return jsonify({'success': False, 'error': 'Approved record not found'}), 404
#
#         query = f"""
#                     UPDATE tbl_pre_disbursement_temp
#                     SET email_status = 2
#                     WHERE pre_disb_temp_id = '{str(pre_disb_temp_id)}';
#                 """
#         execute_command(query, is_print=True)
#
#         # Convert image to base64
#         image_path = os.path.join(application.root_path, 'static', 'images', 'hbl_logo-removebg-preview.png')
#         with open(image_path, 'rb') as image_file:
#             base64_image = base64.b64encode(image_file.read()).decode('utf-8')
#         logo_base64 = f'data:image/png;base64,{base64_image}'
#
#         # Convert User sign to base64
#         query = f"""
#                     SELECT u.name, u.email, u.signature, u.scan_sign
#                     FROM tbl_users u
#                     WHERE u.active = '1' AND u.user_id = '{get_current_user_id()}'
#                 """
#         user = fetch_records(query)
#
#         # Convert scan_sign BLOB to base64 for display if it exists
#         sign_base64 = None
#         if user[0]['scan_sign']:
#             sign_base64 = base64.b64encode(user[0]['scan_sign']).decode('utf-8')
#             print(sign_base64)
#
#         # Generate PDF using xhtml2pdf
#         html_content = render_template('approval_letter.html', result=record[0], logo_base64=logo_base64,
#                                        sign_base64=sign_base64)
#         buffer = BytesIO()
#         pisa.CreatePDF(BytesIO(html_content.encode()), buffer)
#         pdf = buffer.getvalue()
#         buffer.close()
#
#         # Send email with attachment
#         message = f"Dear {record[0].get('Borrower_Name', 'User')},\n\nPlease find attached the loan approval letter for Application No: {record[0].get('Application_No', 'N/A')}.\n\nRegards,\nHBL Microfinance Bank"
#         from Model_Email import send_email
#
#         success = send_email(
#             subject='Loan Approval Letter',
#             email_list=[recipient_email],
#             message=message,
#             attachment=pdf,
#             filename='approval_letter.pdf',
#             content_type='application/pdf',
#             add_cc_list=True
#         )
#
#         if success:
#             return jsonify({'success': True, 'message': 'Email sent successfully'})
#         else:
#             return jsonify({'success': False, 'error': 'Failed to send email'}), 500
#     except Exception as e:
#         return jsonify({'success': False, 'error': str(e)}), 500


@application.route('/send-email', methods=['POST'])
def send_email():
    try:
        if not is_login() and not (is_admin() or is_executive_approver() or is_approver()):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        data = request.get_json()
        pre_disb_temp_id = data.get('app_no')
        recipient_email = data.get('recipient_email')

        if not pre_disb_temp_id or not recipient_email or '@' not in recipient_email:
            return jsonify({'success': False, 'error': 'Invalid application number or email'}), 400

        query = f"""
            SELECT DISTINCT "Borrower_Name", "Application_No", "Loan_Amount", "ApplicationDate", 
            "Father_Husband_Name", "CNIC", "approved_date", 
            KFT_Approved_Loan_Limit, "Collage_Univeristy", "Student_Name", "LoanProductCode", b.branch_name, b.branch_manager
            FROM tbl_pre_disbursement_temp
            LEFT JOIN tbl_branches b on "Branch_Name" LIKE CONCAT('%', b."branch_code", '%') AND b."live_branch" = '1'
            WHERE "pre_disb_temp_id" = '{str(pre_disb_temp_id)}' AND "status" = '2'
        """
        record = fetch_records(query)

        print(record)

        if not record:
            return jsonify({'success': False, 'error': 'Approved record not found'}), 404

        query = f"""
                    UPDATE tbl_pre_disbursement_temp
                    SET email_status = 2
                    WHERE pre_disb_temp_id = '{str(pre_disb_temp_id)}';
                """
        execute_command(query, is_print=True)

        # Convert image to base64
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
            print(sign_base64)

        # Generate PDF using xhtml2pdf
        html_content = render_template('approval_letter.html', result=record[0], logo_base64=logo_base64,
                                       sign_base64=sign_base64)
        buffer = BytesIO()
        pisa.CreatePDF(BytesIO(html_content.encode()), buffer)
        pdf = buffer.getvalue()
        buffer.close()

        # Prepare email subject and body based on LoanProductCode
        loan_product_code = record[0].get('LoanProductCode', '').lower()
        borrower_name = record[0].get('Borrower_Name', 'User')
        branch_name = record[0].get('branch_name', '').lower().capitalize() + ' Branch'
        branch_manager = record[0].get('branch_manager', 'Manager')
        loan_product_display = record[0].get('LoanProductCode', 'N/A').replace('_', ' ')
        kft_approved_limit = f"PKR {record[0].get('kft_approved_loan_limit', '200,000')}/-"

        subject = f"Approval of {borrower_name} – {loan_product_display} – {branch_name}"

        if loan_product_code.__contains__('student'):
            message = f"""
<b>Dear HBLMFB {branch_manager}</b>,
<br/><br/>
Please find attached the approval for the subject case that was forwarded for our review. Based 
on satisfactory verification, strong recommendations, and all other checks conducted by the KFT 
Member and HBL MFB branch, the following loan has been approved:
<br/><br/>
<b>Applicant Name</b>: {borrower_name}
<br/>
<b>Amount</b>: {kft_approved_limit}
<br/>
<b>University Name</b>: {record[0].get('Collage_Univeristy', 'N/A')}
<br/>
<b>Student Name</b>: {record[0].get('Student_Name', 'N/A')}
<br/><br/>
Please note: Any incremental charges than the above amount to be borne by the applicant. 
Disbursement to be made in the name of the institution through PO/DD/BC only. Kindly confirm 
once the disbursement is made in the beneficiary’s account.
<br/><br/>
<b>
Note: Kindly obtain 3PG before disbursement (if required) and share acknowledgement receipt 
of the Pay Order/Demand Draft/Banker’s Cheque from the college/University.
</b>
<br/><br/>
Thank you for your cooperation and continued support.
<br/><br/>
Best Regards,
<br/>
Khushali Foundation Trust (KFT)
Community Helping Community
            """
        else:
            message = f"""
                
<b>Dear HBLMFB {branch_manager}</b>,
<br/>
<br/>
Please find attached the approval for the subject case that was forwarded for our review. Based 
on satisfactory verification, strong recommendations, and all other checks conducted by the KFT 
Member and HBL MFB branch, the following loan has been approved:
<br/>
<br/>
<b>Applicant Name</b>: {borrower_name}
<br/>
<b>Amount</b>: {kft_approved_limit}
<br/>
<br/>
<b>
Note: Kindly obtain 3PG before disbursement (if required). Enhancement to be considered after 
completion of existing requested tenure. Early adjustment of loans to be followed by cooling-off 
period for future enhancements
</b>
<br/>
<br/>
Thank you for your cooperation and continued support.
<br/>
<br/>
<b>Best Regards<b/>,
<br/>
Khushali Foundation Trust (KFT)
Community Helping Community
        """

        from Model_Email import send_email

        # Send email with attachment
        success = send_email(
            subject=subject,
            email_list=[recipient_email],
            message=None,
            html_message=message,
            attachment=pdf,
            filename='approval_letter.pdf',
            content_type='application/pdf',
            add_cc_list=True
        )

        if success:
            return jsonify({'success': True, 'message': 'Email sent successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to send email'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
