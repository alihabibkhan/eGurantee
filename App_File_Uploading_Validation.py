from imports import *
from application import application
from application import allowed_file
import uuid
from pdf_helper import *

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


# def process_zip_application_images(zip_file):
#     """
#     Process uploaded ZIP file:
#     - Extracts images
#     - Parses application number from folder name
#     - Parses CNIC & customer name from filename
#     - Saves binary image data to BYTEA column if not duplicate
#     - Returns summary for display
#     """
#     results = {
#         'processed': 0,
#         'skipped': 0,
#         'applications': []   # list of dicts for display
#     }
#
#     # Read ZIP content
#     zip_content = BytesIO(zip_file.read())
#     with ZipFile(zip_content) as zf:
#         for file_name in zf.namelist():
#             if not file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
#                 continue
#
#             folder_path = os.path.dirname(file_name)
#             folder_name = os.path.basename(folder_path) if folder_path else ""
#
#             # Extract application number from folder name
#             # Examples: loan_1222355_20251210, app-456789_2025-12-30, etc.
#             app_match = re.search(r'(?:loan|app|application)[_-]?(\d+)', folder_name, re.IGNORECASE)
#             if not app_match:
#                 continue
#
#             application_no = app_match.group(1)
#
#             # Read raw image bytes
#             with zf.open(file_name) as img_file:
#                 image_bytes = img_file.read()
#
#             original_filename = os.path.basename(file_name)
#
#             # Parse CNIC and customer name from filename
#             # Expected format: 1222355-3740531323050-ASMAA_IQBAL.jpg
#             fname_no_ext = original_filename.rsplit('.', 1)[0]
#             parts = fname_no_ext.split('-')
#             cnic = parts[1].strip() if len(parts) >= 3 else None
#             customer_name = None
#             if len(parts) >= 3:
#                 customer_name = parts[2].replace('_', ' ').strip().title()
#
#             # Escape values for f-string (basic protection)
#             app_no_esc = application_no.replace("'", "''")
#             cnic_esc   = cnic.replace("'", "''")   if cnic else None
#             name_esc   = customer_name.replace("'", "''") if customer_name else None
#
#             # Check if this exact image content already exists for this application
#             check_query = f"""
#             SELECT pd_ai_id
#             FROM tbl_pre_disbursement_application_images
#             WHERE application_no = '{app_no_esc}'
#               AND image_data = decode('{image_bytes.hex()}', 'hex')
#             LIMIT 1;
#             """
#
#             exists = execute_command(check_query)
#             if exists:
#                 results['skipped'] += 1
#                 continue
#
#             # Build insert query with f-string
#             cnic_sql = f"'{cnic_esc}'" if cnic_esc else 'NULL'
#             name_sql = f"'{name_esc}'" if name_esc else 'NULL'
#
#             insert_query = f"""
#             INSERT INTO tbl_pre_disbursement_application_images (
#                 application_no,
#                 cnic,
#                 customer_name,
#                 image_data,
#                 status,
#                 created_by,
#                 modified_by
#             ) VALUES (
#                 '{app_no_esc}',
#                 {cnic_sql},
#                 {name_sql},
#                 decode('{image_bytes.hex()}', 'hex'),
#                 1,
#                 {str(get_current_user_id())},
#                 {str(get_current_user_id())}
#             );
#             """
#
#             try:
#                 execute_command(insert_query)
#                 results['processed'] += 1
#
#                 # Aggregate per application for display
#                 app_entry = next(
#                     (a for a in results['applications'] if a['application_no'] == application_no),
#                     None
#                 )
#                 if app_entry:
#                     app_entry['images_added'] += 1
#                 else:
#                     results['applications'].append({
#                         'application_no': application_no,
#                         'images_added': 1,
#                         'skipped': 0,
#                         'cnic': cnic,
#                         'customer_name': customer_name,
#                         'folder_name': folder_name or 'Root'
#                     })
#
#             except Exception as insert_error:
#                 application.logger.error(f"Insert failed for {application_no}: {str(insert_error)}")
#                 results['skipped'] += 1
#
#     return results


def process_zip_application_images(zip_file, user_id=None):
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

    if user_id is None:
        user_id = get_current_user_id()
    else:
        user_id = '0'

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
                'created_by': str(user_id),
                'modified_by': str(user_id),
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
    application.logger.debug(
        f"handle_validation: Entering with file_type={file_type}, input_timestamp={input_timestamp}")
    if 'file' not in request.files:
        application.logger.warning("handle_validation: No file in request.files")
        flash('No file selected.', 'danger')
        return redirect(url_for('manage_file'))

    files = request.files.getlist('file')
    if not files or all(f.filename == '' for f in files):
        application.logger.warning("handle_validation: No valid files selected")
        flash('No file selected.', 'danger')
        return redirect(url_for('manage_file'))

    category = request.form.get('category') if file_type == 'post_disbursement' else None
    if file_type == 'post_disbursement' and not category:
        application.logger.warning("handle_validation: Post disbursement but no category")
        flash('Please select a category for Post Disbursement.', 'danger')
        return redirect(url_for('manage_file'))

    if file_type == 'pre_disbursement' and len(files) > 1:
        application.logger.warning("handle_validation: Multiple files for pre_disbursement")
        flash('Only one file allowed for Pre Disbursement.', 'danger')
        return redirect(url_for('manage_file'))
    elif file_type == 'post_disbursement':
        if category in ['los', 'mis'] and len(files) != 1:
            application.logger.warning(f"handle_validation: Invalid file count for {category}")
            flash(f'Exactly one file is required for {category.upper()}.', 'danger')
            return redirect(url_for('manage_file'))
        elif category == 'both' and len(files) != 2:
            application.logger.warning("handle_validation: Invalid file count for 'both'")
            flash('Exactly two files are required for both LOS and MIS.', 'danger')
            return redirect(url_for('manage_file'))

    saved_files = []
    all_sheets = []
    all_counts = {}
    sheet_info_list = []
    has_pre = file_type == 'pre_disbursement'
    has_post = file_type == 'post_disbursement'

    for file_idx, file in enumerate(files):
        application.logger.debug(f"handle_validation: Processing file {file_idx + 1}, filename={file.filename}")
        if not allowed_file(file.filename):
            application.logger.warning(f"handle_validation: File {file.filename} not allowed")
            flash(f'File {file.filename}: Only .xlsx files are allowed.', 'danger')
            # Clean up saved files
            for saved_file in saved_files:
                try:
                    os.remove(saved_file)
                    application.logger.debug(f"handle_validation: Removed file {saved_file}")
                except Exception:
                    application.logger.error(f"handle_validation: Failed to remove file {saved_file}")
            return redirect(url_for('manage_file'))

        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        saved_files.append(filepath)
        application.logger.debug(f"handle_validation: Saved file {filepath}")

        success, result = validate_excel(filepath, file_type, category, file_idx)
        if not success:
            application.logger.warning(f"handle_validation: Validation failed: {result}")
            for saved_file in saved_files:
                try:
                    os.remove(saved_file)
                    application.logger.debug(f"handle_validation: Removed file {saved_file}")
                except Exception:
                    application.logger.error(f"handle_validation: Failed to remove file {saved_file}")
            flash(result, 'warning')
            return redirect(url_for('manage_file'))

        all_sheets.extend(result['sheets_available'])
        all_counts.update(result['record_counts'])
        sheet_info_list.extend(result['sheet_info_list'])
        has_pre |= result['has_pre']
        has_post |= result['has_post']

    # Batch session updates
    session.update({
        'current_files': saved_files,
        'has_pre': has_pre,
        'has_post': has_post,
        'file_type': file_type,
        'category': category,
        'input_timestamp': input_timestamp if input_timestamp else None
    })
    application.logger.debug(f"handle_validation: Updated session with {len(saved_files)} files")

    return render_template('upload.html',
                           view='validation_result',
                           sheet_info_list=sheet_info_list,
                           filename=', '.join([os.path.basename(f) for f in saved_files]),
                           sheets=all_sheets,
                           counts=all_counts,
                           file_type=file_type,
                           category=category)


