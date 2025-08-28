from imports import *
from application import application
from application import allowed_file


@application.route('/manage-file', methods=['GET', 'POST'])
def manage_file():
    if request.method == 'POST':
        action_type = request.form.get('action_type')
        file_type = request.form.get('file_type') or session.get('file_type')

        if not file_type:
            flash('Please select a file type.', 'danger')
            return redirect(url_for('manage_file'))

        if action_type == 'validate':
            return handle_validation(file_type)
        elif action_type == 'upload':
            return handle_upload()

    return render_template('upload.html', view='upload')


def handle_validation(file_type):
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('manage_file'))

    files = request.files.getlist('file')
    if not files or all(f.filename == '' for f in files):
        flash('No file selected.', 'danger')
        return redirect(url_for('manage_file'))

    if file_type == 'pre_disbursement' and len(files) > 1:
        flash('Only one file allowed for Pre Disbursement.', 'danger')
        return redirect(url_for('manage_file'))
    elif file_type == 'post_disbursement' and (len(files) != 1 and len(files) != 2):
        flash('Exactly one or two files are required for Post Disbursement.', 'danger')
        return redirect(url_for('manage_file'))

    saved_files = []
    all_sheets = []
    all_counts = {}
    has_pre = False
    has_post = False

    for file in files:
        if not allowed_file(file.filename):
            flash(f'File {file.filename}: Only .xlsx files are allowed.', 'danger')
            return redirect(url_for('manage_file'))

        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        saved_files.append(filepath)

        success, result = validate_excel(filepath, file_type)
        if not success:
            for saved_file in saved_files:
                try:
                    os.remove(saved_file)
                except Exception:
                    pass
            flash(result, 'warning')
            return redirect(url_for('manage_file'))

        all_sheets.extend(result['sheets_available'])
        all_counts.update(result['record_counts'])
        has_pre = has_pre or result['has_pre']
        has_post = has_post or result['has_post']

    session['current_files'] = saved_files
    session['has_pre'] = has_pre
    session['has_post'] = has_post
    session['file_type'] = file_type

    return render_template('upload.html',
                           view='validation_result',
                           filename=', '.join([os.path.basename(f) for f in saved_files]),
                           sheets=all_sheets,
                           counts=all_counts,
                           file_type=file_type)

def validate_excel(filepath, file_type):
    try:
        pre_headers = [
            'Branch_Name', 'Branch Area', 'Application_No', 'ApplicationDate',
            'Bcc Approval Date', 'LoanProductCode', 'collateral_type', 'Credit History Ecib',
            'Loan Cycle', 'Borrower Name', 'Student_Name', 'Father/Husband Name',
            'Student Relation With Borrower', 'Student Co Borrower Gender', 'Gender', 'CNIC',
            'Contact No', 'Type of Business', 'Nature of Business', 'Business Expense Description',
            'Business Premises', 'Business Experiense (Since)', 'Premises', 'Purpose of Loan',
            'annual_income', 'Annual Business Incomes', 'Annual Expenses', 'Annual Disposable Income',
            'Monthly Repayment Capacity', 'Loan Amount', 'Requested Loan Amount', 'education_level',
            'Collage/Univeristy', 'enrollment_status', 'Loan_Status', 'Current Residencial',
            'Permanent Residencial', 'Dbr', 'Enterprise Premises', 'Existing Loan Number',
            'Existing Loan Limit', 'Existing Loan Status', 'Existing Outstanding Loan Schedules',
            'Experiense Start Date', 'Family Monthly Income', 'KF Remarks', 'No Of Family Members',
            'Residance Type', 'Tenor Of Month'
        ]

        post_headers = [
            'MIS_DATE', 'Area', 'Branch Code', 'Branch Name', 'CNIC', 'Gender', 'Address',
            'Mobile No', 'Loan No', 'Loan Title', 'Product Code', 'Booked On', 'Disbursed Amount',
            'Principal Outstanding', 'Markup Outstanding', 'Repayment Type', 'Sector', 'Purpose',
            'Loan Status', 'Overdue Days', 'Loan Closed On', 'Collateral Title'
        ]

        expected_headers = pre_headers if file_type == 'pre_disbursement' else post_headers

        xls = pd.ExcelFile(filepath)
        sheets = xls.sheet_names
        record_counts = {}
        has_pre = file_type == 'pre_disbursement'
        has_post = file_type == 'post_disbursement'

        for sheet_name in sheets:
            df = pd.read_excel(xls, sheet_name=sheet_name, dtype={'Branch Code': str, 'Application_No': str}).fillna('')
            if df.columns.duplicated().any():
                return False, f"Duplicate column names found in sheet {sheet_name}: {df.columns[df.columns.duplicated()].tolist()}"

            # missing_headers = [h for h in expected_headers if h not in df.columns]
            # if missing_headers:
            #     #flash(f"Sheet '{sheet_name}' is missing headers: {', '.join(missing_headers)}. Adding as blanks.",'warning')
            #     for col in missing_headers:
            #         df[col] = ''

            record_counts[sheet_name] = len(df)
            print(f"Sheet '{sheet_name}' identified as {file_type} with {len(df)} records")

        return True, {
            'sheets_available': sheets,
            'record_counts': record_counts,
            'has_pre': has_pre,
            'has_post': has_post
        }
    except Exception as e:
        return False, f"Error reading Excel file: {str(e)}"


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def safe_remove(filepath):
    os.remove(filepath)
    print(f"File {filepath} deleted successfully.")


