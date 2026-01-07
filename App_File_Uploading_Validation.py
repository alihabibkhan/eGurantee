from imports import *
from application import application
from application import allowed_file
import uuid


@application.route('/manage-file', methods=['GET', 'POST'])
def manage_file():
    if not (is_login() and (is_admin() or is_executive_approver())):
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))

    view = 'upload'
    zip_results = None

    if request.method == 'POST':
        action_type = request.form.get('action_type')
        file_type = request.form.get('file_type')

        if action_type == 'validate':
            # Your existing validation logic (unchanged)
            # Example placeholder – replace with your actual implementation
            return handle_validation(file_type, request.form.get('input_timestamp'))

        elif action_type == 'upload':
            # Your existing Excel upload logic (unchanged)
            # Example placeholder
            return handle_upload()

        elif action_type == 'process_zip':
            if 'file' not in request.files or not request.files['file'].filename:
                flash("No ZIP file selected.", "danger")
                return redirect(url_for('manage_file'))

            file = request.files['file']
            if not file.filename.lower().endswith('.zip'):
                flash("Please upload a valid .zip file.", "danger")
                return redirect(url_for('manage_file'))

            try:
                zip_results = process_zip_application_images(file)
                view = 'zip_result'
            except Exception as e:
                application.logger.error(f"ZIP image processing failed: {str(e)}")
                flash(f"Error processing ZIP file: {str(e)}", "danger")
                return redirect(url_for('manage_file'))

    return render_template(
        'upload.html',
        view=view,
        zip_results=zip_results,
        # Include any other variables your template needs (filename, category, etc.)
    )