def validate_excel(filepath, file_type, category=None, file_idx=0):
    application.logger.debug(
        f"validate_excel: Entering with filepath={filepath}, file_type={file_type}, category={category}, file_idx={file_idx}")
    try:
        # Define headers once to avoid repetition
        headers = {
            'pre_disbursement': [
                'Annual Business Incomes', 'Annual Disposable Income', 'Annual Expenses', 'Appraised Date',
                'Application No', 'ApplicationDate', 'Bcc Approval Date', 'Borrower Name', 'Branch Area',
                'Branch Name', 'Business Expense Description', 'Client Dob', 'Co Borrower Dob',
                'Collage/Univeristy', 'Collateral Type', 'Contact No', 'Credit History (Ecib)',
                'Current Residencial', 'Dbr', 'Education Level', 'Enrollment Status', 'Enterprise Premises',
                'Experiense (Start Date)', 'Family Monthly Income', 'Father/Husband Name', 'Gender',
                'Loan Amount', 'Loan Cycle', 'Loan Officer', 'Loan Per Exposure', 'Loan Product Code',
                'Loan Status', 'Markup Rate', 'Monthly Repayment Capacity', 'Nature of Business',
                'No Of Family Members', 'Other Bank Loans Os', 'Permanent Residencial', 'Purpose of Loan',
                'Relationship Ownership', 'Repayment Frequency', 'Requested Loan Amount', 'Residance Type',
                'Student Co Borrower Gender', 'Student Name', 'Student Relation With Borrower', 'Tenor Of Month',
                'Verfied Date Date'
            ],
            'los': [
                'sector_code', 'branch_code', 'branch_name', 'cnic', 'gender', 'address', 'mobile_number',
                'loan_title', 'rt', 'loan_number', 'product_code', 'loancreationdate', 'disb_amt',
                'loanrepaymenttype', 'sector', 'purpose', 'loanstatus', 'closed_on_date', 'act_clo',
                'colloanno', 'coll_id', 'lrno', 'collat', 'coll_stat', 'collateral_value', 'collateraltitle',
                'od_days', 'os_p', 'total_outstand_other', 'total_outstand_markup', 'lo', 'fc_los', 'dtf',
                'dtt', 'customer_id', 'application_num'
            ],
            'mis': [
                'sector_code', 'bcode', 'branch_name', 'customer_id', 'gender', 'address', 'mobile',
                'loantitle', 'rt', 'loanno', 'product_code', 'loancreationdate', 'disbursedamt',
                'loanrepaymenttype', 'sector', 'purpose', 'loanstatus', 'ln_clo_dt', 'act_clo',
                'colloanno', 'coll_id', 'lrno', 'collateral_type', 'coll_stat', 'collateral_value',
                'collateraltitle', 'od_days', 'total_outstand_principal', 'total_outstand_other',
                'total_outstand_markup', 'clo_on', 'liab_id', 'pool_id', 'account_number'
            ]
        }

        expected_headers = headers.get(file_type, [])
        if file_type == 'post_disbursement':
            expected_headers = headers['los'] if category == 'los' or (category == 'both' and file_idx == 0) else \
            headers['mis']
            if not expected_headers:
                application.logger.error(f"validate_excel: Invalid category={category}")
                return False, f"Invalid category: {category}"

        xls = pd.ExcelFile(filepath)
        sheets = [o for o in xls.sheet_names if o != 'GVMetadata']
        record_counts = {}
        sheet_info_list = []

        for sheet_name in sheets:
            application.logger.debug(f"validate_excel: Processing sheet '{sheet_name}'")
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

            if df.columns.duplicated().any():
                duplicates = df.columns[df.columns.duplicated()].tolist()
                application.logger.warning(f"validate_excel: Duplicate columns in sheet '{sheet_name}': {duplicates}")
                return False, f"Duplicate column names found in sheet {sheet_name}: {duplicates}"

            # Add missing headers in one operation
            missing_headers = [h for h in expected_headers if h not in df.columns]
            if missing_headers:
                application.logger.debug(f"validate_excel: Adding missing headers: {missing_headers}")
                df = df.reindex(columns=df.columns.tolist() + missing_headers, fill_value='')

            unique_id = uuid.uuid4().hex
            row_count = len(df)
            record_counts[f"{sheet_name}_{unique_id}"] = row_count
            sheet_info_list.append({
                'sheet_name': sheet_name,
                'uuid': unique_id,
                'record_count': row_count
            })

        return True, {
            'sheets_available': sheets,
            'record_counts': record_counts,
            'sheet_info_list': sheet_info_list,
            'has_pre': file_type == 'pre_disbursement',
            'has_post': file_type == 'post_disbursement'
        }
    except Exception as e:
        application.logger.error(f"validate_excel: Error reading Excel file: {str(e)}")
        return False, f"Error reading Excel file: {str(e)}"


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def safe_remove(filepath):
    application.logger.debug(f"safe_remove: Attempting to remove file {filepath}")
    os.remove(filepath)
    application.logger.debug(f"safe_remove: File {filepath} deleted successfully.")


def handle_upload():
    application.logger.debug("handle_upload: Entering function")
    if 'current_files' not in session or not session['current_files']:
        application.logger.warning("handle_upload: No validated files in session")
        flash('No validated files found. Please validate a file first.', 'danger')
        return redirect(url_for('manage_file'))

    file_type = session.get('file_type')
    if not file_type:
        application.logger.warning("handle_upload: No file_type in session")
        flash('File type not found in session. Please start over.', 'danger')
        return redirect(url_for('manage_file'))

    filepaths = session['current_files']
    has_pre = session.get('has_pre', False)
    has_post = session.get('has_post', False)
    category = session.get('category')
    input_timestamp = session.get('input_timestamp')

    success, result = process_upload()
    if not success:
        application.logger.warning(f"handle_upload: Upload failed: {result}")
        flash(result, 'warning')
        return redirect(url_for('manage_file'))

    # Clean up files
    for filepath in filepaths:
        try:
            safe_remove(filepath)
            application.logger.debug(f"handle_upload: Removed file {filepath}")
        except Exception as e:
            application.logger.error(f"handle_upload: Failed to delete file {filepath}: {str(e)}")

    # Batch session cleanup
    session.pop('current_files', None)
    session.pop('has_pre', None)
    session.pop('has_post', None)
    session.pop('file_type', None)
    session.pop('category', None)
    session.pop('input_timestamp', None)
    application.logger.debug("handle_upload: Cleared session variables")

    if result['summary_path']:
        session['summary_file'] = result['summary_path']
        application.logger.debug(f"handle_upload: Set session['summary_file']={result['summary_path']}")

    # In handle_upload(), after getting result
    if result.get('anomalies_report_path'):
        session['anomalies_report'] = result['anomalies_report_path']
        session['anomalies_detected'] = result.get('anomalies_detected', False)
        application.logger.debug(f"handle_upload: Set session['anomalies_report']={result['anomalies_report_path']}")

    return render_template('upload.html',
                           view='upload_result',
                           duplicates=result['duplicates'],
                           new_records=result['new_records'],
                           has_summary=result['summary_path'] is not None)