def handle_upload():
    if 'current_files' not in session or not session['current_files']:
        flash('No validated files found. Please validate a file first.', 'danger')
        return redirect(url_for('manage_file'))

    filepaths = session['current_files']
    has_pre = session.get('has_pre', False)
    has_post = session.get('has_post', False)

    success, result = process_upload()

    if not success:
        flash(result, 'warning')
        return redirect(url_for('manage_file'))

    try:
        for filepath in filepaths:
            safe_remove(filepath)
    except Exception as e:
        print(f"Failed to delete file: {e}")

    session.pop('current_files', None)
    session.pop('has_pre', None)
    session.pop('has_post', None)
    session.pop('file_type', None)

    if result['summary_path']:
        session['summary_file'] = result['summary_path']

    return render_template('upload.html',
                           view='upload_result',
                           duplicates=result['duplicates'],
                           new_records=result['new_records'],
                           has_summary=result['summary_path'] is not None)


def process_upload():
    file_type = session.get('file_type')
    filepaths = session['current_files']
    duplicates = {}
    new_records = {}
    summary_path = None

    pre_headers = [
        'branch_name', 'branch_area', 'application_no', 'applicationdate',
        'bcc_approval_date', 'loanproductcode', 'collateral_type', 'credit_history_ecib',
        'loan_cycle', 'borrower_name', 'student_name', 'father_husband_name',
        'student_relation_with_borrower', 'student_co_borrower_gender', 'gender', 'cnic',
        'contact_no', 'type_of_business', 'nature_of_business', 'business_expense_description',
        'business_premises', 'business_experiense_(since)', 'premises', 'purpose_of_loan',
        'annual_income', 'annual_business_incomes', 'annual_expenses', 'annual_disposable_income',
        'monthly_repayment_capacity', 'loan_amount', 'requested_loan_amount', 'education_level',
        'collage_univeristy', 'enrollment_status', 'loan_status', 'current_residencial',
        'permanent_residencial', 'dbr', 'enterprise_premises', 'existing_loan_number',
        'existing_loan_limit', 'existing_loan_status', 'existing_outstanding_loan_schedules',
        'experiense_start_date', 'family_monthly_income', 'kf_remarks', 'no_of_family_members',
        'residance_type', 'tenor_of_month'
    ]

    post_headers = [
        'mis_date', 'area', 'branch_code', 'branch_name', 'cnic', 'gender', 'address',
        'mobile_no', 'loan_no', 'loan_title', 'product_code', 'booked_on', 'disbursed_amount',
        'principal_outstanding', 'markup_outstanding', 'repayment_type', 'sector', 'purpose',
        'loan_status', 'overdue_days', 'loan_closed_on', 'collateral_title'
    ]

    try:
        for filepath in filepaths:
            xl = pd.ExcelFile(filepath)
            sheet_names = xl.sheet_names

            for sheet_name in sheet_names:
                df = pd.read_excel(filepath, sheet_name=sheet_name,
                                   dtype={'Branch Code': str, 'Application_No': str}).fillna('')
                df.columns = [col.strip().lower().replace('/', '_').replace(' ', '_') for col in df.columns]

                if df.columns.duplicated().any():
                    raise ValueError(
                        f"Duplicate column names found in sheet {sheet_name}: {df.columns[df.columns.duplicated()].tolist()}")

                if file_type == 'pre_disbursement':
                    expected_headers = pre_headers
                    table_name = 'tbl_pre_disbursement_temp'
                    key_column = 'application_no'
                    existing_records = fetch_records('SELECT "Application_No", "status" FROM tbl_pre_disbursement_temp')
                    existing_app_nos = {str(row['Application_No']): str(row['status']) for row in existing_records}
                else:
                    expected_headers = post_headers
                    table_name = 'tbl_post_disbursement'
                    key_column = 'loan_no'
                    existing_records = fetch_records(f'SELECT "{key_column}" FROM {table_name}')
                    existing_app_nos = {str(row[key_column]): None for row in existing_records}

                missing_headers = [h for h in expected_headers if h not in df.columns]
                if missing_headers:
                    flash(f"Sheet '{sheet_name}' is missing headers: {', '.join(missing_headers)}. Adding as blanks.",
                          'warning')
                    for col in missing_headers:
                        df[col] = ''

                duplicates[sheet_name] = []
                new_records[sheet_name] = []

                for _, row in df.iterrows():
                    key = str(row[key_column])
                    if key in existing_app_nos and (file_type != 'pre_disbursement' or existing_app_nos[key] != '3'):
                        duplicates[sheet_name].append(row)
                    else:
                        new_records[sheet_name].append(row)

                duplicates[sheet_name] = pd.DataFrame(duplicates[sheet_name], columns=df.columns)
                new_records[sheet_name] = pd.DataFrame(new_records[sheet_name], columns=df.columns)

                if len(new_records[sheet_name]) > 0:
                    date_columns = ['applicationdate', 'bcc_approval_date', 'business_experiense_(since)',
                                    'experiense_start_date'] if file_type == 'pre_disbursement' else ['mis_date',
                                                                                                      'booked_on',
                                                                                                      'loan_closed_on']
                    for col in date_columns:
                        if col in new_records[sheet_name].columns:
                            new_records[sheet_name][col] = new_records[sheet_name][col].apply(parse_excel_date)

                    for rec in new_records[sheet_name].to_dict('records'):
                        if file_type == 'pre_disbursement' and str(rec['application_no']) not in ['', 'NaN', 'None']:
                            query = f"""
                                INSERT INTO tbl_pre_disbursement_temp (
                                    "Application_No", "Annual_Business_Incomes", "Annual_Disposable_Income",
                                    "Annual_Expenses", "ApplicationDate", "Bcc_Approval_Date", "Borrower_Name", 
                                    "Branch_Area", "Branch_Name", "Business_Expense_Description", 
                                    "Business_Experiense_Since", "Business_Premises", "CNIC", "Collage_Univeristy",
                                    "Collateral_Type", "Contact_No", "Credit_History_Ecib", "Current_Residencial",
                                    "Dbr", "Education_Level", "Enrollment_Status", "Enterprise_Premises",
                                    "Existing_Loan_Number", "Existing_Loan_Limit", "Existing_Loan_Status",
                                    "Existing_Outstanding_Loan_Schedules", "Experiense_Start_Date",
                                    "Family_Monthly_Income", "Father_Husband_Name", "Gender", "KF_Remarks",
                                    "Loan_Amount", "Loan_Cycle", "LoanProductCode", "Loan_Status",
                                    "Monthly_Repayment_Capacity", "Nature_Of_Business", "No_Of_Family_Members",
                                    "Permanent_Residencial", "Premises", "Purpose_Of_Loan", "Requested_Loan_Amount",
                                    "Residance_Type", "Student_Name", "Student_Co_Borrower_Gender", 
                                    "Student_Relation_With_Borrower", "Tenor_Of_Month", "Type_of_Business",
                                    "annual_income", "status", "uploaded_by", "uploaded_date"
                                ) VALUES (
                                    '{rec['application_no']}', '{rec['annual_business_incomes']}', '{rec['annual_disposable_income']}',
                                    '{rec['annual_expenses']}', '{rec['applicationdate']}', '{rec['bcc_approval_date']}', 
                                    '{rec['borrower_name']}', '{rec['branch_area']}', '{rec['branch_name']}', 
                                    '{rec['business_expense_description']}', '{rec['business_experiense_(since)']}',
                                    '{rec['business_premises']}', '{rec['cnic']}', '{rec['collage_univeristy']}', '{rec['collateral_type']}',
                                    '{rec['contact_no']}', '{rec['credit_history_ecib']}', '{rec['current_residencial']}', '{rec['dbr']}',
                                    '{rec['education_level']}', '{rec['enrollment_status']}', '{rec['enterprise_premises']}', '{rec['existing_loan_number']}',
                                    '{rec['existing_loan_limit']}', '{rec['existing_loan_status']}', '{rec['existing_outstanding_loan_schedules']}', 
                                    '{rec['experiense_start_date']}', '{rec['family_monthly_income']}', '{rec['father_husband_name']}',
                                    '{rec['gender']}', '{rec['kf_remarks']}', '{rec['loan_amount']}', '{rec['loan_cycle']}',
                                    '{rec['loanproductcode']}', '{rec['loan_status']}', '{rec['monthly_repayment_capacity']}', 
                                    '{rec['nature_of_business']}', '{rec['no_of_family_members']}', '{rec['permanent_residencial']}',
                                    '{rec['premises']}', '{rec['purpose_of_loan']}', '{rec['requested_loan_amount']}',
                                    '{rec['residance_type']}', '{rec['student_name']}', '{rec['student_co_borrower_gender']}',
                                    '{rec['student_relation_with_borrower']}', '{rec['tenor_of_month']}', '{rec['type_of_business']}',
                                    '{rec['annual_income']}', '1', '{str(get_current_user_id())}', '{str(datetime.now())}'
                                )
                            """
                        else:
                            query = f"""
                                INSERT INTO tbl_post_disbursement (
                                    mis_date, area, branch_code, branch_name, cnic, gender,
                                    address, mobile_no, loan_no, loan_title, product_code,
                                    booked_on, disbursed_amount, principal_outstanding,
                                    markup_outstanding, repayment_type, sector, purpose,
                                    loan_status, overdue_days, loan_closed_on, collateral_title
                                ) VALUES (
                                    '{rec['mis_date']}', '{rec['area']}', '{rec['branch_code']}', '{rec['branch_name']}',
                                    '{rec['cnic']}', '{rec['gender']}', '{rec['address']}', '{rec['mobile_no']}',
                                    '{rec['loan_no']}', '{rec['loan_title']}', '{rec['product_code']}',
                                    '{rec['booked_on']}', '{rec['disbursed_amount']}', '{rec['principal_outstanding']}',
                                    '{rec['markup_outstanding']}', '{rec['repayment_type']}', '{rec['sector']}', '{rec['purpose']}',
                                    '{rec['loan_status']}', '{rec['overdue_days']}', '{rec['loan_closed_on']}',
                                    '{rec['collateral_title']}'
                                )
                            """
                        execute_command(query, is_print=True)

        if any(len(duplicates[sheet]) > 0 for sheet in duplicates):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_filename = f"Summary_of_duplicates_discrepancies_{timestamp}.xlsx"
            summary_path = os.path.join(current_app.config['UPLOAD_FOLDER'], summary_filename)
            with pd.ExcelWriter(summary_path) as writer:
                for sheet_name, df in duplicates.items():
                    if len(df) > 0:
                        df.to_excel(writer, sheet_name=f"Duplicate_{sheet_name}", index=False)

        return True, {
            'duplicates': {k: len(v) for k, v in duplicates.items()},
            'new_records': {k: len(v) for k, v in new_records.items()},
            'summary_path': summary_path
        }

    except Exception as e:
        print(f"Error processing files: {str(e)}")
        return False, f"Error processing file: {str(e)}"