def process_zip_application_images(zip_file):
    """
    Process uploaded ZIP file containing application images:
    - Extracts images from supported formats
    - Parses application number from folder name
    - Parses CNIC and customer name from filename
    - Skips duplicates by comparing MD5 hashes (bulk pre-load + in-memory check)
    - Inserts new images in a single batch operation
    - Returns processing summary
    """
    results = {
        'processed': 0,
        'skipped': 0,
        'applications': []
    }

    application.logger.debug("process_zip_application_images: Starting ZIP processing")

    # Step 1: First pass - collect all application numbers from ZIP
    zip_content = BytesIO(zip_file.read())
    application_numbers = set()

    application.logger.debug(f"ZIP file size: {len(zip_content.getvalue())} bytes")

    with ZipFile(zip_content) as zf:
        for file_name in zf.namelist():
            if not file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.jfif')):
                continue

            folder_path = os.path.dirname(file_name)
            folder_name = os.path.basename(folder_path) if folder_path else ""

            match = re.search(r'(?:loan|app|application)[_-]?(\d+)', folder_name, re.IGNORECASE)
            if match:
                app_no = match.group(1)
                application_numbers.add(app_no)
                application.logger.debug(f"Found application: {app_no} from folder '{folder_name}'")

    application.logger.info(f"Extracted {len(application_numbers)} unique application numbers")

    if not application_numbers:
        application.logger.warning("No valid application folders found in ZIP")
        return results

    # Step 2: Pre-load existing image hashes from database (single query)
    app_list_str = ",".join("'" + no.replace("'", "''") + "'" for no in application_numbers)

    preload_query = f"""
    SELECT 
        application_no,
        md5(image_data) AS image_hash
    FROM tbl_pre_disbursement_application_images
    WHERE application_no IN ({app_list_str})
    """

    application.logger.debug(f"Executing preload query for {len(application_numbers)} applications")
    rows = fetch_records(preload_query) or []

    existing_images = {}  # application_no → set of md5 hex strings
    for row in rows:
        app_no = row['application_no']
        hash_val = row['image_hash']
        if app_no not in existing_images:
            existing_images[app_no] = set()
        existing_images[app_no].add(hash_val)

    total_existing = sum(len(hashes) for hashes in existing_images.values())
    application.logger.info(f"Loaded {total_existing} existing image hashes for {len(existing_images)} applications")

    # Step 3: Second pass - process images and prepare inserts
    insert_rows = []
    app_image_counts = {}
    app_metadata = {}

    zip_content.seek(0)  # Reset to beginning for second read
    application.logger.debug("Starting second pass over ZIP file")

    with ZipFile(zip_content) as zf:
        for file_name in zf.namelist():
            if not file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                continue

            folder_path = os.path.dirname(file_name)
            folder_name = os.path.basename(folder_path) if folder_path else ""

            match = re.search(r'(?:loan|app|application)[_-]?(\d+)', folder_name, re.IGNORECASE)
            if not match:
                continue

            application_no = match.group(1)

            with zf.open(file_name) as img_file:
                image_bytes = img_file.read()

            image_hash = md5(image_bytes).hexdigest()
            image_size = len(image_bytes)

            # Check for duplicate using pre-loaded hashes
            is_duplicate = (
                application_no in existing_images
                and image_hash in existing_images[application_no]
            )

            if is_duplicate:
                results['skipped'] += 1
                application.logger.debug(
                    f"Skipped duplicate - App: {application_no} | "
                    f"Hash: {image_hash[:12]}... | Size: {image_size} bytes"
                )
                continue

            # Parse filename (expected: number-cnic-name.ext)
            original_filename = os.path.basename(file_name)
            fname_no_ext = original_filename.rsplit('.', 1)[0]
            parts = fname_no_ext.split('-')

            cnic = parts[1].strip() if len(parts) >= 3 else None
            customer_name = None
            if len(parts) >= 3:
                customer_name = parts[2].replace('_', ' ').strip().title()

            # Prepare escaped values
            app_no_esc = application_no.replace("'", "''")
            cnic_esc   = cnic.replace("'", "''") if cnic else None
            name_esc   = customer_name.replace("'", "''") if customer_name else None

            insert_rows.append({
                'application_no': app_no_esc,
                'cnic': cnic_esc,
                'customer_name': name_esc,
                'image_data_hex': image_bytes.hex(),
                'created_by': str(get_current_user_id()),
                'modified_by': str(get_current_user_id()),
            })

            app_image_counts[application_no] = app_image_counts.get(application_no, 0) + 1

            if application_no not in app_metadata:
                app_metadata[application_no] = {
                    'cnic': cnic,
                    'customer_name': customer_name,
                    'folder_name': folder_name or 'Root'
                }

            application.logger.debug(
                f"Will insert - App: {application_no} | "
                f"File: {original_filename} | Hash: {image_hash[:12]}... | Size: {image_size} bytes"
            )

    application.logger.info(f"Prepared {len(insert_rows)} new images for batch insert")

    # Step 4: Perform batch insert
    if insert_rows:
        try:
            values_clauses = []
            for row in insert_rows:
                cnic_sql = f"'{row['cnic']}'" if row['cnic'] else 'NULL'
                name_sql = f"'{row['customer_name']}'" if row['customer_name'] else 'NULL'

                values_clauses.append(f"""
                    (
                        '{row['application_no']}',
                        {cnic_sql},
                        {name_sql},
                        decode('{row['image_data_hex']}', 'hex'),
                        1,
                        {row['created_by']},
                        {row['modified_by']}
                    )
                """)

            insert_query = f"""
            INSERT INTO tbl_pre_disbursement_application_images (
                application_no, cnic, customer_name, image_data, status, created_by, modified_by
            ) VALUES
            {','.join(values_clauses)}
            """

            application.logger.debug("Executing batch INSERT...")
            execute_command(insert_query)

            results['processed'] = len(insert_rows)
            application.logger.info(f"Successfully inserted {len(insert_rows)} images")

        except Exception as e:
            application.logger.error(f"Batch insert failed: {str(e)}", exc_info=True)
            results['skipped'] += len(insert_rows)
            results['processed'] = 0

    # Step 5: Build summary for response
    for app_no in sorted(app_image_counts.keys()):
        meta = app_metadata.get(app_no, {})
        results['applications'].append({
            'application_no': app_no,
            'images_added': app_image_counts[app_no],
            'skipped': 0,  # per-app skipped count not tracked in this version
            'cnic': meta.get('cnic'),
            'customer_name': meta.get('customer_name'),
            'folder_name': meta.get('folder_name')
        })

    application.logger.info(
        f"Processing finished → Processed: {results['processed']}, "
        f"Skipped: {results['skipped']}, "
        f"Applications: {len(results['applications'])}"
    )

    return results


