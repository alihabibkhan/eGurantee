from imports import *
from application import application
from App_File_Uploading_Validation import process_zip_application_images
from Model_Email import send_email, get_cron_success_email_body

# Setup logging (Render shows stdout/stderr in logs)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_job_start():
    host_info = os.uname().nodename if hasattr(os, 'uname') else 'render'
    query = f"""
        INSERT INTO monitoring.cron_job_runs (
                    job_name, started_at, status, host_info
                ) VALUES ('email-zip-processor', NOW(), 'running', '{str(host_info)}')
                RETURNING id
        """
    inserted_record_id = execute_command(query)

    return inserted_record_id


def log_job_end(job_id, status, duration_sec=None, emails_found=0, zips_processed=0,
                images_processed=0, images_skipped=0, error_msg=None, error_trace=None):
    try:
        query = f"""
            UPDATE monitoring.cron_job_runs
            SET 
                finished_at     = NOW(),
                status          = '{status}',
                duration_seconds = {duration_sec if duration_sec is not None else 'NULL'},
                emails_found    = {emails_found},
                zips_processed  = {zips_processed},
                images_processed= {images_processed},
                images_skipped  = {images_skipped},
                error_message   = {f"'{error_msg}'" if error_msg is not None else 'NULL'},
                error_trace     = {f"'{error_trace}'" if error_trace is not None else 'NULL'},
                updated_at      = NOW()
            WHERE id = {job_id}
        """
        execute_command(query)
    except Exception as e:
        print(f"Failed to update job log: {e}")


def decode_subject(subject):
    """Decode email subject (handles encoded subjects)"""
    decoded, encoding = decode_header(subject)[0]
    if isinstance(decoded, bytes):
        return decoded.decode(encoding or 'utf-8', errors='ignore')
    return decoded


def get_zip_attachments(msg):
    """Extract ZIP attachments from email message"""
    zips = []
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
            if filename.lower().endswith('.zip'):
                payload = part.get_payload(decode=True)
                if payload:
                    zips.append((filename, BytesIO(payload)))
                    logger.info(f"Found ZIP attachment: {filename}")
    return zips



# def main():
#     job_id = None
#     start_time = datetime.now()
#
#     job_id = log_job_start()
#     logger.info(f"Job started - run ID: {job_id}")
#
#     emails_found = 0
#     zips_processed = 0
#     total_processed = 0
#     total_skipped = 0
#
#     user = os.getenv('EMAIL_USER', 'alihabib202299@gmail.com')
#     password = os.getenv('EMAIL_PASS', 'eqnp oytt klbi ojit')
#     imap_server = os.getenv('IMAP_SERVER', 'imap.gmail.com')
#     sender_email = os.getenv('EMAIL_SENDER', 'zali9261@gmail.com')
#
#     if not user or not password:
#         logger.error("Missing EMAIL_USER or EMAIL_PASS env vars")
#         return
#
#     try:
#         # Connect & login
#         mail = imaplib.IMAP4_SSL(imap_server)
#         mail.login(user, password)
#
#         mail.select('INBOX')  # or '"[Gmail]/All Mail"' if needed
#
#         # Search criteria: since today, specific subject, unseen (to avoid re-processing)
#         today = datetime.now()
#         date_str = today.strftime("%d-%b-%Y")  # IMAP format: 05-Mar-2026
#
#         # Adjust 'FROM' if the sender is fixed; here assuming subject is main filter
#         # If sender is known, add: f'(SINCE "{date_str}" SUBJECT "Loan - Attachment Images (ZIP)" FROM "sender@example.com" UNSEEN)'
#         search_criteria = f'(SINCE "{date_str}" FROM "{sender_email}" SUBJECT "Loan - Attachment Images (ZIP)" UNSEEN)'
#
#         status, messages = mail.search(None, search_criteria)
#         if status != 'OK':
#             logger.error("Search failed")
#             return
#
#         mail_ids = messages[0].split()
#         if not mail_ids:
#             logger.info("No matching emails found today")
#             mail.logout()
#             return
#
#         logger.info(f"Found {len(mail_ids)} matching email(s)")
#
#         for num in mail_ids:
#             _, msg_data = mail.fetch(num, '(RFC822)')
#             raw_email = msg_data[0][1]
#             msg = email.message_from_bytes(raw_email)
#
#             subject = decode_subject(msg['Subject'] or '')
#             logger.info(f"Processing email: {subject}")
#
#             zip_attachments = get_zip_attachments(msg)
#             if not zip_attachments:
#                 logger.warning("No ZIP attachment found in this email")
#                 continue
#
#             for filename, zip_buffer in zip_attachments:
#                 try:
#                     # Reuse your existing function!
#                     # It expects a file-like object with .read()
#                     results = process_zip_application_images(zip_buffer)
#                     logger.info(f"Processed ZIP {filename}: {results}")
#                 except Exception as e:
#                     logger.error(f"Failed to process ZIP {filename}: {e}", exc_info=True)
#
#             # Mark as seen so we don't process again
#             mail.store(num, '+FLAGS', '\\Seen')
#
#         mail.logout()
#         logger.info("Cron job completed successfully")
#
#     except Exception as e:
#         logger.error(f"IMAP error: {e}", exc_info=True)


