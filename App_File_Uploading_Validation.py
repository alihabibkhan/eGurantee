from imports import *
from application import application
from application import allowed_file


@application.route('/manage-file', methods=['GET', 'POST'])
def manage_file():
    print("manage_file: Entering function")
    if request.method == 'POST':
        print("manage_file: Request method is POST")
        action_type = request.form.get('action_type')
        print(f"manage_file: action_type={action_type}")
        file_type = request.form.get('file_type') or session.get('file_type')
        print(f"manage_file: file_type={file_type}")

        if not file_type:
            print("manage_file: No file_type provided, flashing error")
            flash('Please select a file type.', 'danger')
            return redirect(url_for('manage_file'))

        if action_type == 'validate':
            print("manage_file: Action is validate, calling handle_validation")
            return handle_validation(file_type)
        elif action_type == 'upload':
            print("manage_file: Action is upload, calling handle_upload")
            return handle_upload()

    print("manage_file: Rendering upload.html with view='upload'")
    return render_template('upload.html', view='upload')


def handle_validation(file_type):
    print(f"handle_validation: Entering function with file_type={file_type}")
    if 'file' not in request.files:
        print("handle_validation: No file in request.files, flashing error")
        flash('No file selected.', 'danger')
        return redirect(url_for('manage_file'))

    files = request.files.getlist('file')
    print(f"handle_validation: Retrieved {len(files)} files from request")
    if not files or all(f.filename == '' for f in files):
        print("handle_validation: No valid files selected, flashing error")
        flash('No file selected.', 'danger')
        return redirect(url_for('manage_file'))

    category = request.form.get('category') if file_type == 'post_disbursement' else None
    print(f"handle_validation: category={category}")
    if file_type == 'post_disbursement' and not category:
        print("handle_validation: Post disbursement but no category, flashing error")
        flash('Please select a category for Post Disbursement.', 'danger')
        return redirect(url_for('manage_file'))

    if file_type == 'pre_disbursement' and len(files) > 1:
        print("handle_validation: Multiple files for pre_disbursement, flashing error")
        flash('Only one file allowed for Pre Disbursement.', 'danger')
        return redirect(url_for('manage_file'))
    elif file_type == 'post_disbursement':
        if category in ['los', 'mis'] and len(files) != 1:
            print(f"handle_validation: Invalid file count for {category}, flashing error")
            flash(f'Exactly one file is required for {category.upper()}.', 'danger')
            return redirect(url_for('manage_file'))
        elif category == 'both' and len(files) != 2:
            print("handle_validation: Invalid file count for 'both', flashing error")
            flash('Exactly two files are required for both LOS and MIS.', 'danger')
            return redirect(url_for('manage_file'))

    saved_files = []

    all_sheets = []
    all_counts = {}
    sheet_info_list = []

    has_pre = False
    has_post = False
    print("handle_validation: Initialized variables for file processing")

    for file_idx, file in enumerate(files):
        print(f"handle_validation: Processing file {file_idx + 1}, filename={file.filename}")
        if not allowed_file(file.filename):
            print(f"handle_validation: File {file.filename} not allowed, flashing error")
            flash(f'File {file.filename}: Only .xlsx files are allowed.', 'danger')
            return redirect(url_for('manage_file'))

        filename = secure_filename(file.filename)
        print(f"handle_validation: Secured filename={filename}")
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        print(f"handle_validation: Saving file to {filepath}")
        file.save(filepath)
        saved_files.append(filepath)
        print(f"handle_validation: Added {filepath} to saved_files")

        success, result = validate_excel(filepath, file_type, category, file_idx)
        print(f"handle_validation: validate_excel returned success={success}, result={result}")
        if not success:
            print("handle_validation: Validation failed, removing saved files")
            for saved_file in saved_files:
                try:
                    os.remove(saved_file)
                    print(f"handle_validation: Removed file {saved_file}")
                except Exception:
                    print(f"handle_validation: Failed to remove file {saved_file}")
            flash(result, 'warning')
            return redirect(url_for('manage_file'))

        all_sheets.extend(result['sheets_available'])
        print(f"handle_validation: Extended all_sheets with {result['sheets_available']}")
        all_counts.update(result['record_counts'])
        print(f"handle_validation: Updated all_counts with {result['record_counts']}")

        print('===========')
        print('all_sheets:- ', all_sheets)
        print('all_counts:- ', all_counts)
        print('===========')

        if result['sheet_info_list']:
            sheet_info_list.extend(result['sheet_info_list'])

        print('sheet_info_list:- ', sheet_info_list)
        print('===========')

        has_pre = has_pre or result['has_pre']
        print(f"handle_validation: has_pre={has_pre}")
        has_post = has_post or result['has_post']
        print(f"handle_validation: has_post={has_post}")

    session['current_files'] = saved_files
    print(f"handle_validation: Set session['current_files']={saved_files}")
    session['has_pre'] = has_pre
    print(f"handle_validation: Set session['has_pre']={has_pre}")
    session['has_post'] = has_post
    print(f"handle_validation: Set session['has_post']={has_post}")
    session['file_type'] = file_type
    print(f"handle_validation: Set session['file_type']={file_type}")
    session['category'] = category
    print(f"handle_validation: Set session['category']={category}")
    print(f"handle_validation: Rendering upload.html with view='validation_result', files={len(saved_files)}")
    return render_template('upload.html',
                           view='validation_result',
                           sheet_info_list=sheet_info_list,
                           filename=', '.join([os.path.basename(f) for f in saved_files]),
                           sheets=all_sheets,
                           counts=all_counts,
                           file_type=file_type,
                           category=category)