def handle_validation(file_type, input_timestamp=None):
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

    if input_timestamp:
        session['input_timestamp'] = input_timestamp
        print(f"handle_validation: Set session['input_timestamp']={input_timestamp}")

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
            'Annual Business Incomes',
            'Annual Disposable Income',
            'Annual Expenses',
            'Appraised Date',
            'Application No',
            'ApplicationDate',
            'Bcc Approval Date',
            'Borrower Name',
            'Branch Area',
            'Branch Name',
            'Business Expense Description',
            'Client Dob',
            'Co Borrower Dob',
            'Collage/Univeristy',
            'Collateral Type',
            'Contact No',
            'Credit History (Ecib)',
            'Current Residencial',
            'Dbr',
            'Education Level',
            'Enrollment Status',
            'Enterprise Premises',
            'Experiense (Start Date)',
            'Family Monthly Income',
            'Father/Husband Name',
            'Gender',
            'Loan Amount',
            'Loan Cycle',
            'Loan Officer',
            'Loan Per Exposure',
            'Loan Product Code',
            'Loan Status',
            'Markup Rate',
            'Monthly Repayment Capacity',
            'Nature of Business',
            'No Of Family Members',
            'Other Bank Loans Os',
            'Permanent Residencial',
            'Purpose of Loan',
            'Relationship Ownership',
            'Repayment Frequency',
            'Requested Loan Amount',
            'Residance Type',
            'Student Co Borrower Gender',
            'Student Name',
            'Student Relation With Borrower',
            'Tenor Of Month',
            'Verfied Date Date'
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
    input_timestamp = session.get('input_timestamp')

    print(f"handle_upload: file_type={file_type}, category={category}, files={len(filepaths)}, has_pre={has_pre}, has_post={has_post}, input_timestamp={input_timestamp}")

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
    session.pop('input_timestamp', None)
    print("handle_upload: Cleared session['input_timestamp']")

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
    input_timestamp = session['input_timestamp']
    print(f"process_upload: file_type={file_type}, category={category}, files={len(filepaths)}, input_timestamp={input_timestamp}")
    duplicates = {}
    new_records = {}
    summary_path = None
    print("process_upload: Initialized duplicates, new_records, summary_path")

    pre_headers = [
        'annual_business_incomes',
        'annual_disposable_income',
        'annual_expenses',
        'appraised_date',
        'application_no',
        'applicationdate',
        'bcc_approval_date',
        'borrower_name',
        'branch_area',
        'branch_name',
        'business_expense_description',
        'client_dob',
        'co_borrower_dob',
        'collage_univeristy',
        'collateral_type',
        'contact_no',
        'credit_history_(ecib)',
        'current_residencial',
        'dbr',
        'education_level',
        'enrollment_status',
        'enterprise_premises',
        'experiense_(start_date)',
        'family_monthly_income',
        'father_husband_name',
        'gender',
        'loan_amount',
        'loan_cycle',
        'loan_officer',
        'loan_per_exposure',
        'loan_product_code',
        'loan_status',
        'markup_rate',
        'monthly_repayment_capacity',
        'nature_of_business',
        'no_of_family_members',
        'other_bank_loans_os',
        'permanent_residencial',
        'purpose_of_loan',
        'relationship_ownership',
        'repayment_frequency',
        'requested_loan_amount',
        'residance_type',
        'student_co_borrower_gender',
        'student_name',
        'student_relation_with_borrower',
        'tenor_of_month',
        'verfied_date_date'
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
                    # existing_records = fetch_records(f'SELECT "{key_column}" FROM {table_name}')
                    # print(f"process_upload: Fetched {len(existing_records)} existing records for post_disbursement")
                    # existing_app_nos = {str(row[key_column]): None for row in existing_records}
                    # print(f"process_upload: Created existing_app_nos with {len(existing_app_nos)} entries")

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

                # for _, row in df.iterrows():
                #     key = str(row[key_column])
                #     print(f"process_upload: Checking row with {key_column}={key}")
                #     if key in existing_app_nos and (file_type != 'pre_disbursement' or existing_app_nos[key] != '3'):
                #         duplicates[sheet_name].append(row)
                #         print(f"process_upload: Added row to duplicates for sheet '{sheet_name}'")
                #     else:
                #         new_records[sheet_name].append(row)
                #         print(f"process_upload: Added row to new_records for sheet '{sheet_name}'")

                for _, row in df.iterrows():
                    new_records[sheet_name].append(row)
                    print(f"process_upload: Added row to new_records for sheet '{sheet_name}'")


                # duplicates[sheet_name] = pd.DataFrame(duplicates[sheet_name], columns=df.columns)
                # print(f"process_upload: Converted duplicates for sheet '{sheet_name}' to DataFrame with {len(duplicates[sheet_name])} rows")
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
                # duplicates = {f'combined_{category}': pd.concat([duplicates[s] for s in duplicates if len(duplicates[s]) > 0], ignore_index=True)}
                # duplicates[f'combined_{category}'] = pd.concat(
                #     [duplicates[s] for s in duplicates if len(duplicates[s]) > 0],
                #     ignore_index=True
                # ) if any(len(duplicates[s]) > 0 for s in duplicates) else pd.DataFrame()
                # print(f"process_upload: Set duplicates to combined DataFrame for 'both' with {len(duplicates[f'combined_{category}'])} rows")
        else:
            new_records = {k: v for k, v in new_records.items() if len(v) > 0}
            print(f"process_upload: Filtered new_records: {list(new_records.keys())}")
            # duplicates = {k: v for k, v in duplicates.items() if len(v) > 0}
            # print(f"process_upload: Filtered duplicates: {list(duplicates.keys())}")

        if len(new_records) > 0:
            print(f"process_upload: Processing {len(new_records)} new_records for insertion")
            date_columns = ['applicationdate', 'bcc_approval_date', 'business_experiense_(since)',
                            'experiense_(start_date)'] if file_type == 'pre_disbursement' else ['mis_date',
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

                pre_disbursement_queries = []
                post_disbursement_queries = []
                for rec in df.to_dict('records'):
                    print(f"process_upload: Processing record in DataFrame '{df_key}'")
                    if file_type == 'pre_disbursement' and str(rec['application_no']) not in ['', 'NaN', 'None']:
                        education_level = str(rec.get('education_level'))
                        no_of_family_members = str(rec.get('no_of_family_members', ''))
                        tenor_of_month = str(rec.get('tenor_of_month', ''))
                        cnic = str(rec.get('cnic'))
                        appraised_date = str(rec.get('appraised_date'))
                        client_dob = str(rec.get('client_dob'))
                        co_borrower_dob = str(rec.get('co_borrower_dob'))
                        verfied_date_date = str(rec.get('verfied_date_date'))


                        # Extract and clean data from the sheet
                        rec_borrower_name = str(rec.get('borrower_name', '')).strip().lower()
                        rec_gender = str(rec.get('gender', '')).strip().lower()
                        rec_branch_name = str(rec.get('branch_name', '')).strip().lower()
                        rec_student_name = str(rec.get('student_name', '')).strip().lower()
                        rec_student_co_borrower_gender = str(rec.get('student_co_borrower_gender', '')).strip().lower()
                        rec_college_university = str(rec.get('collage_univeristy', '')).strip().lower()

                        # Query to fetch the latest record from tbl_pre_disbursement_temp for the given CNIC
                        query = f"""
                                SELECT pdt.pre_disb_temp_id, pdt."Borrower_Name", pdt."Gender", pdt."Branch_Name", 
                                       pdt."Student_Name", pdt."Student_Co_Borrower_Gender", pdt."Collage_Univeristy"
                                FROM tbl_pre_disbursement_temp pdt 
                                WHERE pdt."CNIC" = '{cnic}' 
                                ORDER BY pdt.pre_disb_temp_id DESC 
                                LIMIT 1
                            """

                        try:
                            # Execute the query using the predefined execute_command function
                            result = execute_command(query)

                            if result:
                                # Extract database record fields
                                db_pre_disb_temp_id, db_borrower_name, db_gender, db_branch_name, \
                                    db_student_name, db_student_co_borrower_gender, db_college_university = result[0]

                                # Clean database fields (handle None and convert to lowercase)
                                db_borrower_name = str(db_borrower_name or '').strip().lower()
                                db_gender = str(db_gender or '').strip().lower()
                                db_branch_name = str(db_branch_name or '').strip().lower()
                                db_student_name = str(db_student_name or '').strip().lower()
                                db_student_co_borrower_gender = str(db_student_co_borrower_gender or '').strip().lower()
                                db_college_university = str(db_college_university or '').strip().lower()

                                # Check for anomalies
                                anomalies = []
                                if rec_borrower_name != db_borrower_name:
                                    anomalies.append(
                                        f"Borrower Name mismatch: Sheet='{rec_borrower_name}', DB='{db_borrower_name}'")
                                if rec_gender != db_gender:
                                    anomalies.append(f"Gender mismatch: Sheet='{rec_gender}', DB='{db_gender}'")
                                if rec_branch_name != db_branch_name:
                                    anomalies.append(
                                        f"Branch Name mismatch: Sheet='{rec_branch_name}', DB='{db_branch_name}'")
                                if rec_student_name != db_student_name:
                                    anomalies.append(
                                        f"Student Name mismatch: Sheet='{rec_student_name}', DB='{db_student_name}'")
                                if rec_student_co_borrower_gender != db_student_co_borrower_gender:
                                    anomalies.append(
                                        f"Student Co-Borrower Gender mismatch: Sheet='{rec_student_co_borrower_gender}', DB='{db_student_co_borrower_gender}'")
                                if rec_college_university != db_college_university:
                                    anomalies.append(
                                        f"College/University mismatch: Sheet='{rec_college_university}', DB='{db_college_university}'")

                                # If anomalies are found, insert them into tbl_pre_disb_anomalies
                                if anomalies:
                                    details = "; ".join(anomalies)
                                    insert_query = f"""
                                            INSERT INTO tbl_pre_disb_anomalies (pre_disb_id, details, created_date)
                                            VALUES ({db_pre_disb_temp_id}, '{details}', '{datetime.now()}')
                                        """
                                    execute_command(insert_query)
                                    print(f"Anomalies recorded for pre_disb_id {db_pre_disb_temp_id}: {details}")
                                else:
                                    print("No anomalies found.")
                            else:
                                print(f"No record found in tbl_pre_disbursement_temp for CNIC: {cnic}")

                        except Exception as e:
                            print(f"Error executing query: {e}")


                        if education_level in ['None', 'NaN', 'Nan', '']:
                            education_level = 'N/A'
                        else:
                            # Example: strip spaces and escape single quotes
                            education_level = education_level.strip().replace("'", "''")

                        if no_of_family_members in ['None', 'NaN', 'Nan', '']:
                            no_of_family_members = '0'

                        if tenor_of_month in ['None', 'NaN', 'Nan', '']:
                            tenor_of_month = '0'

                        if appraised_date in ['None', 'NaN', 'Nan', '']:
                            appraised_date = '1900-01-01'

                        if client_dob in ['None', 'NaN', 'Nan', '']:
                            client_dob = '1900-01-01'

                        if verfied_date_date in ['None', 'NaN', 'Nan', '']:
                            verfied_date_date = '1900-01-01'

                        if co_borrower_dob in ['None', 'NaN', 'Nan', '']:
                            co_borrower_dob = '1900-01-01'

                        client_dob_formatted = format_date_for_sql(client_dob, str(rec['application_no']))
                        co_borrower_dob_formatted = format_date_for_sql(co_borrower_dob, str(rec['application_no']))


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
                                "annual_income", "markup_rate", "repayment_frequency", "loan_officer",
                                "appraised_date", "verfied_date_date", "loan_per_exposure", "client_dob",
                                "co_borrower_dob", "relationship_ownership", "other_bank_loans_os",
                                "status", "uploaded_by", "uploaded_date"
                            ) VALUES (
                                '{rec.get('application_no', '')}', '{rec.get('annual_business_incomes', '')}', '{rec.get('annual_disposable_income', '')}',
                                '{rec.get('annual_expenses', '')}', '{rec.get('applicationdate', '')}', '{rec.get('bcc_approval_date', '')}',
                                '{rec.get('borrower_name', '')}', '{rec.get('branch_area', '')}', '{rec.get('branch_name', '')}',
                                '{rec.get('business_expense_description', '').replace(',', ' and ')}', '{rec.get('business_experiense_(since)', '1900-01-01')}',
                                '{rec.get('business_premises', '')}', '{rec.get('cnic', '')}', '{rec.get('collage_univeristy', '')}',
                                '{rec.get('collateral_type', '')}', '{rec.get('contact_no', '')}', '{rec.get('credit_history_(ecib)', '')}',
                                '{rec.get('current_residencial', '')}', '{rec.get('dbr', '')}', '{education_level}',
                                '{rec.get('enrollment_status', '')}', '{rec.get('enterprise_premises', '')}', '{rec.get('existing_loan_number', '')}',
                                '{rec.get('existing_loan_limit', '')}', '{rec.get('existing_loan_status', '')}',
                                '{rec.get('existing_outstanding_loan_schedules', '')}', '{rec.get('experiense_(start_date)', '')}',
                                '{rec.get('family_monthly_income', '')}', '{rec.get('father_husband_name', '')}', '{rec.get('gender', '')}',
                                '{rec.get('kf_remarks', '')}', '{rec.get('loan_amount', '')}', '{rec.get('loan_cycle', '')}',
                                '{rec.get('loanproductcode', '')}', '{rec.get('loan_status', '')}', '{rec.get('monthly_repayment_capacity', '')}',
                                '{rec.get('nature_of_business', '')}', '{no_of_family_members}', '{rec.get('permanent_residencial', '')}',
                                '{rec.get('premises', '')}', '{sanitize_file_columns(str(rec.get('purpose_of_loan', '')))}', '{rec.get('requested_loan_amount', '')}',
                                '{rec.get('residance_type', '')}', '{rec.get('student_name', '')}', '{rec.get('student_co_borrower_gender', '')}',
                                '{rec.get('student_relation_with_borrower', '')}', '{tenor_of_month}', '{rec.get('type_of_business', '')}',
                                '{rec.get('annual_income', '')}', '{rec.get('markup_rate', '')}', '{rec.get('repayment_frequency', '')}',
                                '{rec.get('loan_officer', '')}', '{appraised_date}', '{verfied_date_date}',
                                '{rec.get('loan_per_exposure', '')}',  '{str(client_dob_formatted)}', '{str(co_borrower_dob_formatted)}',
                                '{rec.get('relationship_ownership', '')}', '{rec.get('other_bank_loans_os', '')}', '1',
                                '{str(get_current_user_id())}', '{str(datetime.now())}'
                            )
                        """
                        pre_disbursement_queries.append(query)
                        print(
                            f"process_upload: Preparing INSERT query for pre_disbursement, application_no={rec.get('application_no', '')}")
                    else:
                        loan_closed_on = str(rec.get('loan_closed_on', ''))
                        booked_on = str(rec.get('booked_on', ''))
                        clo_on = str(rec.get('clo_on', ''))

                        if loan_closed_on in ['None', 'NaN', 'Nan', '']:
                            loan_closed_on = '1900-01-01'

                        if booked_on in ['None', 'NaN', 'Nan', '']:
                            booked_on = '1900-01-01'

                        if clo_on in ['None', 'NaN', 'Nan', '']:
                            clo_on = '1900-01-01'

                        loan_no = rec.get('loan_no', '').replace("'", '')
                        if loan_no not in ['', 'NaN', 'None']:
                            mis_date = input_timestamp or '1900-01-01'
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
                                        '{mis_date}', '{rec.get('area', '')}', '{rec.get('sector_code', '')}',
                                        '{rec.get('branch_code', '')}', '{rec.get('branch_name', '')}', '{rec.get('cnic', '')}',
                                        '{rec.get('gender', '')}', '{sanitize_file_columns(str(rec.get('address', '')))}', '{rec.get('mobile_no', '')}',
                                        '{rec.get('loan_title', '')}', '{rec.get('rt', '')}', '{loan_no}',
                                        '{rec.get('product_code', '')}', '{booked_on}',
                                        '{rec.get('disbursed_amount', '')}', '{rec.get('repayment_type', '')}',
                                        '{rec.get('sector', '')}', '{rec.get('purpose', '')}', '{rec.get('loan_status', '')}',
                                        '{loan_closed_on}', '{rec.get('act_clo', '')}',
                                        '{rec.get('colloanno', '')}', '{rec.get('coll_id', '')}', '{rec.get('lrno', '')}',
                                        '{rec.get('collat', '')}', '{rec.get('coll_stat', '')}', '{rec.get('collateral_value', '')}',
                                        '{rec.get('collateral_title', '')}', '{rec.get('overdue_days', '')}',
                                        '{rec.get('principal_outstanding', '')}', '{rec.get('total_outstand_other', '')}',
                                        '{rec.get('markup_outstanding', '')}', '{rec.get('lo', '')}', '{rec.get('fc_los', '')}',
                                        '{rec.get('dtf', '')}', '{rec.get('dtt', '')}', '{rec.get('customer_id', '')}',
                                        '{rec.get('application_num', '')}', '{clo_on}',
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

        if file_type == 'pre_disbursement' and any(len(duplicates[sheet]) > 0 for sheet in duplicates):
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
    # print(f"parse_excel_date: Entering function with date_str={date_str}")
    if pd.isnull(date_str):
        # print("parse_excel_date: Date is null, returning '1900-01-01'")
        return '1900-01-01'

    if not date_str:
        # print("parse_excel_date: Date is empty, returning '1900-01-01'")
        return '1900-01-01'

    if isinstance(date_str, datetime):
        # print("parse_excel_date: Date is datetime, returning date part")
        return date_str.date()

    clean_date = str(date_str).strip().replace('\r', '').replace('\n', '')
    # print(f"parse_excel_date: Cleaned date string: {clean_date}")

    # Try known formats first
    for fmt in (
        "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d", "%Y-%m-%d",
        "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y"
    ):
        try:
            result = datetime.strptime(clean_date, fmt).date()
            # print(f"parse_excel_date: Parsed date with format {fmt}: {result}")
            return result
        except ValueError:
            # print(f"parse_excel_date: Failed to parse with format {fmt}")
            continue

    # Try ISO and other common formats using dateutil
    try:
        result = parse(clean_date).date()
        # print(f"parse_excel_date: Parsed date with dateutil: {result}")
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


def sanitize_file_columns(address: str) -> str:
    """
    Sanitize address string to prevent SQL query issues.
    Removes or escapes problematic characters and handles None/empty values.
    """
    if not address or not isinstance(address, str):
        print("Address is None or not a string, returning empty string")
        return ''

    # Remove or replace problematic characters (e.g., #, ;, --)
    # You can customize this regex based on specific needs
    cleaned_address = re.sub(r'[;\'"\--]', '', address.strip())

    # Log if significant cleaning was done
    if cleaned_address != address.strip():
        print(f"Cleaned address from '{address}' to '{cleaned_address}'")

    return cleaned_address


def format_date_for_sql(date_str: str, application_no: str = None) -> str:
    """
    Converts a date string to ISO format (YYYY-MM-DD) for SQL.
    Flashes messages including the application number and date string on errors.

    :param date_str: Input date string.
    :param application_no: Application number for context in flash messages.
    :return: ISO format string or None.
    """
    if not date_str or date_str.strip() == '':
        flash_msg = f"Application {application_no}: Date is missing or empty."
        flash(flash_msg, "danger")
        return '1900-01-01'

    cleaned = date_str.strip()

    invalid_dates = {'0000-00-00', '1974-00-00', '00-00-0000', '0/0/0000', '0-0-0'}

    if cleaned in invalid_dates:
        flash_msg = f"Application {application_no}: Invalid date detected '{cleaned}'. Date will be saved as NULL."
        flash(flash_msg, "danger")
        return '1900-01-01'

    possible_formats = [
        '%d/%m/%Y', '%d-%m-%Y',
        '%Y/%m/%d', '%Y-%m-%d',
        '%m/%d/%Y', '%m-%d-%Y',
        '%d.%m.%Y', '%Y.%m.%d'
    ]

    for fmt in possible_formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.date().isoformat()
        except ValueError:
            continue

    flash_msg = f"Application {application_no}: Unrecognized date format '{cleaned}'. Date will be saved as NULL."
    flash(flash_msg, "danger")
    return '1900-01-01'