# def process_upload():
#     application.logger.debug("process_upload: Entering function")
#     file_type = session.get('file_type')
#     category = session.get('category')
#     filepaths = session['current_files']
#     input_timestamp = session.get('input_timestamp') or '1900-01-01'
#
#     duplicates = {}
#     new_records = {}
#     summary_path = None
#
#     # Define headers and mappings
#     pre_headers = [
#         'annual_business_incomes', 'annual_disposable_income', 'annual_expenses', 'appraised_date',
#         'application_no', 'applicationdate', 'bcc_approval_date', 'borrower_name', 'branch_area',
#         'branch_name', 'business_expense_description', 'client_dob', 'co_borrower_dob',
#         'collage_univeristy', 'collateral_type', 'contact_no', 'credit_history_(ecib)',
#         'current_residencial', 'dbr', 'education_level', 'enrollment_status', 'enterprise_premises',
#         'experiense_(start_date)', 'family_monthly_income', 'father_husband_name', 'gender',
#         'loan_amount', 'loan_cycle', 'loan_officer', 'loan_per_exposure', 'loan_product_code',
#         'loan_status', 'markup_rate', 'monthly_repayment_capacity', 'nature_of_business',
#         'no_of_family_members', 'other_bank_loans_os', 'permanent_residencial', 'purpose_of_loan',
#         'relationship_ownership', 'repayment_frequency', 'requested_loan_amount', 'residance_type',
#         'student_co_borrower_gender', 'student_name', 'student_relation_with_borrower',
#         'tenor_of_month', 'verfied_date_date'
#     ]
#     post_headers = [
#         'mis_date', 'area', 'sector_code', 'branch_code', 'branch_name', 'cnic', 'gender',
#         'address', 'mobile_no', 'loan_title', 'rt', 'loan_no', 'product_code', 'booked_on',
#         'disbursed_amount', 'repayment_type', 'sector', 'purpose', 'loan_status', 'loan_closed_on',
#         'act_clo', 'colloanno', 'coll_id', 'lrno', 'collat', 'coll_stat', 'collateral_value',
#         'collateral_title', 'overdue_days', 'principal_outstanding', 'total_outstand_other',
#         'markup_outstanding', 'lo', 'fc_los', 'dtf', 'dtt', 'customer_id', 'application_num',
#         'clo_on', 'liab_id', 'pool_id', 'account_number'
#     ]
#     post_to_los_mapping = {
#         'branch_code': 'branch_code', 'branch_name': 'branch_name', 'cnic': 'cnic', 'gender': 'gender',
#         'address': 'address', 'mobile_no': 'mobile_number', 'loan_no': 'loan_number',
#         'loan_title': 'loan_title', 'product_code': 'product_code', 'booked_on': 'loancreationdate',
#         'disbursed_amount': 'disb_amt', 'principal_outstanding': 'os_p',
#         'markup_outstanding': 'total_outstand_markup', 'repayment_type': 'loanrepaymenttype',
#         'sector': 'sector', 'purpose': 'purpose', 'loan_status': 'loanstatus',
#         'overdue_days': 'od_days', 'loan_closed_on': 'closed_on_date', 'collateral_title': 'collateraltitle'
#     }
#     post_to_mis_mapping = {
#         'branch_code': 'bcode', 'branch_name': 'branch_name', 'cnic': 'customer_id', 'gender': 'gender',
#         'address': 'address', 'mobile_no': 'mobile', 'loan_no': 'loanno', 'loan_title': 'loantitle',
#         'product_code': 'product_code', 'booked_on': 'loancreationdate', 'disbursed_amount': 'disbursedamt',
#         'principal_outstanding': 'total_outstand_principal', 'markup_outstanding': 'total_outstand_markup',
#         'repayment_type': 'loanrepaymenttype', 'sector': 'sector', 'purpose': 'purpose',
#         'loan_status': 'loanstatus', 'overdue_days': 'od_days', 'loan_closed_on': 'ln_clo_dt',
#         'collateral_title': 'collateraltitle'
#     }
#     los_to_mis_mapping = {'collat': 'collateral_type'}
#
#     try:
#         # Fetch existing records once
#         existing_records = {}
#         if file_type == 'pre_disbursement':
#             records = fetch_records(
#                 'SELECT "Application_No", "status", "CNIC", "Borrower_Name", "Gender", "Branch_Name", '
#                 '"Student_Name", "Student_Co_Borrower_Gender", "Collage_Univeristy", '
#                 'KFT_Approved_Loan_Limit, "approved_date" FROM tbl_pre_disbursement_temp')
#             existing_records['pre'] = {str(row['Application_No']): row for row in records}
#             existing_records['cnic'] = {str(row['CNIC']): row for row in records if row['CNIC']}
#
#             existing_applications = set(existing_records['pre'].keys())
#             application.logger.debug(f"process_upload: Loaded {len(existing_applications)} existing application numbers")
#         else:
#             records = fetch_records('SELECT customer_id, branch_name, gender, loan_no, product_code, booked_on, '
#                                     'repayment_type, principal_outstanding, disbursed_amount FROM tbl_post_disbursement '
#                                     f'WHERE mis_date < \'{input_timestamp}\'')
#             existing_records['post'] = {str(row['customer_id']): row for row in records if row['customer_id']}
#
#         all_dfs = []
#         for file_idx, filepath in enumerate(filepaths):
#             xl = pd.ExcelFile(filepath)
#             sheet_names = [o for o in xl.sheet_names if o != 'GVMetadata']
#             for sheet_name in sheet_names:
#                 df = pd.read_excel(filepath, sheet_name=sheet_name, dtype=str).fillna('')
#                 df.columns = [col.strip().lower().replace('/', '_').replace(' ', '_') for col in df.columns]
#
#                 if df.columns.duplicated().any():
#                     duplicates = df.columns[df.columns.duplicated()].tolist()
#                     application.logger.error(f"process_upload: Duplicate columns in sheet '{sheet_name}': {duplicates}")
#                     raise ValueError(f"Duplicate column names found in sheet {sheet_name}: {duplicates}")
#
#                 expected_headers = pre_headers if file_type == 'pre_disbursement' else post_headers
#                 table_name = 'tbl_pre_disbursement_temp' if file_type == 'pre_disbursement' else 'tbl_post_disbursement'
#                 key_column = 'application_no' if file_type == 'pre_disbursement' else 'loan_no'
#
#                 if file_type == 'post_disbursement':
#                     mapping = post_to_los_mapping if category == 'los' or (category == 'both' and file_idx == 0) else post_to_mis_mapping
#                     inverse_mapping = {v: k for k, v in mapping.items()}
#
#                     # Check for duplicate columns before renaming
#                     if df.columns.duplicated().any():
#                         duplicates = df.columns[df.columns.duplicated()].tolist()
#                         application.logger.error(
#                             f"process_upload: Duplicate columns in sheet '{sheet_name}': {duplicates}")
#                         raise ValueError(f"Duplicate column names found in sheet {sheet_name}: {duplicates}")
#
#                     # Only rename columns that exist in the DataFrame
#                     rename_dict = {k: v for k, v in inverse_mapping.items() if k in df.columns}
#                     df = df.rename(columns=rename_dict)
#
#                     if category == 'both' and file_idx == 0:
#                         # Similarly for los_to_mis_mapping
#                         los_rename_dict = {k: v for k, v in los_to_mis_mapping.items() if k in df.columns}
#                         df = df.rename(columns=los_rename_dict)
#
#                 missing_headers = [h for h in expected_headers if h not in df.columns]
#                 if missing_headers:
#                     application.logger.warning(
#                         f"process_upload: Missing headers in sheet '{sheet_name}': {missing_headers}")
#                     flash(f"Sheet '{sheet_name}' is missing headers: {', '.join(missing_headers)}. Adding as blanks.",
#                           'warning')
#                     df = df.reindex(columns=df.columns.tolist() + missing_headers, fill_value='')
#
#                 if key_column not in df.columns:
#                     application.logger.error(
#                         f"process_upload: Key column '{key_column}' not found in sheet '{sheet_name}'")
#                     raise ValueError(f"Key column '{key_column}' not found in sheet {sheet_name}")
#
#                 duplicates[sheet_name] = []
#                 new_records[sheet_name] = df
#                 all_dfs.append(df)
#
#         # Merge datasets for 'both'
#         if file_type == 'post_disbursement' and category == 'both' and all_dfs:
#             combined_df = pd.concat(all_dfs, ignore_index=True)
#             new_records = {f'combined_{category}': combined_df}
#         else:
#             new_records = {k: v for k, v in new_records.items() if not v.empty}
#
#         if new_records:
#             date_columns = ['applicationdate', 'bcc_approval_date',
#                             'experiense_(start_date)'] if file_type == 'pre_disbursement' else ['mis_date', 'booked_on',
#                                                                                                 'loan_closed_on',
#                                                                                                 'clo_on', 'dtf', 'dtt']
#             queries = {'pre': [], 'post': [], 'anomalies_pre': [], 'anomalies_post': []}
#             current_user_id = str(get_current_user_id())
#             current_time = str(datetime.now())
#
#             for df_key, df in new_records.items():
#                 df[date_columns] = df[date_columns].apply(
#                     lambda x: x.apply(parse_excel_date) if x.name in df.columns else x)
#                 records = df.to_dict('records')
#
#                 for rec in records:
#                     if file_type == 'pre_disbursement' and str(rec['application_no']) not in ['', 'NaN', 'None']:
#
#                         app_no = str(rec['application_no'])
#
#                         # 👇 ADD THIS DUPLICATE CHECK HERE
#                         if app_no in existing_applications:
#                             application.logger.debug(f"process_upload: Skipping duplicate application_no: {app_no}")
#                             # Add to duplicates dict if you want to track them
#                             if sheet_name not in duplicates:
#                                 duplicates[sheet_name] = []
#                             duplicates[sheet_name].append(rec)
#                             continue  # Skip this record - don't insert
#
#                         cnic = str(rec.get('cnic', ''))
#                         education_level = str(rec.get('education_level', 'N/A')).strip().replace("'", "''")
#                         no_of_family_members = str(rec.get('no_of_family_members', '0'))
#
#                         if no_of_family_members.strip() == '':
#                             no_of_family_members = '0'
#
#                         tenor_of_month = str(rec.get('tenor_of_month', '0'))
#                         appraised_date = str(rec.get('appraised_date', '1900-01-01'))
#                         client_dob = format_date_for_sql(str(rec.get('client_dob', '1900-01-01')),
#                                                          rec['application_no'])
#                         co_borrower_dob = format_date_for_sql(str(rec.get('co_borrower_dob', '1900-01-01')),
#                                                               rec['application_no'])
#                         verfied_date_date = str(rec.get('verfied_date_date', '1900-01-01'))
#
#                         # Anomaly detection
#                         if cnic in existing_records.get('cnic', {}):
#                             db_rec = existing_records['cnic'][cnic]
#                             pre_disb_id = db_rec.get('pre_disb_temp_id')
#                             anomalies = []
#                             fields_to_check = [
#                                 ('Borrower_Name', 'borrower_name'),
#                                 ('Gender', 'gender'),
#                                 ('Branch_Name', 'branch_name'),
#                                 ('Student_Name', 'student_name'),
#                                 ('Student_Co_Borrower_Gender', 'student_co_borrower_gender'),
#                                 ('Collage_Univeristy', 'collage_univeristy')
#                             ]
#                             for db_field, rec_field in fields_to_check:
#                                 db_val = str(db_rec.get(db_field, '')).strip().lower()
#                                 rec_val = str(rec.get(rec_field, '')).strip().lower()
#                                 if db_val != rec_val:
#                                     anomalies.append(f"{db_field} mismatch: Sheet='{rec_val}', DB='{db_val}'")
#                             if anomalies:
#                                 details = "; ".join(anomalies)
#                                 queries['anomalies_pre'].append(
#                                     f"INSERT INTO tbl_pre_disb_anomalies (pre_disb_id, details, created_date) "
#                                     f"VALUES ({pre_disb_id}, '{details}', '{current_time}')"
#                                 )
#
#                         query = f"""
#                             INSERT INTO tbl_pre_disbursement_temp (
#                                 "Application_No", "Annual_Business_Incomes", "Annual_Disposable_Income",
#                                 "Annual_Expenses", "ApplicationDate", "Bcc_Approval_Date", "Borrower_Name",
#                                 "Branch_Area", "Branch_Name", "Business_Expense_Description",
#                                 "Business_Experiense_Since", "Business_Premises", "CNIC", "Collage_Univeristy",
#                                 "Collateral_Type", "Contact_No", "Credit_History_Ecib", "Current_Residencial",
#                                 "Dbr", "Education_Level", "Enrollment_Status", "Enterprise_Premises",
#                                 "Existing_Loan_Number", "Existing_Loan_Limit", "Existing_Loan_Status",
#                                 "Existing_Outstanding_Loan_Schedules", "Experiense_Start_Date",
#                                 "Family_Monthly_Income", "Father_Husband_Name", "Gender", "KF_Remarks",
#                                 "Loan_Amount", "Loan_Cycle", "LoanProductCode", "Loan_Status",
#                                 "Monthly_Repayment_Capacity", "Nature_Of_Business", "No_Of_Family_Members",
#                                 "Permanent_Residencial", "Premises", "Purpose_Of_Loan", "Requested_Loan_Amount",
#                                 "Residance_Type", "Student_Name", "Student_Co_Borrower_Gender",
#                                 "Student_Relation_With_Borrower", "Tenor_Of_Month", "Type_of_Business",
#                                 "annual_income", "markup_rate", "repayment_frequency", "loan_officer",
#                                 "appraised_date", "verfied_date_date", "loan_per_exposure", "client_dob",
#                                 "co_borrower_dob", "relationship_ownership", "other_bank_loans_os",
#                                 "status", "uploaded_by", "uploaded_date"
#                             ) VALUES (
#                                 '{rec.get('application_no', '')}', '{clean_numeric_value(rec.get('annual_business_incomes', '0'))}', '{clean_numeric_value(rec.get('annual_disposable_income', '0'))}',
#                                 '{rec.get('annual_expenses', '')}', '{rec.get('applicationdate', '')}', '{rec.get('bcc_approval_date', '')}',
#                                 '{sanitize_file_columns(rec.get('borrower_name', ''))}', '{rec.get('branch_area', '')}', '{rec.get('branch_name', '')}',
#                                 '{sanitize_file_columns(rec.get('business_expense_description', '').replace(',', ' and '))}', '{rec.get('business_experiense_(since)', '1900-01-01')}',
#                                 '{sanitize_file_columns(rec.get('business_premises', ''))}', '{rec.get('cnic', '')}', '{sanitize_file_columns(rec.get('collage_univeristy', ''))}',
#                                 '{sanitize_file_columns(rec.get('collateral_type', ''))}', '{rec.get('contact_no', '')}', '{rec.get('credit_history_(ecib)', '')}',
#                                 '{sanitize_file_columns(rec.get('current_residencial', ''))}', '{rec.get('dbr', '')}', '{sanitize_file_columns(education_level)}',
#                                 '{rec.get('enrollment_status', '')}', '{sanitize_file_columns(rec.get('enterprise_premises', ''))}', '{rec.get('existing_loan_number', '')}',
#                                 '{rec.get('existing_loan_limit', '')}', '{rec.get('existing_loan_status', '')}',
#                                 '{rec.get('existing_outstanding_loan_schedules', '')}', '{rec.get('experiense_(start_date)', '')}',
#                                 '{rec.get('family_monthly_income', '')}', '{sanitize_file_columns(rec.get('father_husband_name', ''))}', '{sanitize_file_columns(rec.get('gender', ''))}',
#                                 '{rec.get('kf_remarks', '')}', '{clean_numeric_value(rec.get('loan_amount', '0'))}', '{rec.get('loan_cycle', '')}',
#                                 '{rec.get('loanproductcode', '')}', '{rec.get('loan_status', '')}', '{clean_numeric_value(rec.get('monthly_repayment_capacity', ''))}',
#                                 '{sanitize_file_columns(rec.get('nature_of_business', ''))}', '{no_of_family_members}', '{sanitize_file_columns(rec.get('permanent_residencial', ''))}',
#                                 '{sanitize_file_columns(rec.get('premises', ''))}', '{sanitize_file_columns(str(rec.get('purpose_of_loan', '')))}', '{clean_numeric_value(rec.get('requested_loan_amount', '0'))}',
#                                 '{sanitize_file_columns(rec.get('residance_type', ''))}', '{sanitize_file_columns(rec.get('student_name', ''))}', '{sanitize_file_columns(rec.get('student_co_borrower_gender', ''))}',
#                                 '{rec.get('student_relation_with_borrower', '')}', '{tenor_of_month}', '{rec.get('type_of_business', '')}',
#                                 '{clean_numeric_value(rec.get('annual_income', ''))}', '{rec.get('markup_rate', '')}', '{rec.get('repayment_frequency', '')}',
#                                 '{rec.get('loan_officer', '')}', '{appraised_date}', '{verfied_date_date}',
#                                 '{clean_numeric_value(rec.get('loan_per_exposure', ''))}', '{client_dob}', '{co_borrower_dob}',
#                                 '{rec.get('relationship_ownership', '')}', '{rec.get('other_bank_loans_os', '')}', '1',
#                                 '{current_user_id}', '{current_time}'
#                             )
#                         """
#                         queries['pre'].append(query)
#                     else:
#                         customer_id = str(rec.get('customer_id', ''))
#                         pre_disb_id = None
#                         loan_no = str(rec.get('loan_no', '')).replace("'", '')
#                         loan_closed_on = str(rec.get('loan_closed_on', '1900-01-01'))
#                         booked_on = str(rec.get('booked_on', '1900-01-01'))
#                         clo_on = str(rec.get('clo_on', '1900-01-01'))
#
#                         if customer_id and customer_id in existing_records.get('pre', {}):
#                             db_rec = existing_records['pre'].get(customer_id)
#                             anomalies = []
#                             try:
#                                 pre_disb_id = db_rec.get('pre_disb_temp_id')
#                                 kft_approved_limit = int(float(str(db_rec.get('KFT_Approved_Loan_Limit', '0'))))
#                                 disbursed_amount = int(float(str(rec.get('disbursed_amount', '0'))))
#                                 if kft_approved_limit != disbursed_amount:
#                                     anomalies.append(f"KFT Approved Amount mismatch: Pre-disbursement = {kft_approved_limit}, Post-disbursement = {disbursed_amount}")
#                             except ValueError:
#                                 anomalies.append(
#                                     f"Invalid amount format: KFT_Approved_Loan_Limit = {db_rec.get('KFT_Approved_Loan_Limit', '')}, disbursed_amount = {rec.get('disbursed_amount', '')}")
#
#                             try:
#                                 booked_on_date = pd.to_datetime(str(rec.get('booked_on', '')), errors='coerce')
#                                 approval_date = pd.to_datetime(str(db_rec.get('approved_date', '')), errors='coerce')
#                                 if pd.notnull(booked_on_date) and pd.notnull(
#                                         approval_date) and booked_on_date < approval_date:
#                                     anomalies.append(
#                                         f"Booked date before approval: booked_on = {booked_on_date}, approval_date = {approval_date}")
#                             except ValueError:
#                                 anomalies.append(
#                                     f"Invalid date format: booked_on = {rec.get('booked_on', '')}, approval_date = {db_rec.get('approved_date', '')}")
#
#                             if anomalies:
#                                 details = "; ".join(anomalies)
#                                 queries['anomalies_post'].append(
#                                     f"INSERT INTO tbl_post_disbursement_anomalies (pre_disb_id, application_no, details, created_date) "
#                                     f"VALUES ({(pre_disb_id or 'NULL')}, '{customer_id}', '{details}', '{current_time}')"
#                                 )
#
#                         if customer_id in existing_records.get('post', {}):
#                             prev_rec = existing_records['post'][customer_id]
#                             anomalies = []
#                             fields_to_check = [
#                                 ('branch_name', 'branch_name'),
#                                 ('gender', 'gender'),
#                                 ('loan_no', 'loan_no'),
#                                 ('product_code', 'product_code'),
#                                 ('booked_on', 'booked_on'),
#                                 ('repayment_type', 'repayment_type')
#                             ]
#                             for db_field, rec_field in fields_to_check:
#                                 prev_val = str(prev_rec.get(db_field, '')).strip().lower()
#                                 curr_val = str(rec.get(rec_field, '')).strip().lower()
#                                 if prev_val != curr_val:
#                                     anomalies.append(
#                                         f"{db_field} mismatch: Previous = {prev_val}, Current = {curr_val}")
#                             try:
#                                 curr_outstanding = int(float(str(rec.get('principal_outstanding', '0'))))
#                                 prev_outstanding = int(float(str(prev_rec.get('principal_outstanding', '0'))))
#                                 curr_disbursed = int(float(str(rec.get('disbursed_amount', '0'))))
#                                 if curr_outstanding > prev_outstanding:
#                                     anomalies.append(
#                                         f"Outstanding amount increased: Previous = {prev_outstanding}, Current = {curr_outstanding}")
#                                 if curr_outstanding > curr_disbursed:
#                                     anomalies.append(
#                                         f"Outstanding exceeds disbursed: Outstanding = {curr_outstanding}, Disbursed = {curr_disbursed}")
#                             except ValueError:
#                                 anomalies.append(
#                                     f"Invalid amount format: principal_outstanding = {rec.get('principal_outstanding', '')}, disbursed_amount = {rec.get('disbursed_amount', '')}")
#                             if anomalies:
#                                 details = "; ".join(anomalies)
#                                 queries['anomalies_post'].append(
#                                     f"INSERT INTO tbl_post_disbursement_anomalies (pre_disb_id, application_no, details, created_date) "
#                                     f"VALUES ({db_rec.get('pre_disb_temp_id', 'NULL') if 'pre' in existing_records else 'NULL'}, '{customer_id}', '{details}', '{current_time}')"
#                                 )
#
#                         if loan_no:
#                             query = f"""
#                                 INSERT INTO tbl_post_disbursement (
#                                     mis_date, area, sector_code, branch_code, branch_name, cnic, gender,
#                                     address, mobile_no, loan_title, rt, loan_no, product_code, booked_on,
#                                     disbursed_amount, repayment_type, sector, purpose, loan_status, loan_closed_on,
#                                     act_clo, colloanno, coll_id, lrno, collat, coll_stat, collateral_value,
#                                     collateral_title, overdue_days, principal_outstanding, total_outstand_other,
#                                     markup_outstanding, lo, fc_los, dtf, dtt, customer_id, application_num,
#                                     clo_on, liab_id, pool_id, account_number, created_by, created_date
#                                 ) VALUES (
#                                     '{input_timestamp}', '{rec.get('area', '')}', '{rec.get('sector_code', '')}',
#                                     '{rec.get('branch_code', '')}', '{rec.get('branch_name', '')}', '{rec.get('cnic', '')}',
#                                     '{rec.get('gender', '')}', '{sanitize_file_columns(str(rec.get('address', '')))}', '{rec.get('mobile_no', '')}',
#                                     '{sanitize_file_columns(rec.get('loan_title', ''))}', '{rec.get('rt', '')}', '{loan_no}',
#                                     '{rec.get('product_code', '')}', '{booked_on}',
#                                     '{rec.get('disbursed_amount', '')}', '{rec.get('repayment_type', '')}',
#                                     '{rec.get('sector', '')}', '{rec.get('purpose', '')}', '{rec.get('loan_status', '')}',
#                                     '{loan_closed_on}', '{rec.get('act_clo', '')}',
#                                     '{rec.get('colloanno', '')}', '{rec.get('coll_id', '')}', '{rec.get('lrno', '')}',
#                                     '{rec.get('collat', '')}', '{rec.get('coll_stat', '')}', '{rec.get('collateral_value', '')}',
#                                     '{rec.get('collateral_title', '')}', '{rec.get('overdue_days', '')}',
#                                     '{rec.get('principal_outstanding', '')}', '{rec.get('total_outstand_other', '')}',
#                                     '{rec.get('markup_outstanding', '')}', '{rec.get('lo', '')}', '{rec.get('fc_los', '')}',
#                                     '{rec.get('dtf', '')}', '{rec.get('dtt', '')}', '{rec.get('customer_id', '')}',
#                                     '{rec.get('application_num', '')}', '{clo_on}',
#                                     '{rec.get('liab_id', '')}', '{rec.get('pool_id', '')}', '{rec.get('account_number', '')}',
#                                     '{current_user_id}', '{current_time}'
#                                 )
#                             """
#                             queries['post'].append(query)
#
#             # Execute all queries in batches
#             for query_type, query_list in queries.items():
#                 if query_list:
#                     batch_query = ";".join(query_list)
#                     execute_command(batch_query, is_print=False)
#                     application.logger.debug(
#                         f"process_upload: Executed batch {query_type} query for {len(query_list)} records")
#
#         if file_type == 'pre_disbursement' and any(len(duplicates[sheet]) > 0 for sheet in duplicates):
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             summary_filename = f"Summary_of_duplicates_discrepancies_{timestamp}.xlsx"
#             summary_path = os.path.join(current_app.config['UPLOAD_FOLDER'], summary_filename)
#             with pd.ExcelWriter(summary_path) as writer:
#                 for sheet_name, duplicate_rows in duplicates.items():
#                     if len(duplicate_rows) > 0:
#                         # Convert list of dicts to DataFrame
#                         duplicate_df = pd.DataFrame(duplicate_rows)
#                         duplicate_df.to_excel(writer, sheet_name=f"Duplicate_{sheet_name}", index=False)
#
#         return True, {
#             'duplicates': {k: len(v) for k, v in duplicates.items()},
#             'new_records': {k: len(v) for k, v in new_records.items()},
#             'summary_path': summary_path
#         }
#     except Exception as e:
#         application.logger.error(f"process_upload: Error processing files: {str(e)}")
#         return False, f"Error processing file: {str(e)}"


