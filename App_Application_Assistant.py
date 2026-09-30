from imports import *
from application import application
from Model_Application_Assistant import *


def can_use_application_assistant():
    return is_login() and (
        str(session.get('rights')) in ['1', '2', '3', '4', '5']
        or PermissionHelper.has_permission(get_current_user_id(), "/application-assistant")
    )


def _fmt_date(value, with_time=False):
    if not value:
        return None
    try:
        parsed = value if isinstance(value, (datetime, date)) else parse(str(value))
        if parsed.year <= 1900:
            return None
        return parsed.strftime('%d-%b-%Y %I:%M %p' if with_time and isinstance(parsed, datetime) else '%d-%b-%Y')
    except (ValueError, OverflowError, TypeError):
        return str(value)


def _fmt_amount(value):
    try:
        return f"Rs {float(str(value).replace(',', '')):,.0f}"
    except (ValueError, TypeError):
        return None


def _email_summary(record):
    status = str(record.get('status'))
    email_status = str(record.get('email_status'))
    pending = str(record.get('exec_approval_pending')) == '1'

    if status in ['2', '9']:
        if email_status == '2':
            return {'state': 'sent', 'text': 'Approval letter email has been sent.'}
        if email_status == '3':
            return {'state': 'rejected', 'text': 'Approval letter email was rejected.'}
        if pending:
            return {'state': 'held', 'text': 'Email is on hold until the Executive approves.'}
        return {'state': 'not-sent', 'text': 'Approved, but the approval letter email has not been sent yet.'}
    if status in ['3', '10']:
        if pending:
            return {'state': 'held', 'text': 'Disagreement email is on hold until the Executive approves.'}
        return {'state': 'info', 'text': 'Disagreement email goes to the branch automatically; its delivery is not tracked.'}
    return {'state': 'info', 'text': 'No email at this stage - the application has not been finally decided yet.'}


def _executive_summary(record):
    if str(record.get('allow_exceptional_approval')) != '1':
        return None
    if str(record.get('exec_approval_pending')) == '1':
        return {'state': 'pending', 'text': 'Waiting for Executive approval.'}
    if record.get('exec_approved_by'):
        return {'state': 'done', 'text': f"Executive approved by {record['exec_approved_by']} on "
                                         f"{_fmt_date(record.get('exec_approved_date'), True)}."}
    return {'state': 'info', 'text': 'This product needs Executive approval after the approver decides.'}


def _timeline(record):
    events = [
        ('Reviewed', record.get('reviewed_by'), record.get('reviewed_date')),
        ('Approved', record.get('approved_by'), record.get('approved_date')),
        ('Disagreed', record.get('rejected_by'), record.get('rejected_date')),
        ('Executive approved', record.get('exec_approved_by'), record.get('exec_approved_date')),
    ]
    timeline = [
        {'label': label, 'by': by, 'date': _fmt_date(when, True), 'sort': str(when)}
        for label, by, when in events if by and _fmt_date(when)
    ]
    timeline.sort(key=lambda item: item.pop('sort'))
    return timeline


def _application_details(record):
    application_no = record.get('Application_No')

    images = [
        {'url': url_for('serve_pre_image', image_id=img['pd_ai_id']), 'uploaded': _fmt_date(img.get('created_date'), True)}
        for img in get_application_images_info(application_no)
    ]

    status = str(record.get('status'))
    return {
        'application_no': application_no,
        'borrower_name': record.get('Borrower_Name'),
        'cnic': record.get('CNIC'),
        'branch': record.get('Branch_Name'),
        'product_code': record.get('LoanProductCode'),
        'application_date': _fmt_date(record.get('ApplicationDate')),
        'requested_amount': _fmt_amount(record.get('Requested_Loan_Amount')),
        'loan_amount': _fmt_amount(record.get('Loan_Amount')),
        'approved_limit': _fmt_amount(record.get('kft_approved_loan_limit')),
        'status': status,
        'status_label': APPLICATION_STATUS_LABELS.get(status, 'Not Received'),
        'notes': record.get('notes'),
        'timeline': _timeline(record),
        'executive': _executive_summary(record),
        'email': _email_summary(record),
        'images': images,
    }


@application.route('/application-assistant')
def application_assistant():
    try:
        if can_use_application_assistant():
            return render_template('application_assistant.html', result={})
    except Exception as e:
        print('application-assistant exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/application-assistant/lookup', methods=['POST'])
def application_assistant_lookup():
    try:
        if not can_use_application_assistant():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        data = request.get_json(silent=True) or {}
        raw_text = ' '.join(str(data.get('query', '')).split())
        search_text = raw_text.replace(' ', '')
        is_id = bool(search_text) and len(search_text) <= 30 and re.fullmatch(r'[0-9A-Za-z\-/]+', search_text)
        is_name = 3 <= len(raw_text) <= 60 and re.fullmatch(r"[A-Za-z][A-Za-z .'\-]*", raw_text)
        if not is_id and not is_name:
            return jsonify({'success': True, 'type': 'invalid'})

        # Application No / CNIC first; fall back to Borrower Name when the text looks like a name.
        records = find_applications(search_text) if is_id else []
        by_name = not records and is_name
        if by_name:
            records = find_applications_by_name(raw_text)
            search_text = raw_text

        if not records:
            return jsonify({'success': True, 'type': 'not-found', 'query': search_text})

        if len(records) > 1:
            return jsonify({
                'success': True,
                'type': 'multiple',
                'query': search_text,
                'limited': by_name and len(records) >= NAME_SEARCH_LIMIT,
                'matches': [
                    {
                        'application_no': r.get('Application_No'),
                        'borrower_name': r.get('Borrower_Name'),
                        'cnic': r.get('CNIC'),
                        'application_date': _fmt_date(r.get('ApplicationDate')),
                        'status_label': APPLICATION_STATUS_LABELS.get(str(r.get('status')), 'Not Received'),
                    }
                    for r in records
                ]
            })

        return jsonify({'success': True, 'type': 'application', 'application': _application_details(records[0])})

    except Exception as e:
        print('application-assistant lookup exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Something went wrong while looking up the application'}), 500
