from imports import *
from application import application
from pdf_helper import *
from App_File_Uploading_Validation import parse_excel_date, sanitize_file_columns, clean_numeric_value, format_date_for_sql
import tempfile
import shutil

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def log_job_start():

    try:
        query = """
                INSERT INTO monitoring.pre_disb_email_processor_runs (
                    job_name, started_at, status
                ) VALUES ('pre-disb-email-processor', NOW(), 'running')
            """
        inserted_record_id = execute_command(query)

        return inserted_record_id

    except Exception as e:
        logger.error(f'cron_pre_disb_email_processor -> log_job_start -> exception: {str(e)}')
        print()


def log_job_end(job_id, status, duration_sec=None, emails_found=0, files_processed=0,
                new_records_count=0, duplicates_count=0, anomalies_count=0,
                summary_path=None, anomalies_path=None, error_msg=None, error_trace=None):

    if job_id is None:
        logger.warning("No job_id — skipping DB log")
        return

    try:
        # Format string values with quotes, handle None as NULL
        status_str = f"'{status}'" if status is not None else "NULL"
        duration_str = str(duration_sec) if duration_sec is not None else "NULL"
        emails_found_str = str(emails_found)
        files_processed_str = str(files_processed)
        new_records_str = str(new_records_count)
        duplicates_str = str(duplicates_count)
        anomalies_str = str(anomalies_count)
        summary_path_str = f"'{summary_path}'" if summary_path is not None else "NULL"
        anomalies_path_str = f"'{anomalies_path}'" if anomalies_path is not None else "NULL"
        error_msg_str = f"""'{sanitize_file_columns(error_msg)}'""" if error_msg is not None else "NULL"
        error_trace_str = f"""'{sanitize_file_columns(error_trace)}'""" if error_trace is not None else "NULL"

        query = f"""
            UPDATE monitoring.pre_disb_email_processor_runs
            SET 
                finished_at = NOW(),
                status = {status_str},
                duration_seconds = {duration_str},
                emails_found = {emails_found_str},
                files_processed = {files_processed_str},
                new_records_count = {new_records_str},
                duplicates_count = {duplicates_str},
                anomalies_count = {anomalies_str},
                summary_path = {summary_path_str},
                anomalies_path = {anomalies_path_str},
                error_message = {error_msg_str},
                error_trace = {error_trace_str},
                updated_at = NOW()
            WHERE id = {job_id}
        """
        execute_command(query)
    except Exception as e:
        logger.error(f"Failed to log job end: {e}")


# ── Helper to decode subject ──
def decode_subject(subject):
    decoded, encoding = decode_header(subject)[0]
    if isinstance(decoded, bytes):
        return decoded.decode(encoding or 'utf-8', errors='ignore')
    return decoded


# ── Extract Excel attachments ──
def get_excel_attachments(msg):
    excels = []
    for part in msg.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue

        filename = part.get_filename()
        if filename:
            filename = decode_header(filename)[0][0]
            if isinstance(filename, bytes):
                filename = filename.decode(errors='ignore')
            if filename.lower().endswith(('.xlsx', '.xls')):
                payload = part.get_payload(decode=True)
                if payload:
                    excels.append((filename, BytesIO(payload)))
                    logger.info(f"Found Excel attachment: {filename}")
    return excels