def process_upload():
    application.logger.debug("process_upload: Entering function")
    file_type = session.get('file_type')
    category = session.get('category')
    filepaths = session['current_files']
    input_timestamp = session.get('input_timestamp') or '1900-01-01'

    duplicates = {}
    new_records = {}
    summary_path = None
    anomaly_applications = set()  # Track application numbers with anomalies

    # Define headers and mappings
    pre_headers = [
        'annual_business_incomes', 'annual_disposable_income', 'annual_expenses', 'appraised_date',
        'application_no', 'applicationdate', 'bcc_approval_date', 'borrower_name', 'branch_area',
        'branch_name', 'business_expense_description', 'client_dob', 'co_borrower_dob',
        'collage_univeristy', 'collateral_type', 'contact_no', 'credit_history_(ecib)',
        'current_residencial', 'dbr', 'education_level', 'enrollment_status', 'enterprise_premises',
        'experiense_(start_date)', 'family_monthly_income', 'father_husband_name', 'gender',
        'loan_amount', 'loan_cycle', 'loan_officer', 'loan_per_exposure', 'loan_product_code',
        'loan_status', 'markup_rate', 'monthly_repayment_capacity', 'nature_of_business',
        'no_of_family_members', 'other_bank_loans_os', 'permanent_residencial', 'purpose_of_loan',
        'relationship_ownership', 'repayment_frequency', 'requested_loan_amount', 'residance_type',
        'student_co_borrower_gender', 'student_name', 'student_relation_with_borrower',
        'tenor_of_month', 'verfied_date_date'
    ]
    post_headers = [
        'mis_date', 'area', 'sector_code', 'branch_code', 'branch_name', 'cnic', 'gender',
        'address', 'mobile_no', 'loan_title', 'rt', 'loan_no', 'product_code', 'booked_on',
        'disbursed_amount', 'repayment_type', 'sector', 'purpose', 'loan_status', 'loan_closed_on',
        'act_clo', 'colloanno', 'coll_id', 'lrno', 'collat', 'coll_stat', 'collateral_value',
        'collateral_title', 'overdue_days', 'principal_outstanding', 'total_outstand_other',
        'markup_outstanding', 'lo', 'fc_los', 'dtf', 'dtt', 'customer_id', 'application_num',
        'clo_on', 'liab_id', 'pool_id', 'account_number'
    ]
    post_to_los_mapping = {
        'branch_code': 'branch_code', 'branch_name': 'branch_name', 'cnic': 'cnic', 'gender': 'gender',
        'address': 'address', 'mobile_no': 'mobile_number', 'loan_no': 'loan_number',
        'loan_title': 'loan_title', 'product_code': 'product_code', 'booked_on': 'loancreationdate',
        'disbursed_amount': 'disb_amt', 'principal_outstanding': 'os_p',
        'markup_outstanding': 'total_outstand_markup', 'repayment_type': 'loanrepaymenttype',
        'sector': 'sector', 'purpose': 'purpose', 'loan_status': 'loanstatus',
        'overdue_days': 'od_days', 'loan_closed_on': 'closed_on_date', 'collateral_title': 'collateraltitle'
    }
    post_to_mis_mapping = {
        'branch_code': 'bcode', 'branch_name': 'branch_name', 'cnic': 'customer_id', 'gender': 'gender',
        'address': 'address', 'mobile_no': 'mobile', 'loan_no': 'loanno', 'loan_title': 'loantitle',
        'product_code': 'product_code', 'booked_on': 'loancreationdate', 'disbursed_amount': 'disbursedamt',
        'principal_outstanding': 'total_outstand_principal', 'markup_outstanding': 'total_outstand_markup',
        'repayment_type': 'loanrepaymenttype', 'sector': 'sector', 'purpose': 'purpose',
        'loan_status': 'loanstatus', 'overdue_days': 'od_days', 'loan_closed_on': 'ln_clo_dt',
        'collateral_title': 'collateraltitle'
    }
    los_to_mis_mapping = {'collat': 'collateral_type'}

    try:
        # Fetch existing records once
        existing_records = {}
        existing_applications = set()

        if file_type == 'pre_disbursement':
            records = fetch_records(
                'SELECT "pre_disb_temp_id", "Application_No", "status", "CNIC", "Borrower_Name", "Gender", "Branch_Name", '
                '"Student_Name", "Student_Co_Borrower_Gender", "Collage_Univeristy", '
                'KFT_Approved_Loan_Limit, "approved_date" FROM tbl_pre_disbursement_temp')
            existing_records['pre'] = {str(row['Application_No']): row for row in records}
            existing_records['cnic'] = {str(row['CNIC']): row for row in records if row['CNIC']}
            existing_applications = set(existing_records['pre'].keys())
            application.logger.debug(
                f"process_upload: Loaded {len(existing_applications)} existing application numbers")
        else:
            records = fetch_records('SELECT customer_id, branch_name, gender, loan_no, product_code, booked_on, '
                                    'repayment_type, principal_outstanding, disbursed_amount FROM tbl_post_disbursement '
                                    f'WHERE mis_date < \'{input_timestamp}\'')
            existing_records['post'] = {str(row['customer_id']): row for row in records if row['customer_id']}

        all_dfs = []
        for file_idx, filepath in enumerate(filepaths):
            xl = pd.ExcelFile(filepath)
            sheet_names = [o for o in xl.sheet_names if o != 'GVMetadata']
            for sheet_name in sheet_names:
                df = pd.read_excel(filepath, sheet_name=sheet_name, dtype=str).fillna('')
                df.columns = [col.strip().lower().replace('/', '_').replace(' ', '_') for col in df.columns]

                if df.columns.duplicated().any():
                    duplicates_list = df.columns[df.columns.duplicated()].tolist()
                    application.logger.error(
                        f"process_upload: Duplicate columns in sheet '{sheet_name}': {duplicates_list}")
                    raise ValueError(f"Duplicate column names found in sheet {sheet_name}: {duplicates_list}")

                expected_headers = pre_headers if file_type == 'pre_disbursement' else post_headers
                table_name = 'tbl_pre_disbursement_temp' if file_type == 'pre_disbursement' else 'tbl_post_disbursement'
                key_column = 'application_no' if file_type == 'pre_disbursement' else 'loan_no'

                if file_type == 'post_disbursement':
                    mapping = post_to_los_mapping if category == 'los' or (
                                category == 'both' and file_idx == 0) else post_to_mis_mapping
                    inverse_mapping = {v: k for k, v in mapping.items()}

                    if df.columns.duplicated().any():
                        duplicates_list = df.columns[df.columns.duplicated()].tolist()
                        application.logger.error(
                            f"process_upload: Duplicate columns in sheet '{sheet_name}': {duplicates_list}")
                        raise ValueError(f"Duplicate column names found in sheet {sheet_name}: {duplicates_list}")

                    rename_dict = {k: v for k, v in inverse_mapping.items() if k in df.columns}
                    df = df.rename(columns=rename_dict)

                    if category == 'both' and file_idx == 0:
                        los_rename_dict = {k: v for k, v in los_to_mis_mapping.items() if k in df.columns}
                        df = df.rename(columns=los_rename_dict)

                missing_headers = [h for h in expected_headers if h not in df.columns]
                if missing_headers:
                    application.logger.warning(
                        f"process_upload: Missing headers in sheet '{sheet_name}': {missing_headers}")
                    flash(f"Sheet '{sheet_name}' is missing headers: {', '.join(missing_headers)}. Adding as blanks.",
                          'warning')
                    df = df.reindex(columns=df.columns.tolist() + missing_headers, fill_value='')

                if key_column not in df.columns:
                    application.logger.error(
                        f"process_upload: Key column '{key_column}' not found in sheet '{sheet_name}'")
                    raise ValueError(f"Key column '{key_column}' not found in sheet {sheet_name}")

                duplicates[sheet_name] = []
                new_records[sheet_name] = df
                all_dfs.append(df)

        # Merge datasets for 'both'
        if file_type == 'post_disbursement' and category == 'both' and all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            new_records = {f'combined_{category}': combined_df}
        else:
            new_records = {k: v for k, v in new_records.items() if not v.empty}

        if new_records:
            date_columns = ['applicationdate', 'bcc_approval_date',
                            'experiense_(start_date)'] if file_type == 'pre_disbursement' else ['mis_date', 'booked_on',
                                                                                                'loan_closed_on',
                                                                                                'clo_on', 'dtf', 'dtt']
            queries = {'pre': [], 'post': [], 'anomalies_pre': [], 'anomalies_post': []}
            current_user_id = str(get_current_user_id())
            current_time = str(datetime.now())

            for df_key, df in new_records.items():
                df[date_columns] = df[date_columns].apply(
                    lambda x: x.apply(parse_excel_date) if x.name in df.columns else x)
                records = df.to_dict('records')

                for rec in records:
                    if file_type == 'pre_disbursement' and str(rec['application_no']) not in ['', 'NaN', 'None']:

                        app_no = str(rec['application_no'])

                        # Duplicate check
                        if app_no in existing_applications:
                            application.logger.debug(f"process_upload: Skipping duplicate application_no: {app_no}")
                            if sheet_name not in duplicates:
                                duplicates[sheet_name] = []
                            duplicates[sheet_name].append(rec)
                            continue

                        cnic = str(rec.get('cnic', ''))
                        education_level = str(rec.get('education_level', 'N/A')).strip().replace("'", "''")
                        no_of_family_members = str(rec.get('no_of_family_members', '0'))

                        if no_of_family_members.strip() == '':
                            no_of_family_members = '0'

                        tenor_of_month = str(rec.get('tenor_of_month', '0'))
                        appraised_date = str(rec.get('appraised_date', '1900-01-01'))
                        client_dob = format_date_for_sql(str(rec.get('client_dob', '1900-01-01')),
                                                         rec['application_no'])
                        co_borrower_dob = format_date_for_sql(str(rec.get('co_borrower_dob', '1900-01-01')),
                                                              rec['application_no'])
                        verfied_date_date = str(rec.get('verfied_date_date', '1900-01-01'))
                        loan_per_exposure = str(rec.get('loan_per_exposure', '0')).strip()

                        if loan_per_exposure in ['', 'None']:
                            loan_per_exposure = '0'

                        # print('loan_per_exposure:- ', loan_per_exposure, ' type of loan_per_exposure ', type(loan_per_exposure))

                        # Anomaly detection for pre-disbursement
                        if cnic in existing_records.get('cnic', {}):
                            db_rec = existing_records['cnic'][cnic]
                            pre_disb_id = db_rec.get('pre_disb_temp_id')
                            dub_app_no = db_rec.get('Application_No')

                            anomalies = []
                            fields_to_check = [
                                ('Borrower_Name', 'borrower_name'),
                                ('Gender', 'gender'),
                                ('Branch_Name', 'branch_name'),
                                ('Student_Name', 'student_name'),
                                ('Student_Co_Borrower_Gender', 'student_co_borrower_gender'),
                                ('Collage_Univeristy', 'collage_univeristy')
                            ]
                            for db_field, rec_field in fields_to_check:
                                db_val = str(db_rec.get(db_field, '')).strip().lower()
                                rec_val = str(rec.get(rec_field, '')).strip().lower()

                                message = f"New application no is: {str(app_no)} \n"

                                if db_val != rec_val:
                                    message += f"{db_field} mismatch: Current= {rec_val}, Previous={db_val} \n"
                                    anomalies.append(message)

                            if anomalies:
                                details = "; ".join(anomalies)
                                queries['anomalies_pre'].append(
                                    f"""
                                        INSERT INTO tbl_pre_disb_anomalies (pre_disb_id, details, created_date)
                                        VALUES ({pre_disb_id}, {escape_sql_string(details)}, '{current_time}')
                                    """

                                )
                                # Add to anomaly applications set
                                anomaly_applications.add(str(dub_app_no))

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
                                '{rec.get('application_no', '')}', '{clean_numeric_value(rec.get('annual_business_incomes', '0'))}', '{clean_numeric_value(rec.get('annual_disposable_income', '0'))}',
                                '{rec.get('annual_expenses', '')}', '{rec.get('applicationdate', '')}', '{rec.get('bcc_approval_date', '')}',
                                '{sanitize_file_columns(rec.get('borrower_name', ''))}', '{rec.get('branch_area', '')}', '{rec.get('branch_name', '')}',
                                '{sanitize_file_columns(rec.get('business_expense_description', '').replace(',', ' and '))}', '{rec.get('business_experiense_(since)', '1900-01-01')}',
                                '{sanitize_file_columns(rec.get('business_premises', ''))}', '{rec.get('cnic', '')}', '{sanitize_file_columns(rec.get('collage_univeristy', ''))}',
                                '{sanitize_file_columns(rec.get('collateral_type', ''))}', '{rec.get('contact_no', '')}', '{rec.get('credit_history_(ecib)', '')}',
                                '{sanitize_file_columns(rec.get('current_residencial', ''))}', '{rec.get('dbr', '')}', '{sanitize_file_columns(education_level)}',
                                '{rec.get('enrollment_status', '')}', '{sanitize_file_columns(rec.get('enterprise_premises', ''))}', '{rec.get('existing_loan_number', '')}',
                                '{rec.get('existing_loan_limit', '')}', '{rec.get('existing_loan_status', '')}',
                                '{rec.get('existing_outstanding_loan_schedules', '')}', '{rec.get('experiense_(start_date)', '')}',
                                '{rec.get('family_monthly_income', '')}', '{sanitize_file_columns(rec.get('father_husband_name', ''))}', '{sanitize_file_columns(rec.get('gender', ''))}',
                                '{rec.get('kf_remarks', '')}', '{clean_numeric_value(rec.get('loan_amount', '0'))}', '{rec.get('loan_cycle', '')}',
                                '{rec.get('loanproductcode', '')}', '{rec.get('loan_status', '')}', '{clean_numeric_value(rec.get('monthly_repayment_capacity', ''))}',
                                '{sanitize_file_columns(rec.get('nature_of_business', ''))}', '{no_of_family_members}', '{sanitize_file_columns(rec.get('permanent_residencial', ''))}',
                                '{sanitize_file_columns(rec.get('premises', ''))}', '{sanitize_file_columns(str(rec.get('purpose_of_loan', '')))}', '{clean_numeric_value(rec.get('requested_loan_amount', '0'))}',
                                '{sanitize_file_columns(rec.get('residance_type', ''))}', '{sanitize_file_columns(rec.get('student_name', ''))}', '{sanitize_file_columns(rec.get('student_co_borrower_gender', ''))}',
                                '{rec.get('student_relation_with_borrower', '')}', '{tenor_of_month}', '{rec.get('type_of_business', '')}',
                                '{clean_numeric_value(rec.get('annual_income', ''))}', '{rec.get('markup_rate', '')}', '{rec.get('repayment_frequency', '')}',
                                '{rec.get('loan_officer', '')}', '{appraised_date}', '{verfied_date_date}',
                                '{clean_numeric_value(loan_per_exposure)}', '{client_dob}', '{co_borrower_dob}',
                                '{rec.get('relationship_ownership', '')}', '{rec.get('other_bank_loans_os', '')}', '1',
                                '{current_user_id}', '{current_time}'
                            )
                        """
                        queries['pre'].append(query)

                    else:  # Post disbursement
                        customer_id = str(rec.get('customer_id', ''))
                        pre_disb_id = None
                        loan_no = str(rec.get('loan_no', '')).replace("'", '')
                        loan_closed_on = str(rec.get('loan_closed_on', '1900-01-01'))
                        booked_on = str(rec.get('booked_on', '1900-01-01'))
                        clo_on = str(rec.get('clo_on', '1900-01-01'))

                        # Anomaly detection - comparing with pre-disbursement data
                        if customer_id and customer_id in existing_records.get('pre', {}):
                            db_rec = existing_records['pre'].get(customer_id)
                            anomalies = []
                            try:
                                pre_disb_id = db_rec.get('pre_disb_temp_id')
                                kft_approved_limit = int(float(str(db_rec.get('KFT_Approved_Loan_Limit', '0'))))
                                disbursed_amount = int(float(str(rec.get('disbursed_amount', '0'))))
                                if kft_approved_limit != disbursed_amount:
                                    anomalies.append(
                                        f"KFT Approved Amount mismatch: Pre-disbursement = {kft_approved_limit}, Post-disbursement = {disbursed_amount}")
                            except ValueError:
                                anomalies.append(
                                    f"Invalid amount format: KFT_Approved_Loan_Limit = {db_rec.get('KFT_Approved_Loan_Limit', '')}, disbursed_amount = {rec.get('disbursed_amount', '')}")

                            try:
                                booked_on_date = pd.to_datetime(str(rec.get('booked_on', '')), errors='coerce')
                                approval_date = pd.to_datetime(str(db_rec.get('approved_date', '')), errors='coerce')
                                if pd.notnull(booked_on_date) and pd.notnull(
                                        approval_date) and booked_on_date < approval_date:
                                    anomalies.append(
                                        f"Booked date before approval: booked_on = {booked_on_date}, approval_date = {approval_date}")
                            except ValueError:
                                anomalies.append(
                                    f"Invalid date format: booked_on = {rec.get('booked_on', '')}, approval_date = {db_rec.get('approved_date', '')}")

                            if anomalies:
                                details = "; ".join(anomalies)
                                queries['anomalies_post'].append(
                                    f"INSERT INTO tbl_post_disbursement_anomalies (pre_disb_id, application_no, details, created_date) "
                                    f"VALUES ({(pre_disb_id or 'NULL')}, '{customer_id}', {escape_sql_string(details)}, '{current_time}')"
                                )
                                # Add to anomaly applications set
                                anomaly_applications.add(str(customer_id))

                        # Anomaly detection - comparing with existing post-disbursement records
                        if customer_id in existing_records.get('post', {}):
                            prev_rec = existing_records['post'][customer_id]
                            anomalies = []
                            fields_to_check = [
                                ('branch_name', 'branch_name'),
                                ('gender', 'gender'),
                                ('loan_no', 'loan_no'),
                                ('product_code', 'product_code'),
                                ('booked_on', 'booked_on'),
                                ('repayment_type', 'repayment_type')
                            ]
                            for db_field, rec_field in fields_to_check:
                                prev_val = str(prev_rec.get(db_field, '')).strip().lower()
                                curr_val = str(rec.get(rec_field, '')).strip().lower()
                                if prev_val != curr_val:
                                    anomalies.append(
                                        f"{db_field} mismatch: Previous = {prev_val}, Current = {curr_val}")

                            try:
                                curr_outstanding = int(float(str(rec.get('principal_outstanding', '0'))))
                                prev_outstanding = int(float(str(prev_rec.get('principal_outstanding', '0'))))
                                curr_disbursed = int(float(str(rec.get('disbursed_amount', '0'))))
                                if curr_outstanding > prev_outstanding:
                                    anomalies.append(
                                        f"Outstanding amount increased: Previous = {prev_outstanding}, Current = {curr_outstanding}")
                                if curr_outstanding > curr_disbursed:
                                    anomalies.append(
                                        f"Outstanding exceeds disbursed: Outstanding = {curr_outstanding}, Disbursed = {curr_disbursed}")
                            except ValueError:
                                anomalies.append(
                                    f"Invalid amount format: principal_outstanding = {rec.get('principal_outstanding', '')}, disbursed_amount = {rec.get('disbursed_amount', '')}")

                            if anomalies:
                                details = "; ".join(anomalies)
                                queries['anomalies_post'].append(
                                    f"INSERT INTO tbl_post_disbursement_anomalies (pre_disb_id, application_no, details, created_date) "
                                    f"VALUES ({db_rec.get('pre_disb_temp_id', 'NULL') if 'pre' in existing_records else 'NULL'}, '{customer_id}', '{details}', '{current_time}')"
                                )
                                # Add to anomaly applications set
                                anomaly_applications.add(str(customer_id))

                        if loan_no:
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
                                    '{input_timestamp}', '{rec.get('area', '')}', '{rec.get('sector_code', '')}',
                                    '{rec.get('branch_code', '')}', '{rec.get('branch_name', '')}', '{rec.get('cnic', '')}',
                                    '{rec.get('gender', '')}', '{sanitize_file_columns(str(rec.get('address', '')))}', '{rec.get('mobile_no', '')}',
                                    '{sanitize_file_columns(rec.get('loan_title', ''))}', '{rec.get('rt', '')}', '{loan_no}',
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
                                    '{current_user_id}', '{current_time}'
                                )
                            """
                            queries['post'].append(query)

            # Execute all queries in batches
            for query_type, query_list in queries.items():
                if query_list:
                    batch_query = ";".join(query_list)
                    execute_command(batch_query, is_print=False)
                    application.logger.debug(
                        f"process_upload: Executed batch {query_type} query for {len(query_list)} records")

        # Generate duplicate summary Excel if needed
        if file_type == 'pre_disbursement' and any(len(duplicates[sheet]) > 0 for sheet in duplicates):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_filename = f"Summary_of_duplicates_discrepancies_{timestamp}.xlsx"
            summary_path = os.path.join(current_app.config['UPLOAD_FOLDER'], summary_filename)
            with pd.ExcelWriter(summary_path) as writer:
                for sheet_name, duplicate_rows in duplicates.items():
                    if len(duplicate_rows) > 0:
                        duplicate_df = pd.DataFrame(duplicate_rows)
                        duplicate_df.to_excel(writer, sheet_name=f"Duplicate_{sheet_name}", index=False)

        # Generate anomalies PDF if any anomalies were detected
        anomalies_report_path = None
        if anomaly_applications:
            try:
                anomalies_report_path = generate_anomalies_html(list(anomaly_applications))
                if anomalies_report_path:
                    application.logger.info(
                        f"process_upload: Generated anomalies report for {len(anomaly_applications)} applications")
            except Exception as e:
                application.logger.error(f"process_upload: Failed to generate anomalies PDF: {str(e)}")

        return True, {
            'duplicates': {k: len(v) for k, v in duplicates.items()},
            'new_records': {k: len(v) for k, v in new_records.items()},
            'summary_path': summary_path,
            'anomalies_report_path': anomalies_report_path,
            'anomalies_detected': len(anomaly_applications) > 0
        }

    except Exception as e:
        application.logger.error(f"process_upload: Error processing files: {str(e)}")
        return False, f"Error processing file: {str(e)}"


