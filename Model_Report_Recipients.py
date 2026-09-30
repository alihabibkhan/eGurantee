from imports import *


REPORT_MANAGEMENT = 'management'
REPORT_REGIONAL = 'regional'

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def is_valid_email(email):
    return bool(EMAIL_PATTERN.match(email or ''))


def get_report_groups():
    """Management group + one group per active National Council Distribution, each with its active recipients."""
    regions = fetch_records("""
        SELECT national_council_distribution_id, national_council_distribution_name
        FROM tbl_national_council_distribution
        WHERE status = 1
        ORDER BY national_council_distribution_name
    """, is_print=False)

    recipients = fetch_records("""
        SELECT report_type, national_council_distribution_id, email
        FROM tbl_report_recipients
        WHERE status = 1
        ORDER BY recipient_id
    """, is_print=False)

    last_sent = fetch_records("""
        SELECT DISTINCT ON (report_type, COALESCE(national_council_distribution_id, 0))
            report_type, national_council_distribution_id, report_period, is_success, snapshot_id,
            TO_CHAR(sent_date, 'DD-Mon-YYYY HH24:MI') AS sent_date
        FROM tbl_report_email_log
        ORDER BY report_type, COALESCE(national_council_distribution_id, 0), sent_date DESC
    """, is_print=False)

    def emails_for(report_type, ncd_id):
        return [r['email'] for r in recipients
                if r['report_type'] == report_type and r['national_council_distribution_id'] == ncd_id]

    def last_sent_for(report_type, ncd_id):
        return next((r for r in last_sent
                     if r['report_type'] == report_type and r['national_council_distribution_id'] == ncd_id), None)

    groups = [{
        'report_type': REPORT_MANAGEMENT,
        'ncd_id': None,
        'name': 'Management Report',
        'region': None,
        'emails': emails_for(REPORT_MANAGEMENT, None),
        'last_sent': last_sent_for(REPORT_MANAGEMENT, None),
    }]
    for region in regions:
        ncd_id = region['national_council_distribution_id']
        groups.append({
            'report_type': REPORT_REGIONAL,
            'ncd_id': ncd_id,
            'name': region['national_council_distribution_name'],
            'region': region['national_council_distribution_name'],
            'emails': emails_for(REPORT_REGIONAL, ncd_id),
            'last_sent': last_sent_for(REPORT_REGIONAL, ncd_id),
        })
    return groups


def get_report_group(report_type, ncd_id):
    return next((g for g in get_report_groups()
                 if g['report_type'] == report_type and g['ncd_id'] == ncd_id), None)


def save_report_recipients(report_type, ncd_id, emails, user_id):
    """Replace the active recipient list of one group (single transaction)."""
    ncd_sql = 'IS NULL' if ncd_id is None else f"= {int(ncd_id)}"
    ncd_value = 'NULL' if ncd_id is None else str(int(ncd_id))
    user_value = int(user_id) if str(user_id).lstrip('-').isdigit() else 'NULL'

    statements = [f"""
        UPDATE tbl_report_recipients
        SET status = 2, modified_by = {user_value}, modified_date = CURRENT_TIMESTAMP
        WHERE status = 1 AND report_type = '{report_type}' AND national_council_distribution_id {ncd_sql}
    """]
    for email in emails:
        statements.append(f"""
            INSERT INTO tbl_report_recipients
                (report_type, national_council_distribution_id, email, status, created_by, modified_by)
            VALUES ('{report_type}', {ncd_value}, {escape_sql_string(email)}, 1, {user_value}, {user_value})
        """)
    execute_command(';'.join(statements), return_id=False)


def log_report_email(report_type, ncd_id, report_period, recipients, commentary, is_success, error_message, user_id,
                     snapshot_id=None):
    ncd_value = 'NULL' if ncd_id is None else str(int(ncd_id))
    user_value = int(user_id) if str(user_id).lstrip('-').isdigit() else 'NULL'
    snapshot_value = 'NULL' if snapshot_id is None else str(int(snapshot_id))
    execute_command(f"""
        INSERT INTO tbl_report_email_log
            (report_type, national_council_distribution_id, report_period, recipients, commentary,
             is_success, error_message, sent_by, snapshot_id)
        VALUES ('{report_type}', {ncd_value}, {escape_sql_string(report_period)},
                {escape_sql_string(', '.join(recipients))}, {escape_sql_string(commentary or None)},
                {1 if is_success else 0}, {escape_sql_string(error_message or None)}, {user_value}, {snapshot_value})
    """, return_id=False)


def save_report_snapshot(report_type, ncd_id, report_period, report_html, user_id):
    """Keep the exact report HTML that is attached to the email; returns its id (None if it could not be saved)."""
    ncd_value = 'NULL' if ncd_id is None else str(int(ncd_id))
    user_value = int(user_id) if str(user_id).lstrip('-').isdigit() else 'NULL'
    return execute_command(f"""
        INSERT INTO tbl_report_snapshots
            (report_type, national_council_distribution_id, report_period, report_html, created_by)
        VALUES ('{report_type}', {ncd_value}, {escape_sql_string(report_period)},
                {escape_sql_string(report_html)}, {user_value})
    """)


def get_report_snapshot_html(snapshot_id):
    result = fetch_records("SELECT report_html FROM tbl_report_snapshots WHERE snapshot_id = %s",
                           is_print=False, params=(int(snapshot_id),))
    return result[0]['report_html'] if result else None