def validate_excel(filepath, file_type, category=None, file_idx=0):
    print(f"validate_excel: Entering function with filepath={filepath}, file_type={file_type}, category={category}, file_idx={file_idx}")
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
        print("validate_excel: Defined pre_headers")

        los_headers = [
            'sector_code', 'branch_code', 'branch_name', 'cnic', 'gender', 'address',
            'mobile_number', 'loan_title', 'rt', 'loan_number', 'product_code',
            'loancreationdate', 'disb_amt', 'loanrepaymenttype', 'sector', 'purpose',
            'loanstatus', 'closed_on_date', 'act_clo', 'colloanno', 'coll_id', 'lrno',
            'collat', 'coll_stat', 'collateral_value', 'collateraltitle', 'od_days',
            'os_p', 'total_outstand_other', 'total_outstand_markup', 'lo', 'fc_los',
            'dtf', 'dtt', 'customer_id', 'application_num'
        ]
        print("validate_excel: Defined los_headers")

        mis_headers = [
            'sector_code', 'bcode', 'branch_name', 'customer_id', 'gender', 'address',
            'mobile', 'loantitle', 'rt', 'loanno', 'product_code', 'loancreationdate',
            'disbursedamt', 'loanrepaymenttype', 'sector', 'purpose', 'loanstatus',
            'ln_clo_dt', 'act_clo', 'colloanno', 'coll_id', 'lrno', 'collateral_type',
            'coll_stat', 'collateral_value', 'collateraltitle', 'od_days',
            'total_outstand_principal', 'total_outstand_other', 'total_outstand_markup',
            'clo_on', 'liab_id', 'pool_id', 'account_number'
        ]
        print("validate_excel: Defined mis_headers")

        if file_type == 'pre_disbursement':
            expected_headers = pre_headers
            print("validate_excel: Set expected_headers to pre_headers")
        elif file_type == 'post_disbursement':
            if category == 'los':
                expected_headers = los_headers
                print("validate_excel: Set expected_headers to los_headers")
            elif category == 'mis':
                expected_headers = mis_headers
                print("validate_excel: Set expected_headers to mis_headers")
            elif category == 'both':
                expected_headers = los_headers if file_idx == 0 else mis_headers
                print(f"validate_excel: Set expected_headers to {'los_headers' if file_idx == 0 else 'mis_headers'} for 'both'")
            else:
                print("validate_excel: Invalid category, returning error")
                return False, "Invalid category selected."
        else:
            print(f"validate_excel: Invalid file_type={file_type}, returning error")
            return False, f"Invalid file type: {file_type}"

        xls = pd.ExcelFile(filepath)
        print(f"validate_excel: Loaded Excel file {filepath}")
        sheets = xls.sheet_names
        print(f"validate_excel: Found sheets: {sheets}")
        sheets = [o for o in sheets if o != 'GVMetadata']
        print(f"validate_excel: Filtered sheets (excluding GVMetadata): {sheets}")
        record_counts = {}
        sheet_info_list = []
        has_pre = file_type == 'pre_disbursement'
        has_post = file_type == 'post_disbursement'
        print(f"validate_excel: has_pre={has_pre}, has_post={has_post}")

        import uuid  # Move this to top of your Python file

        for sheet_name in sheets:
            print(f"validate_excel: Processing sheet '{sheet_name}'")

            df = pd.read_excel(
                xls,
                sheet_name=sheet_name,
                dtype={
                    'Branch Code': str,
                    'Application_No': str,
                    'loan_number': str,
                    'loanno': str
                }
            ).fillna('')

            print(f"validate_excel: Loaded DataFrame for sheet '{sheet_name}' with {len(df)} rows")

            if df.columns.duplicated().any():
                duplicates = df.columns[df.columns.duplicated()].tolist()
                print(f"validate_excel: Found duplicate columns in sheet '{sheet_name}': {duplicates}")
                return False, f"Duplicate column names found in sheet {sheet_name}: {duplicates}"

            missing_headers = [h for h in expected_headers if h not in df.columns]
            print(f"validate_excel: Missing headers in sheet '{sheet_name}': {missing_headers}")

            if missing_headers:
                print(f"validate_excel: Adding missing headers as blanks: {missing_headers}")
                for col in missing_headers:
                    df[col] = ''
                    print(f"validate_excel: Added column '{col}' with empty strings")

            unique_id = uuid.uuid4().hex
            row_count = len(df)

            record_counts[f"{sheet_name}_{unique_id}"] = row_count

            sheet_info_list.append({
                'sheet_name': sheet_name,
                'uuid': unique_id,
                'record_count': row_count
            })

            print(f"validate_excel: Recorded {row_count} rows for sheet '{sheet_name}' with UUID '{unique_id}'")

        print("validate_excel: Validation completed successfully")
        return True, {
            'sheets_available': sheets,
            'record_counts': record_counts,
            'sheet_info_list': sheet_info_list,
            'has_pre': has_pre,
            'has_post': has_post
        }
    except Exception as e:
        print(f"validate_excel: Error reading Excel file: {str(e)}")
        return False, f"Error reading Excel file: {str(e)}"


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def safe_remove(filepath):
    print(f"safe_remove: Attempting to remove file {filepath}")
    os.remove(filepath)
    print(f"safe_remove: File {filepath} deleted successfully.")