def parse_excel_date(date_str):
    if pd.isnull(date_str) or not date_str or str(date_str).strip() in ['', 'NaN', 'None']:
        return '1900-01-01'
    if isinstance(date_str, datetime):
        return date_str.date().isoformat()
    try:
        return parse(str(date_str).strip()).date().isoformat()
    except Exception:
        application.logger.warning(f"parse_excel_date: Failed to parse date '{date_str}'")
        return '1900-01-01'


@application.route('/download_summary')
def download_summary():
    application.logger.debug("download_summary: Entering function")
    try:
        if 'summary_file' not in session or not session['summary_file']:
            application.logger.warning("download_summary: No summary file in session")
            flash('No summary file available for download', 'danger')
            return redirect(url_for('manage_file'))

        file_path = session['summary_file']
        if not os.path.exists(file_path):
            application.logger.warning("download_summary: Summary file does not exist")
            flash('Summary file no longer exists', 'danger')
            return redirect(url_for('manage_file'))

        if not file_path.startswith(application.config['UPLOAD_FOLDER']):
            application.logger.error("download_summary: File path not in UPLOAD_FOLDER")
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
                    application.logger.debug("download_summary: Cleaned up summary file and session")
            except Exception as e:
                application.logger.error(f"download_summary: Error cleaning up summary file: {str(e)}")
            return response

        return send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            conditional=True
        )
    except Exception as e:
        application.logger.error(f"download_summary: Error downloading summary: {str(e)}")
        flash('Could not prepare the download. Please try again.', 'danger')
        return redirect(url_for('manage_file'))