def process_pre_disbursement_files(
        filepaths: list[str],
        input_timestamp: str | None = None,
        uploaded_by_user_id: str | None = None,
        generate_reports: bool = True
) -> dict:
    """
    Process one or more Excel files containing pre-disbursement data.

    This function is meant to be called both from web upload and from cron/email automation.

    Returns dict with processing results (suitable for logging / DB tracking).
    """
    if not filepaths:
        return {"success": False, "error": "No files provided"}

    input_timestamp = input_timestamp or datetime.now().strftime("%Y-%m-%d")
    uploaded_by_user_id = uploaded_by_user_id or "0"  # fallback – better to enforce in production
    current_time = datetime.now().isoformat()

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

    # ── Results containers ──
    duplicates = {}  # sheet_name → list of duplicate rows
    new_records_count = 0
    duplicate_count = 0
    anomaly_applications = set()
    summary_excel_path = None
    anomalies_report_path = None

    # ── Load existing data once ──
    existing_records = fetch_records(
        """
        SELECT 
            "pre_disb_temp_id", 
            "Application_No", 
            "status", 
            "CNIC", 
            "Borrower_Name", 
            "Gender", 
            "Branch_Name", 
            "Student_Name", 
            "Student_Co_Borrower_Gender", 
            "Collage_Univeristy",
            KFT_Approved_Loan_Limit,
            "approved_date"
        FROM tbl_pre_disbursement_temp
        """
    )

    existing_by_app_no = {str(r["Application_No"]): r for r in existing_records}
    existing_by_cnic = {str(r["CNIC"]): r for r in existing_records if r.get("CNIC")}

    existing_app_numbers = set(existing_by_app_no.keys())

    # ── Process each file ──
    all_sheets_data = {}

    for filepath in filepaths:
        if not os.path.exists(filepath):
            application.logger.error(f"File not found: {filepath}")
            continue

        try:
            xl = pd.ExcelFile(filepath)
            sheet_names = [s for s in xl.sheet_names if s.strip() != "GVMetadata"]

            for sheet_name in sheet_names:
                df = pd.read_excel(
                    filepath,
                    sheet_name=sheet_name,
                    dtype=str
                ).fillna("")

                # Normalize column names
                df.columns = [
                    col.strip().lower()
                    .replace("/", "_")
                    .replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                    for col in df.columns
                ]

                # Check for duplicate columns
                if df.columns.duplicated().any():
                    dups = df.columns[df.columns.duplicated()].tolist()
                    application.logger.error(f"Duplicate columns in {sheet_name}: {dups}")
                    raise ValueError(f"Duplicate columns in sheet {sheet_name}")

                # Your pre_headers list (keep it outside or import)
                missing = [h for h in pre_headers if h not in df.columns]
                if missing:
                    df = df.reindex(columns=list(df.columns) + missing, fill_value="")

                if "application_no" not in df.columns:
                    application.logger.error(f"No 'application_no' column in sheet {sheet_name}")
                    continue

                all_sheets_data[sheet_name] = df

        except Exception as exc:
            application.logger.exception(f"Failed to read {filepath} → sheet {sheet_name}")
            continue

    # ── Process rows from all sheets ──
    insert_queries = []
    anomaly_inserts = []

    for sheet_name, df in all_sheets_data.items():
        duplicates[sheet_name] = []

        date_cols = [
            "applicationdate", "bcc_approval_date", "experiense_(start_date)",
            "appraised_date", "verfied_date_date", "client_dob", "co_borrower_dob"
        ]

        # Apply date parsing where needed
        for col in date_cols:
            if col in df.columns:
                df[col] = df[col].apply(parse_excel_date)  # your existing helper

        for _, row in df.iterrows():
            rec = row.to_dict()
            app_no = str(rec.get("application_no", "")).strip()

            if not app_no or app_no in ("", "nan", "NaN", "None"):
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

            # ── Duplicate check ──
            if app_no in existing_app_numbers:
                duplicates[sheet_name].append(rec)
                duplicate_count += 1
                continue

            # ── CNIC anomaly check ──
            cnic = str(rec.get("cnic", "")).strip()
            if cnic and cnic in existing_by_cnic:
                prev = existing_by_cnic[cnic]
                anomalies = []

                checks = [
                    ("Borrower_Name", "borrower_name"),
                    ("Gender", "gender"),
                    ("Branch_Name", "branch_name"),
                    ("Student_Name", "student_name"),
                    ("Student_Co_Borrower_Gender", "student_co_borrower_gender"),
                    ("Collage_Univeristy", "collage_univeristy"),
                ]

                for db_key, rec_key in checks:
                    db_val = str(prev.get(db_key, "")).strip().lower()
                    new_val = str(rec.get(rec_key, "")).strip().lower()
                    if db_val != new_val and db_val and new_val:
                        anomalies.append(
                            f"{db_key} mismatch: previous={db_val!r}, new={new_val!r}"
                        )

                if anomalies:
                    details = "; ".join(anomalies)
                    pre_disb_id = prev.get("pre_disb_temp_id")
                    anomaly_applications.add(app_no)

                    anomaly_inserts.append(
                        f"""
                        INSERT INTO tbl_pre_disb_anomalies 
                            (pre_disb_id, details, created_date)
                        VALUES 
                            ({pre_disb_id or 'NULL'}, {escape_sql_string(details)}, '{current_time}')
                        """
                    )

            # ── Build INSERT ──
            # (your original long INSERT statement goes here, adapted to use rec dict)
            # Make sure to escape/sanitize values properly
            # Example placeholder:
            # insert_query = build_pre_disb_insert_query(rec, uploaded_by_user_id, current_time)
            # insert_queries.append(insert_query)
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
                    '{clean_numeric_value(rec.get('annual_expenses', '0'))}', '{rec.get('applicationdate', '')}', '{rec.get('bcc_approval_date', '')}',
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
                    '{str('0')}', '{current_time}'
                )
            """
            insert_queries.append(query)
            new_records_count += 1

    # ── Execute inserts ──
    if insert_queries:
        # for query_list in insert_queries:
        #     if query_list:
        #         batch_query = ";".join(query_list)
        #         execute_command(batch_query, is_print=False)
        #         application.logger.debug(f"process_upload: {len(query_list)} records")
        execute_command(";\n".join(insert_queries))

    if anomaly_inserts:
        execute_command(";\n".join(anomaly_inserts))

    # ── Generate reports if requested ──
    if generate_reports:
        # Duplicates summary Excel
        if any(duplicates.values()):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pre_disb_duplicates_{timestamp}.xlsx"
            summary_excel_path = os.path.join(
                current_app.config["UPLOAD_FOLDER"], filename
            )
            with pd.ExcelWriter(summary_excel_path) as writer:
                for sheet, rows in duplicates.items():
                    if rows:
                        pd.DataFrame(rows).to_excel(writer, sheet_name=sheet[:31], index=False)

        # Anomalies report (your existing function)
        if anomaly_applications:
            anomalies_report_path = generate_anomalies_html(list(anomaly_applications))

    # ── Result for caller / logging ──
    result = {
        "success": True,
        "new_records_count": new_records_count,
        "duplicate_count": duplicate_count,
        "anomalies_detected": len(anomaly_applications),
        "anomalies_count": len(anomaly_applications),
        "summary_excel_path": summary_excel_path,
        "anomalies_report_path": anomalies_report_path,
        "processed_sheets": list(all_sheets_data.keys()),
    }

    return result


def main():
    job_id = None
    start_time = datetime.now()

    temp_dir = None
    summary_path = None
    anomalies_path = None

    try:

        emails_found = 0
        files_processed = 0
        new_records_count = 0
        duplicates_count = 0
        anomalies_count = 0

        # Environment variables
        user = os.getenv('EMAIL_USER', 'alihabib202299@gmail.com')
        password = os.getenv('EMAIL_PASS', 'eqnp oytt klbi ojit')
        imap_server = os.getenv('IMAP_SERVER', 'imap.gmail.com')
        sender_email = os.getenv('EMAIL_SENDER', 'zali9261@gmail.com')

        if not all([user, password, sender_email]):
            raise ValueError("Missing required env vars: EMAIL_USER, EMAIL_PASS, EMAIL_SENDER")

        # Connect to IMAP
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(user, password)
        mail.select('INBOX')

        today = datetime.now()
        date_str = today.strftime("%d-%b-%Y")

        subject_search = os.getenv('PRE_DISB_SUBJECT', 'Daily Pre-Loan Disbursement Summary||Attachments Excel File')
        # subject_search = subject_search.replace('\u2013', '-')  # en dash → hyphen
        # subject_search = subject_search.replace('\u2014', '-')  # em dash → hyphen
        # subject_search = subject_search.replace('–', '-')  # literal en dash
        # subject_search = subject_search.replace('—', '-')

        # Split into list and clean each one
        subjects = [s.strip()
            .replace('\u2013', '-')  # en dash
            .replace('\u2014', '-')  # em dash
            .replace('–', '-')  # literal en dash
            .replace('—', '-') for s in subject_search.split('||') if s.strip()]

        if not subjects:
            subjects = ['Daily Pre-Loan Disbursement Summary']  # fallback

        # Build OR chain
        subject_clauses = ' '.join(f'SUBJECT "{s}"' for s in subjects)

        if len(subjects) == 1:
            subject_part = subject_clauses
        else:
            # Nested ORs — IMAP requires this structure for >2 items
            subject_part = subject_clauses
            for _ in range(len(subjects) - 2):
                subject_part = f'(OR {subject_part})'

            subject_part = f'(OR {subject_part})'

        print(subject_part)

        search_criteria = f'(SINCE "{date_str}" FROM "{sender_email}" {subject_part} UNSEEN)'
        print(search_criteria)

        status, messages = mail.search(None, search_criteria)
        if status != 'OK':
            raise RuntimeError(f"IMAP search failed: {status}")

        mail_ids = messages[0].split()
        emails_found = len(mail_ids)

        if not mail_ids:
            logger.info("No matching emails found today")
            mail.logout()
            return

        job_id = log_job_start()
        logger.info(f"Pre-disbursement email processor started - run ID: {job_id}")

        logger.info(f"Found {emails_found} matching email(s)")

        # Create temporary directory for downloaded files
        temp_dir = tempfile.mkdtemp(prefix="pre_disb_cron_")

        for num in mail_ids:
            _, msg_data = mail.fetch(num, '(RFC822)')
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = decode_subject(msg['Subject'] or '')
            logger.info(f"Processing email: {subject}")

            excel_attachments = get_excel_attachments(msg)
            if not excel_attachments:
                logger.warning("No Excel attachments found")
                continue

            # Save attachments to temporary files
            filepaths = []
            for filename, raw_bytes in excel_attachments:
                temp_path = os.path.join(temp_dir, filename)
                with open(temp_path, 'wb') as f:
                    f.write(raw_bytes.getvalue())
                filepaths.append(temp_path)
                files_processed += 1

            # Process using the new dedicated function
            try:
                result = process_pre_disbursement_files(
                    filepaths=filepaths,
                    input_timestamp=today.strftime('%Y-%m-%d'),
                    uploaded_by_user_id="system-cron",   # or get_current_user_id() if applicable
                    generate_reports=True
                )

                # Extract metrics for logging
                new_records_count += result.get('new_records_count', 0)
                duplicates_count += result.get('duplicate_count', 0)
                anomalies_count += result.get('anomalies_count', 0)
                summary_path = result.get('summary_excel_path')
                anomalies_path = result.get('anomalies_report_path')

                logger.info(f"Processed {len(filepaths)} files → new: {new_records_count}, dups: {duplicates_count}, anomalies: {anomalies_count}")

            except Exception as proc_err:
                logger.error(f"Processing failed for attachments in email {subject}: {proc_err}", exc_info=True)

            # Mark email as seen
            mail.store(num, '+FLAGS', '\\Seen')

        mail.logout()

        # Final logging
        duration = int((datetime.now() - start_time).total_seconds())

        log_job_end(
            job_id=job_id,
            status='succeeded',
            duration_sec=duration,
            emails_found=emails_found,
            files_processed=files_processed,
            new_records_count=new_records_count,
            duplicates_count=duplicates_count,
            anomalies_count=anomalies_count,
            summary_path=summary_path,
            anomalies_path=anomalies_path
        )

        logger.info("Pre-disbursement email processor completed successfully")

    except Exception as e:
        logger.error(f"Critical error in cron job: {e}", exc_info=True)

        duration = int((datetime.now() - start_time).total_seconds()) if start_time else None

        error_msg = str(e).encode('ascii', errors='replace').decode('ascii')
        error_trace = traceback.format_exc(limit=8)

        if job_id is not None:
            log_job_end(
                job_id=job_id,
                status='failed',
                duration_sec=duration,
                emails_found=emails_found,
                files_processed=files_processed,
                new_records_count=new_records_count,
                duplicates_count=duplicates_count,
                anomalies_count=anomalies_count,
                summary_path=summary_path,
                anomalies_path=anomalies_path,
                error_msg=error_msg,
                error_trace=error_trace
            )

    finally:
        # Cleanup temporary files
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temp dir: {temp_dir}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to clean up temp dir {temp_dir}: {cleanup_err}")

        try:
            mail.logout()
        except:
            pass

if __name__ == '__main__':
    with application.app_context():
        main()