def handle_upload():
    print("handle_upload: Entering function")
    if 'current_files' not in session or not session['current_files']:
        print("handle_upload: No validated files in session, flashing error")
        flash('No validated files found. Please validate a file first.', 'danger')
        return redirect(url_for('manage_file'))

    file_type = session.get('file_type')
    print(f"handle_upload: file_type={file_type}")
    if not file_type:
        print("handle_upload: No file_type in session, flashing error")
        flash('File type not found in session. Please start over.', 'danger')
        return redirect(url_for('manage_file'))

    filepaths = session['current_files']
    has_pre = session.get('has_pre', False)
    has_post = session.get('has_post', False)
    category = session.get('category')
    print(f"handle_upload: file_type={file_type}, category={category}, files={len(filepaths)}, has_pre={has_pre}, has_post={has_post}")

    success, result = process_upload()
    print(f"handle_upload: process_upload returned success={success}, result={result}")

    if not success:
        print("handle_upload: Upload failed, flashing warning")
        flash(result, 'warning')
        return redirect(url_for('manage_file'))

    try:
        for filepath in filepaths:
            print(f"handle_upload: Attempting to remove file {filepath}")
            safe_remove(filepath)
            print(f"handle_upload: Successfully removed file {filepath}")
    except Exception as e:
        print(f"handle_upload: Failed to delete file: {str(e)}")

    session.pop('current_files', None)
    print("handle_upload: Cleared session['current_files']")
    session.pop('has_pre', None)
    print("handle_upload: Cleared session['has_pre']")
    session.pop('has_post', None)
    print("handle_upload: Cleared session['has_post']")
    session.pop('file_type', None)
    print("handle_upload: Cleared session['file_type']")
    session.pop('category', None)
    print("handle_upload: Cleared session['category']")

    if result['summary_path']:
        session['summary_file'] = result['summary_path']
        print(f"handle_upload: Set session['summary_file']={result['summary_path']}")

    print("handle_upload: Rendering upload.html with view='upload_result'")
    return render_template('upload.html',
                           view='upload_result',
                           duplicates=result['duplicates'],
                           new_records=result['new_records'],
                           has_summary=result['summary_path'] is not None)