@application.route('/download_anomalies_report')
def download_anomalies_report():
    application.logger.debug("download_anomalies_report: Entering function")
    try:
        if 'anomalies_report' not in session or not session['anomalies_report']:
            application.logger.warning("download_anomalies_report: No anomalies report in session")
            flash('No anomalies report available for download', 'danger')
            return redirect(url_for('manage_file'))

        file_path = session['anomalies_report']
        if not os.path.exists(file_path):
            application.logger.warning("download_anomalies_report: Report file does not exist")
            flash('Anomalies report no longer exists', 'danger')
            return redirect(url_for('manage_file'))

        if not file_path.startswith(application.config['UPLOAD_FOLDER']):
            application.logger.error("download_anomalies_report: File path not in UPLOAD_FOLDER")
            abort(403, description="Access denied")

        timestamp = datetime.now().strftime("%Y-%m-%d")
        download_name = f"Anomalies_Report_{timestamp}.html"

        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(file_path):
                    safe_remove(file_path)
                    session.pop('anomalies_report', None)
                    application.logger.debug("download_anomalies_report: Cleaned up report file and session")
            except Exception as e:
                application.logger.error(f"download_anomalies_report: Error cleaning up report file: {str(e)}")
            return response

        return send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='text/html',
            conditional=True
        )
    except Exception as e:
        application.logger.error(f"download_anomalies_report: Error downloading report: {str(e)}")
        flash('Could not prepare the download. Please try again.', 'danger')
        return redirect(url_for('manage_file'))