def parse_excel_date(date_str):
    print('called parse_excel_date')
    print('parse_excel_date:- ', date_str)
    if pd.isnull(date_str):
        return '1900-01-01'

    if not date_str:
        return '1900-01-01'

    if isinstance(date_str, datetime):
        return date_str.date()

    clean_date = str(date_str).strip().replace('\r', '').replace('\n', '')

    # Try known formats first
    for fmt in (
        "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d", "%Y-%m-%d",
        "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y"
    ):
        try:
            return datetime.strptime(clean_date, fmt).date()
        except ValueError:
            continue

    # Try ISO and other common formats using dateutil
    try:
        return parse(clean_date).date()
    except Exception:
        return None

@application.route('/download_summary')
def download_summary():
    try:
        if 'summary_file' not in session or not session['summary_file']:
            flash('No summary file available for download', 'danger')
            return redirect(url_for('manage_file'))

        file_path = session['summary_file']
        if not os.path.exists(file_path):
            flash('Summary file no longer exists', 'danger')
            return redirect(url_for('manage_file'))

        if not file_path.startswith(application.config['UPLOAD_FOLDER']):
            abort(403, description="Access denied")

        timestamp = datetime.now().strftime("%Y-%m-%d")
        download_name = f"Duplicate_Records_Summary_{timestamp}.xlsx"

        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(file_path):
                    safe_remove(file_path)
                    session.pop('report_file', None)
                    session.pop('summary_file', None)
                    print(f"Cleaned up summary file: {file_path}")
            except Exception as e:
                print(f"Error cleaning up summary file: {str(e)}")
            return response

        return send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            conditional=True
        )

    except Exception as e:
        application.logger.error(f"Failed to download summary: {str(e)}")
        try:
            if 'summary_file' in session and os.path.exists(session['summary_file']):
                safe_remove(session['summary_file'])
                session.pop('summary_file', None)
        except Exception as e:
            print(f"Error cleaning up summary file: {str(e)}")
        flash('Could not prepare the download. Please try again.', 'danger')
        return redirect(url_for('manage_file'))