def main():
    job_id = None
    start_time = datetime.now()   # better to use timezone-aware

    try:
        emails_found = 0
        zips_processed = 0
        total_processed = 0
        total_skipped = 0

        user = os.getenv('EMAIL_USER', 'alihabib202299@gmail.com')
        password = os.getenv('EMAIL_PASS', 'eqnp oytt klbi ojit')
        imap_server = os.getenv('IMAP_SERVER', 'imap.gmail.com')
        sender_email = os.getenv('EMAIL_SENDER', 'zali9261@gmail.com')
        IMAGE_SUBJECT = os.getenv('IMAGE_SUBJECT', 'Loan – Attachment Images (ZIP)')

        if not user or not password:
            logger.error("Missing EMAIL_USER or EMAIL_PASS env vars")
            return

        # Connect & login
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(user, password)
        mail.select('INBOX')

        today = datetime.now().date()
        date_str = today.strftime("%d-%b-%Y")

        subjects = [s.strip()
                    .replace('\u2013', '-')  # en dash
                    .replace('\u2014', '-')  # em dash
                    .replace('–', '-')  # literal en dash
                    .replace('—', '-') for s in IMAGE_SUBJECT.split('||') if s.strip()]

        if not subjects:
            subjects = ['FW: Loan – Attachment Images (ZIP)']

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

        # IMAGE_SUBJECT = IMAGE_SUBJECT.replace('\u2013', '-')  # en dash → hyphen
        # IMAGE_SUBJECT = IMAGE_SUBJECT.replace('\u2014', '-')  # em dash → hyphen
        # IMAGE_SUBJECT = IMAGE_SUBJECT.replace('–', '-')  # literal en dash
        # IMAGE_SUBJECT = IMAGE_SUBJECT.replace('—', '-')

        search_criteria = f'(SINCE "{date_str}" FROM "{sender_email}" {subject_part} UNSEEN)'
        # search_criteria = f'(SINCE "{date_str}" FROM "{sender_email}" SUBJECT "{IMAGE_SUBJECT}" UNSEEN)'

        status, messages = mail.search(None, search_criteria)
        if status != 'OK':
            logger.error("Search failed")
            return

        mail_ids = messages[0].split()
        if not mail_ids:
            logger.info("No matching emails found today")
            mail.logout()
            # Still log success (zero emails is normal)
            return

        job_id = log_job_start()
        logger.info(f"Job started - run ID: {job_id}")

        logger.info(f"Found {len(mail_ids)} matching email(s)")
        emails_found = len(mail_ids)

        for num in mail_ids:
            _, msg_data = mail.fetch(num, '(RFC822)')
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = decode_subject(msg['Subject'] or '')
            logger.info(f"Processing email: {subject}")

            zip_attachments = get_zip_attachments(msg)
            if not zip_attachments:
                logger.warning("No ZIP attachment found in this email")
                continue

            for filename, zip_buffer in zip_attachments:
                zips_processed += 1
                try:
                    results = process_zip_application_images(zip_buffer, user_id='0')
                    logger.info(f"Processed ZIP {filename}: {results}")
                    total_processed += results.get('processed', 0)
                    total_skipped += results.get('skipped', 0)
                except Exception as e:
                    logger.error(f"Failed to process ZIP {filename}: {e}", exc_info=True)
                    # Optionally increment a failed_zips counter here if you want

            # Mark as seen
            mail.store(num, '+FLAGS', '\\Seen')

        mail.logout()
        logger.info("Cron job completed successfully")

        # ── Log success with collected metrics ──
        end_time = datetime.now()
        duration = int((end_time - start_time).total_seconds())

        status = 'succeeded'

        log_job_end(
            job_id=job_id,
            status=status,
            duration_sec=duration,
            emails_found=emails_found,
            zips_processed=zips_processed,
            images_processed=total_processed,
            images_skipped=total_skipped
        )

        if status == 'succeeded':
            # Prepare summary data (example – adapt from your log_job_end params)
            summary_data = {
                'started_at': start_time.strftime('%Y-%m-%d %H:%M:%S PKT'),
                'finished_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S PKT'),
                'duration_seconds': duration,
                'emails_found': emails_found,
                'files_processed': zips_processed,
                'new_records_count': total_processed,
                'duplicates_count': total_skipped,
                'anomalies_count': '',
            }

            html_body = get_cron_success_email_body(
                job_name="Images Email Processor",
                summary_data=summary_data
            )

            success = send_email(
                subject="Pre-Disbursement Cron Job - Completed Successfully",
                email_list=[user],
                message="The Pre-Disbursement cron job completed successfully. See HTML version for details.",
                html_message=html_body,
                add_cc_list=True,  # will use cc_list from env or default
                cc_list=["zali9261@gmail.com"]        # or pass explicitly if you prefer
            )

            if success:
                logger.info("Success notification email sent")
            else:
                logger.warning("Failed to send success notification email")



    except Exception as e:
        logger.error(f"IMAP / processing error: {e}", exc_info=True)

        end_time = datetime.now()
        duration = int((end_time - start_time).total_seconds()) if start_time else None

        if job_id is not None:
            log_job_end(
                job_id=job_id,
                status='failed',
                duration_sec=duration,
                emails_found=emails_found,
                zips_processed=zips_processed,
                images_processed=total_processed,
                images_skipped=total_skipped,
                error_msg=str(e),
                error_trace=traceback.format_exc(limit=8)  # last 8 lines of traceback
            )

    finally:
        # Any cleanup (e.g. close mail connection if still open)
        try:
            mail.logout()
        except:
            pass


if __name__ == '__main__':
    # If running in Flask context is needed (e.g. for DB functions inside process_zip_...)
    with application.app_context():
        main()