def process_upload():
    print("process_upload: Entering function")
    file_type = session.get('file_type')
    category = session.get('category')
    filepaths = session['current_files']
    print(f"process_upload: file_type={file_type}, category={category}, files={len(filepaths)}")
    duplicates = {}
    new_records = {}
    summary_path = None
    print("process_upload: Initialized duplicates, new_records, summary_path")

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
    print("process_upload: Defined pre_headers")

    post_headers = [
        'mis_date', 'area', 'sector_code', 'branch_code', 'branch_name', 'cnic', 'gender',
        'address', 'mobile_no', 'loan_title', 'rt', 'loan_no', 'product_code', 'booked_on',
        'disbursed_amount', 'repayment_type', 'sector', 'purpose', 'loan_status', 'loan_closed_on',
        'act_clo', 'colloanno', 'coll_id', 'lrno', 'collat', 'coll_stat', 'collateral_value',
        'collateral_title', 'overdue_days', 'principal_outstanding', 'total_outstand_other',
        'markup_outstanding', 'lo', 'fc_los', 'dtf', 'dtt', 'customer_id', 'application_num',
        'clo_on', 'liab_id', 'pool_id', 'account_number'
    ]
    print("process_upload: Defined post_headers")

    post_to_los_mapping = {
        'branch_code': 'branch_code',
        'branch_name': 'branch_name',
        'cnic': 'cnic',
        'gender': 'gender',
        'address': 'address',
        'mobile_no': 'mobile_number',
        'loan_no': 'loan_number',
        'loan_title': 'loan_title',
        'product_code': 'product_code',
        'booked_on': 'loancreationdate',
        'disbursed_amount': 'disb_amt',
        'principal_outstanding': 'os_p',
        'markup_outstanding': 'total_outstand_markup',
        'repayment_type': 'loanrepaymenttype',
        'sector': 'sector',
        'purpose': 'purpose',
        'loan_status': 'loanstatus',
        'overdue_days': 'od_days',
        'loan_closed_on': 'closed_on_date',
        'collateral_title': 'collateraltitle',
    }
    print("process_upload: Defined post_to_los_mapping")

    post_to_mis_mapping = {
        'branch_code': 'bcode',
        'branch_name': 'branch_name',
        'cnic': 'customer_id',
        'gender': 'gender',
        'address': 'address',
        'mobile_no': 'mobile',
        'loan_no': 'loanno',
        'loan_title': 'loantitle',
        'product_code': 'product_code',
        'booked_on': 'loancreationdate',
        'disbursed_amount': 'disbursedamt',
        'principal_outstanding': 'total_outstand_principal',
        'markup_outstanding': 'total_outstand_markup',
        'repayment_type': 'loanrepaymenttype',
        'sector': 'sector',
        'purpose': 'purpose',
        'loan_status': 'loanstatus',
        'overdue_days': 'od_days',
        'loan_closed_on': 'ln_clo_dt',
        'collateral_title': 'collateraltitle',
    }
    print("process_upload: Defined post_to_mis_mapping")

    los_to_mis_mapping = {
        'collat': 'collateral_type'
    }
    print("process_upload: Defined los_to_mis_mapping")

    try:
        all_dfs = []
        print("process_upload: Initialized all_dfs")
        for file_idx, filepath in enumerate(filepaths):
            print(f"process_upload: Processing file {file_idx + 1}: {filepath}")
            xl = pd.ExcelFile(filepath)
            print(f"process_upload: Loaded Excel file {filepath}")
            sheet_names = xl.sheet_names
            print(f"process_upload: Found sheets: {sheet_names}")
            sheet_names = [o for o in sheet_names if o != 'GVMetadata']
            print(f"process_upload: Filtered sheets (excluding GVMetadata): {sheet_names}")

            for sheet_name in sheet_names:
                print(f"process_upload: Processing sheet '{sheet_name}'")
                df = pd.read_excel(filepath, sheet_name=sheet_name,
                                   dtype=str).fillna('')
                print(f"process_upload: Loaded DataFrame for sheet '{sheet_name}' with {len(df)} rows")
                df.columns = [col.strip().lower().replace('/', '_').replace(' ', '_') for col in df.columns]
                print(f"process_upload: Normalized column names: {list(df.columns)}")

                if df.columns.duplicated().any():
                    print(f"process_upload: Found duplicate columns in sheet '{sheet_name}': {df.columns[df.columns.duplicated()].tolist()}")
                    raise ValueError(
                        f"Duplicate column names found in sheet {sheet_name}: {df.columns[df.columns.duplicated()].tolist()}")

                if file_type == 'pre_disbursement':
                    expected_headers = pre_headers
                    table_name = 'tbl_pre_disbursement_temp'
                    key_column = 'application_no'
                    print(f"process_upload: Set pre_disbursement settings: table_name={table_name}, key_column={key_column}")
                    existing_records = fetch_records('SELECT "Application_No", "status" FROM tbl_pre_disbursement_temp')
                    print(f"process_upload: Fetched {len(existing_records)} existing records for pre_disbursement")
                    existing_app_nos = {str(row['Application_No']): str(row['status']) for row in existing_records}
                    print(f"process_upload: Created existing_app_nos with {len(existing_app_nos)} entries")
                else:
                    expected_headers = post_headers
                    table_name = 'tbl_post_disbursement'
                    key_column = 'loan_no'
                    print(f"process_upload: Set post_disbursement settings: table_name={table_name}, key_column={key_column}")
                    existing_records = fetch_records(f'SELECT "{key_column}" FROM {table_name}')
                    print(f"process_upload: Fetched {len(existing_records)} existing records for post_disbursement")
                    existing_app_nos = {str(row[key_column]): None for row in existing_records}
                    print(f"process_upload: Created existing_app_nos with {len(existing_app_nos)} entries")

                    # Apply column mapping based on category and file index
                    if category == 'los' or (category == 'both' and file_idx == 0):
                        mapping = post_to_los_mapping
                        inverse_mapping = {v: k for k, v in mapping.items()}
                        df = df.rename(columns=inverse_mapping)
                        print(f"process_upload: Applied post_to_los_mapping, new columns: {list(df.columns)}")
                        if category == 'both':
                            df = df.rename(columns=los_to_mis_mapping)
                            print(f"process_upload: Applied los_to_mis_mapping for 'both', new columns: {list(df.columns)}")
                    elif category == 'mis' or (category == 'both' and file_idx == 1):
                        mapping = post_to_mis_mapping
                        inverse_mapping = {v: k for k, v in mapping.items()}
                        df = df.rename(columns=inverse_mapping)
                        print(f"process_upload: Applied post_to_mis_mapping, new columns: {list(df.columns)}")
                    else:
                        print(f"process_upload: Invalid category={category}, raising error")
                        raise ValueError(f"Invalid category: {category}")

                missing_headers = [h for h in expected_headers if h not in df.columns]
                print(f"process_upload: Missing headers in sheet '{sheet_name}': {missing_headers}")
                if missing_headers:
                    print(f"process_upload: Adding missing headers as blanks: {missing_headers}")
                    flash(f"Sheet '{sheet_name}' is missing headers: {', '.join(missing_headers)}. Adding as blanks.",
                          'warning')
                    for col in missing_headers:
                        df[col] = ''
                        print(f"process_upload: Added column '{col}' with empty strings")

                # Validate key_column exists in DataFrame
                if key_column not in df.columns:
                    print(f"process_upload: Key column '{key_column}' not found in sheet '{sheet_name}', columns={list(df.columns)}")
                    raise ValueError(f"Key column '{key_column}' not found in sheet {sheet_name} after mapping. Available columns: {list(df.columns)}")

                print(f"process_upload: Processing sheet '{sheet_name}' with key_column={key_column}, columns={list(df.columns)}")
                duplicates[sheet_name] = []
                new_records[sheet_name] = []
                print(f"process_upload: Initialized duplicates and new_records for sheet '{sheet_name}'")

                for _, row in df.iterrows():
                    key = str(row[key_column])
                    print(f"process_upload: Checking row with {key_column}={key}")
                    if key in existing_app_nos and (file_type != 'pre_disbursement' or existing_app_nos[key] != '3'):
                        duplicates[sheet_name].append(row)
                        print(f"process_upload: Added row to duplicates for sheet '{sheet_name}'")
                    else:
                        new_records[sheet_name].append(row)
                        print(f"process_upload: Added row to new_records for sheet '{sheet_name}'")

                duplicates[sheet_name] = pd.DataFrame(duplicates[sheet_name], columns=df.columns)
                print(f"process_upload: Converted duplicates for sheet '{sheet_name}' to DataFrame with {len(duplicates[sheet_name])} rows")
                new_records[sheet_name] = pd.DataFrame(new_records[sheet_name], columns=df.columns)
                print(f"process_upload: Converted new_records for sheet '{sheet_name}' to DataFrame with {len(new_records[sheet_name])} rows")
                all_dfs.append(new_records[sheet_name])
                print(f"process_upload: Appended new_records for sheet '{sheet_name}' to all_dfs")

        # Merge datasets for 'both'
        if file_type == 'post_disbursement' and category == 'both':
            print("process_upload: Merging datasets for category='both'")
            if all_dfs:
                combined_df = pd.concat(all_dfs, ignore_index=True)
                print(f"process_upload: Combined {len(all_dfs)} DataFrames into combined_df with {len(combined_df)} rows")
                new_records = {f'combined_{category}': combined_df}
                print(f"process_upload: Set new_records to combined DataFrame for 'both'")
                duplicates = {f'combined_{category}': pd.concat([duplicates[s] for s in duplicates if len(duplicates[s]) > 0], ignore_index=True)}
                print(f"process_upload: Set duplicates to combined DataFrame for 'both' with {len(duplicates[f'combined_{category}'])} rows")
        else:
            new_records = {k: v for k, v in new_records.items() if len(v) > 0}
            print(f"process_upload: Filtered new_records: {list(new_records.keys())}")
            duplicates = {k: v for k, v in duplicates.items() if len(v) > 0}
            print(f"process_upload: Filtered duplicates: {list(duplicates.keys())}")

        if len(new_records) > 0:
            print(f"process_upload: Processing {len(new_records)} new_records for insertion")
            date_columns = ['applicationdate', 'bcc_approval_date', 'business_experiense_(since)',
                            'experiense_start_date'] if file_type == 'pre_disbursement' else ['mis_date',
                                                                                              'booked_on',
                                                                                              'loan_closed_on', 'clo_on', 'dtf', 'dtt']
            print(f"process_upload: Defined date_columns: {date_columns}")

            for df_key in new_records:
                print(f"process_upload: Processing DataFrame '{df_key}'")
                df = new_records[df_key]
                for col in date_columns:
                    if col in df.columns:
                        print(f"process_upload: Applying parse_excel_date to column '{col}'")
                        df[col] = df[col].apply(parse_excel_date)
                        print(f"process_upload: Parsed dates for column '{col}'")

                # for rec in df.to_dict('records'):
                #     print(f"process_upload: Processing record in DataFrame '{df_key}'")
                #     if file_type == 'pre_disbursement' and str(rec['application_no']) not in ['', 'NaN', 'None']:
                #         query = f"""
                #             INSERT INTO tbl_pre_disbursement_temp (
                #                 "Application_No", "Annual_Business_Incomes", "Annual_Disposable_Income",
                #                 "Annual_Expenses", "ApplicationDate", "Bcc_Approval_Date", "Borrower_Name",
                #                 "Branch_Area", "Branch_Name", "Business_Expense_Description",
                #                 "Business_Experiense_Since", "Business_Premises", "CNIC", "Collage_Univeristy",
                #                 "Collateral_Type", "Contact_No", "Credit_History_Ecib", "Current_Residencial",
                #                 "Dbr", "Education_Level", "Enrollment_Status", "Enterprise_Premises",
                #                 "Existing_Loan_Number", "Existing_Loan_Limit", "Existing_Loan_Status",
                #                 "Existing_Outstanding_Loan_Schedules", "Experiense_Start_Date",
                #                 "Family_Monthly_Income", "Father_Husband_Name", "Gender", "KF_Remarks",
                #                 "Loan_Amount", "Loan_Cycle", "LoanProductCode", "Loan_Status",
                #                 "Monthly_Repayment_Capacity", "Nature_Of_Business", "No_Of_Family_Members",
                #                 "Permanent_Residencial", "Premises", "Purpose_Of_Loan", "Requested_Loan_Amount",
                #                 "Residance_Type", "Student_Name", "Student_Co_Borrower_Gender",
                #                 "Student_Relation_With_Borrower", "Tenor_Of_Month", "Type_of_Business",
                #                 "annual_income", "status", "uploaded_by", "uploaded_date"
                #             ) VALUES (
                #                 '{rec['application_no']}', '{rec['annual_business_incomes']}', '{rec['annual_disposable_income']}',
                #                 '{rec['annual_expenses']}', '{rec['applicationdate']}', '{rec['bcc_approval_date']}',
                #                 '{rec['borrower_name']}', '{rec['branch_area']}', '{rec['branch_name']}',
                #                 '{rec['business_expense_description']}', '{rec['business_experiense_(since)']}',
                #                 '{rec['business_premises']}', '{rec['cnic']}', '{rec['collage_univeristy']}', '{rec['collateral_type']}',
                #                 '{rec['contact_no']}', '{rec['credit_history_ecib']}', '{rec['current_residencial']}', '{rec['dbr']}',
                #                 '{rec['education_level']}', '{rec['enrollment_status']}', '{rec['enterprise_premises']}', '{rec['existing_loan_number']}',
                #                 '{rec['existing_loan_limit']}', '{rec['existing_loan_status']}', '{rec['existing_outstanding_loan_schedules']}',
                #                 '{rec['experiense_start_date']}', '{rec['family_monthly_income']}', '{rec['father_husband_name']}',
                #                 '{rec['gender']}', '{rec['kf_remarks']}', '{rec['loan_amount']}', '{rec['loan_cycle']}',
                #                 '{rec['loanproductcode']}', '{rec['loan_status']}', '{rec['monthly_repayment_capacity']}',
                #                 '{rec['nature_of_business']}', '{rec['no_of_family_members']}', '{rec['permanent_residencial']}',
                #                 '{rec['premises']}', '{rec['purpose_of_loan']}', '{rec['requested_loan_amount']}',
                #                 '{rec['residance_type']}', '{rec['student_name']}', '{rec['student_co_borrower_gender']}',
                #                 '{rec['student_relation_with_borrower']}', '{rec['tenor_of_month']}', '{rec['type_of_business']}',
                #                 '{rec['annual_income']}', '1', '{str(get_current_user_id())}', '{str(datetime.now())}'
                #             )
                #         """
                #         print(f"process_upload: Executing INSERT query for pre_disbursement, application_no={rec['application_no']}")
                #         execute_command(query, is_print=False)
                #     else:
                #         if rec['loan_no'].replace("'", '') not in ['', 'NaN', 'None']:
                #             query = f"""
                #                         INSERT INTO tbl_post_disbursement (
                #                             mis_date, area, sector_code, branch_code, branch_name, cnic, gender,
                #                             address, mobile_no, loan_title, rt, loan_no, product_code, booked_on,
                #                             disbursed_amount, repayment_type, sector, purpose, loan_status, loan_closed_on,
                #                             act_clo, colloanno, coll_id, lrno, collat, coll_stat, collateral_value,
                #                             collateral_title, overdue_days, principal_outstanding, total_outstand_other,
                #                             markup_outstanding, lo, fc_los, dtf, dtt, customer_id, application_num,
                #                             clo_on, liab_id, pool_id, account_number, created_by, created_date
                #                         ) VALUES (
                #                             '{rec.get('mis_date', '1900-01-01')}', '{rec.get('area', '')}', '{rec.get('sector_code', '')}',
                #                             '{rec.get('branch_code', '')}', '{rec.get('branch_name', '')}', '{rec.get('cnic', '')}',
                #                             '{rec.get('gender', '')}', '{rec.get('address', '')}', '{rec.get('mobile_no', '')}',
                #                             '{rec.get('loan_title', '')}', '{rec.get('rt', '')}', '{rec.get('loan_no', '')}',
                #                             '{rec.get('product_code', '')}', '{rec.get('booked_on', '1900-01-01')}',
                #                             '{rec.get('disbursed_amount', '')}', '{rec.get('repayment_type', '')}',
                #                             '{rec.get('sector', '')}', '{rec.get('purpose', '')}', '{rec.get('loan_status', '')}',
                #                             '{rec.get('loan_closed_on', '1900-01-01')}', '{rec.get('act_clo', '')}',
                #                             '{rec.get('colloanno', '')}', '{rec.get('coll_id', '')}', '{rec.get('lrno', '')}',
                #                             '{rec.get('collat', '')}', '{rec.get('coll_stat', '')}', '{rec.get('collateral_value', '')}',
                #                             '{rec.get('collateral_title', '')}', '{rec.get('overdue_days', '')}',
                #                             '{rec.get('principal_outstanding', '')}', '{rec.get('total_outstand_other', '')}',
                #                             '{rec.get('markup_outstanding', '')}', '{rec.get('lo', '')}', '{rec.get('fc_los', '')}',
                #                             '{rec.get('dtf', '')}', '{rec.get('dtt', '')}', '{rec.get('customer_id', '')}',
                #                             '{rec.get('application_num', '')}', '{rec.get('clo_on', '1900-01-01')}',
                #                             '{rec.get('liab_id', '')}', '{rec.get('pool_id', '')}', '{rec.get('account_number', '')}',
                #                             '{str(get_current_user_id())}', '{str(datetime.now())}'
                #                         )
                #                     """
                #             print(
                #                 f"process_upload: Executing INSERT query for {'pre_disbursement' if file_type == 'pre_disbursement' else 'post_disbursement'}, {'application_no' if file_type == 'pre_disbursement' else 'loan_no'}={rec.get('application_no' if file_type == 'pre_disbursement' else 'loan_no', '')}")
                #             execute_command(query, is_print=False)
                #             print("process_upload: Executed INSERT query")
                pre_disbursement_queries = []
                post_disbursement_queries = []
                for rec in df.to_dict('records'):
                    print(f"process_upload: Processing record in DataFrame '{df_key}'")
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
                                    '{rec.get('application_no', '')}', '{rec.get('annual_business_incomes', '')}', '{rec.get('annual_disposable_income', '')}',
                                    '{rec.get('annual_expenses', '')}', '{rec.get('applicationdate', '')}', '{rec.get('bcc_approval_date', '')}', 
                                    '{rec.get('borrower_name', '')}', '{rec.get('branch_area', '')}', '{rec.get('branch_name', '')}', 
                                    '{rec.get('business_expense_description', '')}', '{rec.get('business_experiense_(since)', '')}',
                                    '{rec.get('business_premises', '')}', '{rec.get('cnic', '')}', '{rec.get('collage_univeristy', '')}', 
                                    '{rec.get('collateral_type', '')}', '{rec.get('contact_no', '')}', '{rec.get('credit_history_ecib', '')}', 
                                    '{rec.get('current_residencial', '')}', '{rec.get('dbr', '')}', '{rec.get('education_level', '')}', 
                                    '{rec.get('enrollment_status', '')}', '{rec.get('enterprise_premises', '')}', '{rec.get('existing_loan_number', '')}',
                                    '{rec.get('existing_loan_limit', '')}', '{rec.get('existing_loan_status', '')}', 
                                    '{rec.get('existing_outstanding_loan_schedules', '')}', '{rec.get('experiense_start_date', '')}', 
                                    '{rec.get('family_monthly_income', '')}', '{rec.get('father_husband_name', '')}', '{rec.get('gender', '')}', 
                                    '{rec.get('kf_remarks', '')}', '{rec.get('loan_amount', '')}', '{rec.get('loan_cycle', '')}',
                                    '{rec.get('loanproductcode', '')}', '{rec.get('loan_status', '')}', '{rec.get('monthly_repayment_capacity', '')}', 
                                    '{rec.get('nature_of_business', '')}', '{rec.get('no_of_family_members', '')}', '{rec.get('permanent_residencial', '')}',
                                    '{rec.get('premises', '')}', '{rec.get('purpose_of_loan', '')}', '{rec.get('requested_loan_amount', '')}',
                                    '{rec.get('residance_type', '')}', '{rec.get('student_name', '')}', '{rec.get('student_co_borrower_gender', '')}',
                                    '{rec.get('student_relation_with_borrower', '')}', '{rec.get('tenor_of_month', '')}', '{rec.get('type_of_business', '')}',
                                    '{rec.get('annual_income', '')}', '1', '{str(get_current_user_id())}', '{str(datetime.now())}'
                                )
                            """
                        pre_disbursement_queries.append(query)
                        print(
                            f"process_upload: Preparing INSERT query for pre_disbursement, application_no={rec.get('application_no', '')}")
                    else:
                        loan_no = rec.get('loan_no', '').replace("'", '')
                        if loan_no not in ['', 'NaN', 'None']:
                            query = f"""
                                    INSERT INTO tbl_post_disbursement (
                                        mis_date, area, sector_code, branch_code, branch_name, cnic, gender,
                                        address, mobile_no, loan_title, rt, loan_no, product_code, booked_on,
                                        disbursed_amount, repayment_type, sector, purpose, loan_status, loan_closed_on,
                                        act_clo, colloanno, coll_id, lrno, collat, coll_stat, collateral_value,
                                        collateral_title, overdue_days, principal_outstanding, total_outstand_other,
                                        markup_outstanding, lo, fc_los, dtf, dtt, customer_id, application_num,
                                        clo_on, liab_id, pool_id, account_number, created_by, created_date
                                    ) VALUES (
                                        '{rec.get('mis_date', '1900-01-01')}', '{rec.get('area', '')}', '{rec.get('sector_code', '')}',
                                        '{rec.get('branch_code', '')}', '{rec.get('branch_name', '')}', '{rec.get('cnic', '')}',
                                        '{rec.get('gender', '')}', '{rec.get('address', '')}', '{rec.get('mobile_no', '')}',
                                        '{rec.get('loan_title', '')}', '{rec.get('rt', '')}', '{loan_no}',
                                        '{rec.get('product_code', '')}', '{rec.get('booked_on', '1900-01-01')}',
                                        '{rec.get('disbursed_amount', '')}', '{rec.get('repayment_type', '')}',
                                        '{rec.get('sector', '')}', '{rec.get('purpose', '')}', '{rec.get('loan_status', '')}',
                                        '{rec.get('loan_closed_on', '1900-01-01')}', '{rec.get('act_clo', '')}',
                                        '{rec.get('colloanno', '')}', '{rec.get('coll_id', '')}', '{rec.get('lrno', '')}',
                                        '{rec.get('collat', '')}', '{rec.get('coll_stat', '')}', '{rec.get('collateral_value', '')}',
                                        '{rec.get('collateral_title', '')}', '{rec.get('overdue_days', '')}',
                                        '{rec.get('principal_outstanding', '')}', '{rec.get('total_outstand_other', '')}',
                                        '{rec.get('markup_outstanding', '')}', '{rec.get('lo', '')}', '{rec.get('fc_los', '')}',
                                        '{rec.get('dtf', '')}', '{rec.get('dtt', '')}', '{rec.get('customer_id', '')}',
                                        '{rec.get('application_num', '')}', '{rec.get('clo_on', '1900-01-01')}',
                                        '{rec.get('liab_id', '')}', '{rec.get('pool_id', '')}', '{rec.get('account_number', '')}',
                                        '{str(get_current_user_id())}', '{str(datetime.now())}'
                                    )
                                """
                            post_disbursement_queries.append(query)
                            print(
                                f"process_upload: Preparing INSERT query for {'pre_disbursement' if file_type == 'pre_disbursement' else 'post_disbursement'}, "
                                f"{'application_no' if file_type == 'pre_disbursement' else 'loan_no'}={rec.get('application_no' if file_type == 'pre_disbursement' else 'loan_no', '')}"
                            )

                    # Execute pre_disbursement batch
                if pre_disbursement_queries:
                    batch_query = ";".join(pre_disbursement_queries)
                    print(
                        f"process_upload: Executing batch INSERT query for {len(pre_disbursement_queries)} pre_disbursement records")
                    execute_command(batch_query, is_print=False)
                    print("process_upload: Executed batch INSERT query for pre_disbursement")

                    # Execute post_disbursement batch
                if post_disbursement_queries:
                    batch_query = ";".join(post_disbursement_queries)
                    print(
                        f"process_upload: Executing batch INSERT query for {len(post_disbursement_queries)} post_disbursement records")
                    execute_command(batch_query, is_print=False)

                    # with open('post_disbursement_queries.sql', 'w') as f:
                    #     f.write(batch_query)

                    print("process_upload: Executed batch INSERT query for post_disbursement")

                if not pre_disbursement_queries and not post_disbursement_queries:
                    print("process_upload: No valid records to insert")

        if any(len(duplicates[sheet]) > 0 for sheet in duplicates):
            print("process_upload: Found duplicates, generating summary file")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            print(f"process_upload: Generated timestamp={timestamp}")
            summary_filename = f"Summary_of_duplicates_discrepancies_{timestamp}.xlsx"
            summary_path = os.path.join(current_app.config['UPLOAD_FOLDER'], summary_filename)
            print(f"process_upload: Set summary_path={summary_path}")
            with pd.ExcelWriter(summary_path) as writer:
                print("process_upload: Opened ExcelWriter for summary file")
                for sheet_name, df in duplicates.items():
                    if len(df) > 0:
                        print(f"process_upload: Writing duplicates for sheet '{sheet_name}' with {len(df)} rows")
                        df.to_excel(writer, sheet_name=f"Duplicate_{sheet_name}", index=False)
                        print(f"process_upload: Wrote duplicates for sheet '{sheet_name}'")

        print("process_upload: Upload processing completed")
        return True, {
            'duplicates': {k: len(v) for k, v in duplicates.items()},
            'new_records': {k: len(v) for k, v in new_records.items()},
            'summary_path': summary_path
        }
    except Exception as e:
        print(f"process_upload: Error processing files: {str(e)}")
        return False, f"Error processing file: {str(e)}"


def parse_excel_date(date_str):
    print(f"parse_excel_date: Entering function with date_str={date_str}")
    if pd.isnull(date_str):
        print("parse_excel_date: Date is null, returning '1900-01-01'")
        return '1900-01-01'

    if not date_str:
        print("parse_excel_date: Date is empty, returning '1900-01-01'")
        return '1900-01-01'

    if isinstance(date_str, datetime):
        print("parse_excel_date: Date is datetime, returning date part")
        return date_str.date()

    clean_date = str(date_str).strip().replace('\r', '').replace('\n', '')
    print(f"parse_excel_date: Cleaned date string: {clean_date}")

    # Try known formats first
    for fmt in (
        "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d", "%Y-%m-%d",
        "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y"
    ):
        try:
            result = datetime.strptime(clean_date, fmt).date()
            print(f"parse_excel_date: Parsed date with format {fmt}: {result}")
            return result
        except ValueError:
            print(f"parse_excel_date: Failed to parse with format {fmt}")
            continue

    # Try ISO and other common formats using dateutil
    try:
        result = parse(clean_date).date()
        print(f"parse_excel_date: Parsed date with dateutil: {result}")
        return result
    except Exception:
        print("parse_excel_date: Failed to parse with dateutil, returning None")
        return None


@application.route('/download_summary')
def download_summary():
    print("download_summary: Entering function")
    try:
        if 'summary_file' not in session or not session['summary_file']:
            print("download_summary: No summary file in session, flashing error")
            flash('No summary file available for download', 'danger')
            return redirect(url_for('manage_file'))

        file_path = session['summary_file']
        print(f"download_summary: Retrieved summary_file={file_path}")
        if not os.path.exists(file_path):
            print("download_summary: Summary file does not exist, flashing error")
            flash('Summary file no longer exists', 'danger')
            return redirect(url_for('manage_file'))

        if not file_path.startswith(application.config['UPLOAD_FOLDER']):
            print("download_summary: File path not in UPLOAD_FOLDER, aborting")
            abort(403, description="Access denied")

        timestamp = datetime.now().strftime("%Y-%m-%d")
        print(f"download_summary: Generated timestamp={timestamp}")
        download_name = f"Duplicate_Records_Summary_{timestamp}.xlsx"
        print(f"download_summary: Set download_name={download_name}")

        @after_this_request
        def cleanup(response):
            print("download_summary: Entering cleanup function")
            try:
                if os.path.exists(file_path):
                    print(f"download_summary: Attempting to remove file {file_path}")
                    safe_remove(file_path)
                    print(f"download_summary: Removed file {file_path}")
                    session.pop('report_file', None)
                    print("download_summary: Cleared session['report_file']")
                    session.pop('summary_file', None)
                    print("download_summary: Cleared session['summary_file']")
            except Exception as e:
                print(f"download_summary: Error cleaning up summary file: {str(e)}")
            return response

        print(f"download_summary: Sending file {file_path} as {download_name}")
        return send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            conditional=True
        )

    except Exception as e:
        print(f"download_summary: Error downloading summary: {str(e)}")
        application.logger.error(f"Failed to download summary: {str(e)}")
        try:
            if 'summary_file' in session and os.path.exists(session['summary_file']):
                print(f"download_summary: Attempting to clean up summary file {session['summary_file']}")
                safe_remove(session['summary_file'])
                print("download_summary: Removed summary file")
                session.pop('summary_file', None)
                print("download_summary: Cleared session['summary_file']")
        except Exception as e:
            print(f"download_summary: Error cleaning up summary file: {str(e)}")
        print("download_summary: Flashing download error")
        flash('Could not prepare the download. Please try again.', 'danger')
        return redirect(url_for('manage_file'))