def sanitize_file_columns(address: str) -> str:
    if not address or not isinstance(address, str):
        return ''
    cleaned_address = re.sub(r'[;\'"\--]', '', address.strip())
    if cleaned_address != address.strip():
        application.logger.debug(f"sanitize_file_columns: Cleaned address from '{address}' to '{cleaned_address}'")
    return cleaned_address


def format_date_for_sql(date_str: str, application_no: str = None) -> str:
    if not date_str or date_str.strip() == '' or date_str in {'0000-00-00', '1974-00-00', '00-00-0000', '0/0/0000',
                                                              '0-0-0'}:
        flash_msg = f"Application {application_no}: Invalid or missing date '{date_str}'. Date will be saved as NULL."
        flash(flash_msg, "danger")
        return '1900-01-01'
    try:
        return parse(date_str.strip()).date().isoformat()
    except Exception:
        flash_msg = f"Application {application_no}: Unrecognized date format '{date_str}'. Date will be saved as NULL."
        flash(flash_msg, "danger")
        return '1900-01-01'


def clean_numeric_value(value):
    """
    Clean numeric strings by removing commas and converting to proper format.
    Returns empty string if value is invalid/empty.
    """
    if pd.isna(value) or not value or str(value).strip() in ['', 'NaN', 'None']:
        return ''

    # Convert to string and clean
    str_value = str(value).strip()

    # Remove commas and any whitespace
    str_value = str_value.replace(',', '').replace(' ', '')

    # Handle empty after cleaning
    if not str_value:
        return ''

    # Validate it's a number
    try:
        float(str_value)  # Just to validate
        return str_value
    except ValueError:
        application.logger.warning(f"clean_numeric_value: Invalid number format '{value}'")
        return '0'  # Return '0' as fallback


def pg_escape(s):
    return str(s).replace("'", "''") if s is not None else "NULL"