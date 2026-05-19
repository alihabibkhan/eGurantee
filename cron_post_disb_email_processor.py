from imports import *
from pdf_helper import *
from App_File_Uploading_Validation import parse_excel_date, sanitize_file_columns, clean_numeric_value
import tempfile
import shutil
from Model_Email import get_cron_success_email_body, send_email_with_attachments, send_email

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_job_start(job_name="post-disb-email-processor"):
    """Log start of post-disbursement job and return job_id"""
    try:
        query = f"""
            INSERT INTO monitoring.post_disb_email_processor_runs (
                job_name, started_at, status
            ) VALUES ('{job_name}', NOW(), 'running')
            RETURNING id
        """
        inserted_record_id = execute_command(query)

        return inserted_record_id

    except Exception as e:
        logger.error(f'cron_post_disb_email_processor -> log_job_start -> exception: {str(e)}')
        return None


def log_job_end(job_id, status, duration_sec=None, emails_found=0, files_processed=0,
                new_records_count=0, duplicates_count=0, anomalies_count=0,
                summary_path=None, anomalies_path=None, error_msg=None, error_trace=None):
    """Log end of post-disbursement job"""
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
            UPDATE monitoring.post_disb_email_processor_runs
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


def process_post_disbursement_files(
        filepaths: list[str],
        input_timestamp: str | None = None,
        category: str = "los",  # 'los', 'mis', or 'both'
        uploaded_by_user_id: str | None = None,
        generate_reports: bool = True
) -> dict:
    """
    Process one or more Excel files containing post-disbursement data (LOS/MIS).

    Note: ALL records are inserted (including duplicates) for historical tracking.
    Duplicates are flagged and anomaly detection runs against previous records.

    Args:
        filepaths: List of Excel file paths to process
        input_timestamp: Date for mis_date field (defaults to today)
        category: 'los', 'mis', or 'both' (for two files - one LOS, one MIS)
        uploaded_by_user_id: User ID who uploaded (defaults to "system-cron")
        generate_reports: Whether to generate duplicate and anomaly reports

    Returns:
        dict: Processing results with metrics and report paths
    """
    if not filepaths:
        return {"success": False, "error": "No files provided"}

    input_timestamp = input_timestamp or datetime.now().strftime("%Y-%m-%d")
    uploaded_by_user_id = uploaded_by_user_id or "0"
    current_time = datetime.now().isoformat()

    # Define headers
    los_headers = [
        'sector_code', 'branch_code', 'branch_name', 'cnic', 'gender', 'address', 'mobile_number',
        'loan_title', 'rt', 'loan_number', 'product_code', 'loancreationdate', 'disb_amt',
        'loanrepaymenttype', 'sector', 'purpose', 'loanstatus', 'closed_on_date', 'act_clo',
        'colloanno', 'coll_id', 'lrno', 'collat', 'coll_stat', 'collateral_value', 'collateraltitle',
        'od_days', 'os_p', 'total_outstand_other', 'total_outstand_markup', 'lo', 'fc_los', 'dtf',
        'dtt', 'customer_id', 'application_num'
    ]

    mis_headers = [
        'sector_code', 'bcode', 'branch_name', 'customer_id', 'gender', 'address', 'mobile',
        'loantitle', 'rt', 'loanno', 'product_code', 'loancreationdate', 'disbursedamt',
        'loanrepaymenttype', 'sector', 'purpose', 'loanstatus', 'ln_clo_dt', 'act_clo',
        'colloanno', 'coll_id', 'lrno', 'collateral_type', 'coll_stat', 'collateral_value',
        'collateraltitle', 'od_days', 'total_outstand_principal', 'total_outstand_other',
        'total_outstand_markup', 'clo_on', 'liab_id', 'pool_id', 'account_number'
    ]

    # Mapping dictionaries
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

    # ── Results containers ──
    duplicates = {}  # sheet_name → list of duplicate rows (for reporting only)
    new_records_count = 0
    duplicate_count = 0  # Count of records that are duplicates (but still inserted)
    anomaly_applications = set()
    summary_excel_path = None
    anomalies_report_path = None

    # ── Load existing data for anomaly detection ──
    # Load pre-disbursement data
    pre_disb_records = fetch_records(
        """
        SELECT 
            "pre_disb_temp_id", 
            "Application_No", 
            "CNIC", 
            "Borrower_Name",
            KFT_Approved_Loan_Limit,
            "approved_date"
        FROM tbl_pre_disbursement_temp
        """
    )
    existing_by_app_no = {str(r["Application_No"]): r for r in pre_disb_records}

    # Load existing post-disbursement records (all historical, not just recent)
    existing_post_records = fetch_records(
        """
        SELECT customer_id, loan_no, branch_name, gender, product_code, booked_on, 
               repayment_type, principal_outstanding, disbursed_amount, mis_date,
               loan_status, overdue_days
        FROM tbl_post_disbursement 
        ORDER BY mis_date DESC
        """
    )

    # Group by loan_no to get the most recent record for each loan
    latest_post_by_loan = {}
    for r in existing_post_records:
        loan_no = str(r.get('loan_no', None))
        if loan_no and loan_no not in latest_post_by_loan:
            latest_post_by_loan[loan_no] = r  # First one encountered (most recent due to ORDER BY)

    # ── Process each file ──
    all_sheets_data = []
    file_categories = []

    # Determine category for each file
    if category == 'both' and len(filepaths) >= 2:
        file_categories = ['los', 'mis']
    else:
        file_categories = [category] * len(filepaths)

    for file_idx, filepath in enumerate(filepaths):
        if not os.path.exists(filepath):
            application.logger.error(f"File not found: {filepath}")
            continue

        current_category = file_categories[file_idx] if file_idx < len(file_categories) else category
        expected_headers = los_headers if current_category == 'los' else mis_headers
        mapping = post_to_los_mapping if current_category == 'los' else post_to_mis_mapping
        inverse_mapping = {v: k for k, v in mapping.items()}

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

                # Rename columns based on mapping
                rename_dict = {k: v for k, v in inverse_mapping.items() if k in df.columns}
                df = df.rename(columns=rename_dict)

                # Apply LOS to MIS mapping if needed
                if current_category == 'los' and category == 'both' and file_idx == 0:
                    los_rename_dict = {k: v for k, v in los_to_mis_mapping.items() if k in df.columns}
                    df = df.rename(columns=los_rename_dict)

                # Add missing headers
                missing = [h for h in expected_headers if h not in df.columns]
                if missing:
                    df = df.reindex(columns=list(df.columns) + missing, fill_value="")

                if "loan_no" not in df.columns:
                    application.logger.error(f"No 'loan_no' column in sheet {sheet_name}")
                    continue

                all_sheets_data.append({
                    'sheet_name': sheet_name,
                    'df': df,
                    'category': current_category,
                    'file_idx': file_idx
                })

        except Exception as exc:
            application.logger.exception(f"Failed to read {filepath} → {str(exc)}")
            continue

    # ── Process rows from all sheets (INSERT ALL, even duplicates) ──
    insert_queries = []
    anomaly_inserts = []

    for sheet_info in all_sheets_data:
        sheet_name = sheet_info['sheet_name']
        df = sheet_info['df']
        current_category = sheet_info['category']

        duplicates[sheet_name] = []

        date_cols = ["loancreationdate", "booked_on", "closed_on_date", "ln_clo_dt", "clo_on", "dtf", "dtt"]

        # Apply date parsing where needed
        for col in date_cols:
            if col in df.columns:
                df[col] = df[col].apply(parse_excel_date)

        for _, row in df.iterrows():
            rec = row.to_dict()
            loan_no = str(rec.get("loan_no", "")).strip()
            customer_id = str(rec.get("customer_id", "")).strip()

            if not loan_no or loan_no in ("", "nan", "NaN", "None"):
                continue

            # ── Check if duplicate (exists in database) - for tracking only ──
            is_duplicate = loan_no in latest_post_by_loan
            if is_duplicate:
                duplicates[sheet_name].append(rec)
                duplicate_count += 1
                application.logger.debug(f"Duplicate loan_no found: {loan_no} - will still insert for history")

            # ── Anomaly detection with pre-disbursement data ──
            if customer_id and customer_id in existing_by_app_no:
                prev = existing_by_app_no[customer_id]
                anomalies = []

                try:
                    pre_disb_id = prev.get('pre_disb_temp_id')
                    kft_approved_limit = int(float(str(prev.get('KFT_Approved_Loan_Limit', '0'))))
                    disbursed_amount = int(float(str(rec.get('disbursed_amount', '0'))))

                    if kft_approved_limit != disbursed_amount:
                        anomalies.append(
                            f"KFT Approved Amount mismatch: Pre-disbursement = {kft_approved_limit}, "
                            f"Post-disbursement = {disbursed_amount}"
                        )
                except ValueError as ve:
                    anomalies.append(f"Invalid amount format for KFT/disbursed: {str(ve)}")

                try:
                    booked_on_date = pd.to_datetime(str(rec.get('booked_on', None)), errors='coerce')
                    approval_date = pd.to_datetime(str(prev.get('approved_date', None)), errors='coerce')
                    if pd.notnull(booked_on_date) and pd.notnull(approval_date) and booked_on_date < approval_date:
                        anomalies.append(
                            f"Booked date before approval: booked_on = {booked_on_date}, "
                            f"approval_date = {approval_date}"
                        )
                except Exception as date_err:
                    anomalies.append(f"Date comparison error: {str(date_err)}")

                if anomalies:
                    details = "; ".join(anomalies)
                    anomaly_applications.add(customer_id)

                    anomaly_inserts.append(
                        f"""
                        INSERT INTO tbl_post_disbursement_anomalies 
                            (pre_disb_id, application_no, details, created_date)
                        VALUES 
                            ({pre_disb_id or 'NULL'}, '{customer_id}', {escape_sql_string(details)}, '{current_time}')
                        """
                    )

            # ── Anomaly detection comparing with most recent post-disbursement record ──
            if loan_no and loan_no in latest_post_by_loan:
                prev = latest_post_by_loan[loan_no]
                anomalies = []

                # Check field mismatches
                fields_to_check = [
                    ('branch_name', 'branch_name'),
                    ('gender', 'gender'),
                    ('product_code', 'product_code'),
                    ('repayment_type', 'repayment_type')
                ]

                for db_field, rec_field in fields_to_check:
                    prev_val = str(prev.get(db_field, None)).strip().lower()
                    curr_val = str(rec.get(rec_field, None)).strip().lower()
                    if prev_val != curr_val and prev_val and curr_val:
                        anomalies.append(
                            f"{db_field} mismatch: Previous = '{prev_val}', Current = '{curr_val}'"
                        )

                # Check outstanding amount changes
                try:
                    curr_outstanding = int(float(str(rec.get('principal_outstanding', '0'))))
                    prev_outstanding = int(float(str(prev.get('principal_outstanding', '0'))))
                    curr_disbursed = int(float(str(rec.get('disbursed_amount', '0'))))

                    if curr_outstanding > prev_outstanding:
                        anomalies.append(
                            f"Outstanding amount increased: Previous = {prev_outstanding}, "
                            f"Current = {curr_outstanding}"
                        )
                    if curr_outstanding > curr_disbursed:
                        anomalies.append(
                            f"Outstanding exceeds disbursed: Outstanding = {curr_outstanding}, "
                            f"Disbursed = {curr_disbursed}"
                        )
                except ValueError as ve:
                    anomalies.append(f"Amount validation error: {str(ve)}")

                # Check overdue days
                try:
                    curr_overdue = int(float(str(rec.get('overdue_days', '0'))))
                    prev_overdue = int(float(str(prev.get('overdue_days', '0'))))
                    if curr_overdue > prev_overdue:
                        anomalies.append(
                            f"Overdue days increased: Previous = {prev_overdue}, Current = {curr_overdue}"
                        )
                except ValueError:
                    pass

                if anomalies:
                    details = "; ".join(anomalies)
                    anomaly_applications.add(customer_id or loan_no)

                    anomaly_inserts.append(
                        f"""
                        INSERT INTO tbl_post_disbursement_anomalies 
                            (application_no, details, created_date)
                        VALUES 
                            ('{customer_id or loan_no}', {escape_sql_string(details)}, '{current_time}')
                        """
                    )

            # ── Build INSERT query (ALWAYS INSERT, even for duplicates) ──
            loan_closed_on = str(rec.get('loan_closed_on', '1900-01-01')).strip()
            booked_on = str(rec.get('booked_on', '1900-01-01'))
            clo_on = str(rec.get('clo_on', '1900-01-01'))

            if loan_closed_on in ['', 'None']:
                loan_closed_on = '1900-01-01'


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
                    '{input_timestamp}', '{sanitize_file_columns(str(rec.get('area', None)))}', 
                    '{rec.get('sector_code', None)}', '{rec.get('branch_code', None)}', 
                    '{sanitize_file_columns(rec.get('branch_name', None))}', '{rec.get('cnic', None)}',
                    '{rec.get('gender', None)}', '{sanitize_file_columns(str(rec.get('address', None)))}', 
                    '{rec.get('mobile_no', None)}', '{sanitize_file_columns(rec.get('loan_title', None))}',
                    '{rec.get('rt', None)}', '{loan_no}', '{rec.get('product_code', None)}', 
                    '{booked_on}', '{clean_numeric_value(rec.get('disbursed_amount', '0'))}',
                    '{rec.get('repayment_type', None)}', '{rec.get('sector', None)}', 
                    '{rec.get('purpose', None)}', '{rec.get('loan_status', None)}', '{loan_closed_on}',
                    '{rec.get('act_clo', None)}', '{rec.get('colloanno', None)}', '{rec.get('coll_id', None)}', 
                    '{rec.get('lrno', None)}', '{rec.get('collat', None)}', '{rec.get('coll_stat', None)}',
                    '{clean_numeric_value(rec.get('collateral_value', '0'))}', 
                    '{sanitize_file_columns(rec.get('collateral_title', None))}',
                    '{clean_numeric_value(rec.get('overdue_days', '0'))}', 
                    '{clean_numeric_value(rec.get('principal_outstanding', '0'))}',
                    '{clean_numeric_value(rec.get('total_outstand_other', '0'))}',
                    '{clean_numeric_value(rec.get('markup_outstanding', '0'))}', '{rec.get('lo', None)}',
                    '{rec.get('fc_los', None)}', '{rec.get('dtf', None)}', '{rec.get('dtt', None)}',
                    '{rec.get('customer_id', None)}', '{rec.get('application_num', None)}', '{clo_on}',
                    '{rec.get('liab_id', None)}', '{rec.get('pool_id', None)}', '{rec.get('account_number', None)}',
                    '{uploaded_by_user_id}', '{current_time}'
                )
            """
            insert_queries.append(query)
            new_records_count += 1

    # ── Execute inserts (ALL records, including duplicates) ──
    if insert_queries:
        try:
            # Execute in batches to avoid overwhelming the database
            batch_size = 100
            for i in range(0, len(insert_queries), batch_size):
                batch = insert_queries[i:i + batch_size]
                execute_command(";\n".join(batch))
                logger.info(f"Inserted batch {i // batch_size + 1}: {len(batch)} records")

            logger.info(f"Successfully inserted {len(insert_queries)} post-disbursement records "
                        f"({duplicate_count} were duplicates)")
        except Exception as e:
            logger.error(f"Batch insert failed: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Insert failed: {str(e)}"}

    # ── Execute anomaly inserts ──
    if anomaly_inserts:
        try:
            execute_command(";\n".join(anomaly_inserts))
            logger.info(f"Inserted {len(anomaly_inserts)} anomaly records")
        except Exception as e:
            logger.error(f"Anomaly insert failed: {str(e)}", exc_info=True)

    # ── Generate reports if requested ──
    if generate_reports:
        # Duplicates summary Excel (for reporting only - doesn't affect inserts)
        if any(duplicates.values()):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"post_disb_duplicates_{timestamp}.xlsx"
            summary_excel_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)

            try:
                with pd.ExcelWriter(summary_excel_path) as writer:
                    for sheet, rows in duplicates.items():
                        if rows:
                            df_to_save = pd.DataFrame(rows)
                            logger.info(f"Saving duplicate sheet {sheet} with {len(rows)} rows")
                            df_to_save.to_excel(writer, sheet_name=sheet[:31], index=False)
                logger.info(f"✅ Duplicates report created: {summary_excel_path}")
            except Exception as e:
                logger.error(f"❌ Error creating duplicates Excel file: {str(e)}")
                summary_excel_path = None

        # Anomalies report
        if anomaly_applications:
            try:
                anomalies_report_path = generate_anomalies_html(list(anomaly_applications))
                logger.info(f"✅ Anomalies report created: {anomalies_report_path}")
            except Exception as e:
                logger.error(f"❌ Error creating anomalies report: {str(e)}")
                anomalies_report_path = None

    # ── Result for caller / logging ──
    result = {
        "success": True,
        "new_records_count": new_records_count,
        "duplicate_count": duplicate_count,  # Records that were duplicates (but still inserted)
        "anomalies_detected": len(anomaly_applications),
        "anomalies_count": len(anomaly_applications),
        "summary_excel_path": summary_excel_path,
        "anomalies_report_path": anomalies_report_path,
        "processed_files": len(filepaths),
    }

    return result


def build_or_chain(items, field):
    """Build proper IMAP OR chain for multiple items"""
    if not items:
        return ""
    if len(items) == 1:
        return f'{field} "{items[0]}"'

    clauses = [f'{field} "{item}"' for item in items]
    result = clauses[0]

    for clause in clauses[1:]:
        result = f'(OR {result} {clause})'

    return result


def main():
    job_id = None
    start_time = datetime.now()
    temp_dir = None
    summary_path = None
    anomalies_path = None

    # Statistics for logging
    emails_found = 0
    files_processed = 0
    new_records_count = 0
    duplicates_count = 0
    anomalies_count = 0

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 30

    try:
        # Environment variables
        user = os.getenv('EMAIL_USER')
        password = os.getenv('EMAIL_PASS')
        imap_server = os.getenv('IMAP_SERVER')
        sender_email = os.getenv('POST_DISB_SENDER_EMAIL')

        if not all([user, password, sender_email]):
            raise ValueError("Missing required env vars: EMAIL_USER, EMAIL_PASS, POST_DISB_SENDER_EMAIL")

        # Connect to IMAP
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(user, password)
        mail.select('INBOX')

        today = datetime.now()
        date_str = today.strftime("%d-%b-%Y")

        # Get subject keywords from env
        subject_search = os.getenv('POST_DISB_SUBJECT', 'Daily Post-Loan Disbursement Summary||Post Disbursement Report')

        subjects = [s.strip()
                    .replace('\u2013', '-')
                    .replace('\u2014', '-')
                    .replace('–', '-')
                    .replace('—', '-')
                    for s in subject_search.split('||') if s.strip()]

        # Handle multiple senders
        senders = [s.strip() for s in sender_email.split('||') if s.strip()]

        if not senders:
            logger.error("No sender email configured in POST_DISB_SENDER_EMAIL")
            return

        if not subjects:
            subjects = ['Daily Post-Loan Disbursement Summary']

        subject_part = build_or_chain(subjects, 'SUBJECT')
        sender_part = build_or_chain(senders, 'FROM')

        logger.info(f"Subject search pattern: {subject_part}")
        logger.info(f"Sender search pattern: {sender_part}")

        search_criteria = f'(SINCE "{date_str}" {sender_part} {subject_part} UNSEEN)'
        logger.info(f"Search criteria: {search_criteria}")

        # === RETRY LOGIC FOR EMAIL FETCHING ===
        mail_ids = []
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Email search attempt {attempt}/{MAX_RETRIES}")
                status, messages = mail.search(None, search_criteria)

                if status != 'OK':
                    logger.warning(f"IMAP search failed on attempt {attempt}: {status}")
                    if attempt < MAX_RETRIES:
                        logger.info(f"Waiting {RETRY_DELAY_SECONDS} seconds before retry...")
                        time.sleep(RETRY_DELAY_SECONDS)
                        mail.select('INBOX')
                        continue
                    else:
                        raise RuntimeError(f"IMAP search failed after {MAX_RETRIES} attempts: {status}")

                mail_ids = messages[0].split()
                emails_found = len(mail_ids)

                if emails_found > 0:
                    logger.info(f"Found {emails_found} email(s) on attempt {attempt}")
                    break
                else:
                    logger.warning(f"No emails found on attempt {attempt}")
                    if attempt < MAX_RETRIES:
                        logger.info(f"Waiting {RETRY_DELAY_SECONDS} seconds before retry...")
                        time.sleep(RETRY_DELAY_SECONDS)
                        mail.select('INBOX')
                    else:
                        logger.info(f"No emails found after {MAX_RETRIES} attempts. Exiting.")
                        mail.logout()
                        return

            except Exception as attempt_error:
                logger.error(f"Error on attempt {attempt}: {attempt_error}")
                if attempt < MAX_RETRIES:
                    logger.info(f"Waiting {RETRY_DELAY_SECONDS} seconds before retry...")
                    time.sleep(RETRY_DELAY_SECONDS)
                    try:
                        mail.select('INBOX')
                    except:
                        mail = imaplib.IMAP4_SSL(imap_server)
                        mail.login(user, password)
                        mail.select('INBOX')
                else:
                    raise

        if not mail_ids:
            logger.info("No matching emails found today after all retry attempts")
            mail.logout()
            return

        # Log job start
        job_id = log_job_start()
        logger.info(f"Post-disbursement email processor started - run ID: {job_id}")
        logger.info(f"Found {emails_found} matching email(s)")

        # Create temporary directory for downloaded files
        temp_dir = tempfile.mkdtemp(prefix="post_disb_cron_")

        # Determine category from environment or default to 'both'
        category = os.getenv('POST_DISB_CATEGORY', 'both')

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

            logger.info(f"Saved {len(filepaths)} attachment(s) for processing")

            # Process using the post-disbursement function
            try:
                result = process_post_disbursement_files(
                    filepaths=filepaths,
                    input_timestamp=today.strftime('%Y-%m-%d'),
                    category=category,
                    uploaded_by_user_id="system-cron",
                    generate_reports=True
                )

                if result.get('success'):
                    new_records_count += result.get('new_records_count', 0)
                    duplicates_count += result.get('duplicate_count', 0)
                    anomalies_count += result.get('anomalies_count', 0)
                    summary_path = result.get('summary_excel_path') or summary_path
                    anomalies_path = result.get('anomalies_report_path') or anomalies_path

                    logger.info(
                        f"Processed {len(filepaths)} files → "
                        f"new: {new_records_count}, dups: {duplicates_count}, anomalies: {anomalies_count}"
                    )
                else:
                    logger.error(f"Processing failed: {result.get('error', 'Unknown error')}")

            except Exception as proc_err:
                logger.error(f"Processing failed for attachments in email {subject}: {proc_err}", exc_info=True)

            # Mark email as seen
            mail.store(num, '+FLAGS', '\\Seen')

        mail.logout()

        # Final logging
        duration = int((datetime.now() - start_time).total_seconds())
        status = 'succeeded' if new_records_count > 0 or files_processed > 0 else 'completed_no_data'

        log_job_end(
            job_id=job_id,
            status=status,
            duration_sec=duration,
            emails_found=emails_found,
            files_processed=files_processed,
            new_records_count=new_records_count,
            duplicates_count=duplicates_count,
            anomalies_count=anomalies_count,
            summary_path=summary_path,
            anomalies_path=anomalies_path
        )

        # Send success notification email if any records were processed
        if status == 'succeeded' and (new_records_count > 0 or anomalies_count > 0):
            summary_data = {
                'started_at': start_time.strftime('%Y-%m-%d %H:%M:%S PKT'),
                'finished_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S PKT'),
                'duration_seconds': duration,
                'emails_found': emails_found,
                'files_processed': files_processed,
                'new_records_count': new_records_count,
                'duplicates_count': duplicates_count,
                'anomalies_count': anomalies_count,
            }

            html_body = get_cron_success_email_body(
                job_name="Post-Disbursement Email Processor",
                summary_data=summary_data
            )

            # Prepare attachments list
            attachments_to_send = []

            # Add duplicates report if it exists
            if summary_path and os.path.exists(summary_path):
                try:
                    with open(summary_path, 'rb') as f:
                        attachments_to_send.append({
                            'filename': os.path.basename(summary_path),
                            'content': f.read(),
                            'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        })
                    logger.info(f"Prepared duplicates report attachment: {os.path.basename(summary_path)}")
                except Exception as e:
                    logger.error(f"Failed to read duplicates report: {str(e)}")

            # Add anomalies report if it exists
            if anomalies_path and os.path.exists(anomalies_path):
                try:
                    with open(anomalies_path, 'rb') as f:
                        content = f.read()
                        # Determine content type based on file extension
                        if anomalies_path.endswith('.html'):
                            content_type = 'text/html'
                        elif anomalies_path.endswith('.xlsx'):
                            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        else:
                            content_type = 'application/octet-stream'

                        attachments_to_send.append({
                            'filename': os.path.basename(anomalies_path),
                            'content': content,
                            'content_type': content_type
                        })
                    logger.info(f"Prepared anomalies report attachment: {os.path.basename(anomalies_path)}")
                except Exception as e:
                    logger.error(f"Failed to read anomalies report: {str(e)}")

            # Send email with attachments
            if attachments_to_send:
                success = send_email_with_attachments(
                    subject=f"Post-Disbursement Cron Job - Completed Successfully ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
                    email_list=[user],
                    message="The Post-Disbursement cron job completed successfully. See HTML version for details.",
                    html_message=html_body,
                    attachments=attachments_to_send,
                    add_cc_list=True,
                    cc_list=["zali9261@gmail.com"]
                )

                if success:
                    logger.info(f"Success notification email sent with {len(attachments_to_send)} attachment(s)")
                else:
                    logger.warning("Failed to send success notification email")
            else:
                # Send without attachments if no reports were generated
                success = send_email(
                    subject="Post-Disbursement Cron Job - Completed Successfully",
                    email_list=[user],
                    message="The Post-Disbursement cron job completed successfully. See HTML version for details.",
                    html_message=html_body,
                    add_cc_list=True,
                    cc_list=["zali9261@gmail.com"]
                )

                if success:
                    logger.info("Success notification email sent (no attachments)")
                else:
                    logger.warning("Failed to send success notification email")

        logger.info("Post-disbursement email processor completed successfully")

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


if __name__ == '__main__':
    with application.app_context():
        main()