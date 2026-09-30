from imports import *
from application import application
from itsdangerous import BadSignature


REPORT_CONFIG_ROUTE = '/management-report-configuration'

# Signed link (in the report email) that opens the sent report HTML in a browser tab without logging in.
REPORT_LINK_MAX_AGE_DAYS = int(os.getenv('REPORT_LINK_MAX_AGE_DAYS', 90))
report_link_signer = URLSafeTimedSerializer(application.config['SECRET_KEY'], salt='kft-report-snapshot')


def report_snapshot_url(snapshot_id):
    return url_for('view_report_snapshot', token=report_link_signer.dumps(int(snapshot_id)), _external=True)


def can_manage_reports():
    return is_login() and (
        str(session.get('rights')) in ['3', '4']
        or PermissionHelper.has_permission(get_current_user_id(), REPORT_CONFIG_ROUTE)
    )


def _parse_group(payload):
    report_type = payload.get('report_type')
    if report_type not in (REPORT_MANAGEMENT, REPORT_REGIONAL):
        return None, None, 'Invalid report type'
    if report_type == REPORT_MANAGEMENT:
        return report_type, None, None
    try:
        return report_type, int(payload.get('ncd_id')), None
    except (TypeError, ValueError):
        return None, None, 'Invalid region'


def _report_filename(group, data):
    period = f"{MONTHS[data['meta']['reportMonth'] - 1]}_{data['meta']['reportYear']}"
    name = 'Management_Report' if group['region'] is None else 'Regional_Report_' + group['region']
    return re.sub(r'[^A-Za-z0-9_\-]+', '_', f"KFT_{name}_{period}") + '.html'


def _region_has_data(group, data):
    return group['region'] is None or group['region'] in data['regions']


@application.route(REPORT_CONFIG_ROUTE)
def management_report_configuration():
    if not can_manage_reports():
        return redirect(url_for('login'))
    try:
        data = get_kft_dashboard_data()
        groups = get_report_groups()
        for g in groups:
            g['has_data'] = bool(data) and _region_has_data(g, data)
            if g['last_sent'] and g['last_sent'].get('snapshot_id'):
                g['last_sent']['report_url'] = report_snapshot_url(g['last_sent']['snapshot_id'])
        period = f"{MONTHS_LONG[data['meta']['reportMonth'] - 1]} {data['meta']['reportYear']}" if data else None
        return render_template('management_report_configuration.html', groups=groups, report_period=period)
    except Exception as e:
        print('management report configuration exception:- ', str(e))
        return redirect(url_for('index'))


@application.route(REPORT_CONFIG_ROUTE + '/recipients', methods=['POST'])
def save_management_report_recipients():
    if not can_manage_reports():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    payload = request.get_json(silent=True) or {}
    report_type, ncd_id, error = _parse_group(payload)
    if error:
        return jsonify({'success': False, 'error': error}), 400

    emails, seen = [], set()
    for raw in payload.get('emails') or []:
        email = str(raw).strip()
        if not email:
            continue
        if not is_valid_email(email):
            return jsonify({'success': False, 'error': f'Invalid email address: {email}'}), 400
        if email.lower() not in seen:
            seen.add(email.lower())
            emails.append(email)

    if not get_report_group(report_type, ncd_id):
        return jsonify({'success': False, 'error': 'Report group not found'}), 404

    save_report_recipients(report_type, ncd_id, emails, get_current_user_id())
    saved = get_report_group(report_type, ncd_id)['emails']
    if [e.lower() for e in saved] != [e.lower() for e in emails]:
        return jsonify({'success': False, 'error': 'Could not save the recipients, please try again'}), 500
    return jsonify({'success': True, 'emails': saved})


@application.route(REPORT_CONFIG_ROUTE + '/preview')
def preview_management_report():
    if not can_manage_reports():
        return redirect(url_for('login'))
    report_type, ncd_id, error = _parse_group(request.args)
    group = get_report_group(report_type, ncd_id) if not error else None
    data = get_kft_dashboard_data()
    if not group or not data:
        abort(404)
    return render_kft_report(data, group['region'], request.args.get('commentary', ''))


@application.route('/reports/view/<token>')
def view_report_snapshot(token):
    # Public on purpose: email recipients are not system users. The signed token is the access check.
    try:
        snapshot_id = report_link_signer.loads(token, max_age=REPORT_LINK_MAX_AGE_DAYS * 24 * 60 * 60)
    except SignatureExpired:
        return 'This report link has expired. Please open the HTML file attached to the email.', 410
    except BadSignature:
        abort(404)
    report_html = get_report_snapshot_html(snapshot_id)
    if not report_html:
        abort(404)
    return Response(report_html, mimetype='text/html')


@application.route(REPORT_CONFIG_ROUTE + '/send', methods=['POST'])
def send_management_reports():
    if not can_manage_reports():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    payload = request.get_json(silent=True) or {}
    commentary = (payload.get('commentary') or '').strip()
    data = get_kft_dashboard_data(force_refresh=True)
    if not data:
        return jsonify({'success': False, 'error': 'No post-disbursement data available'}), 404

    groups = get_report_groups()
    if payload.get('all'):
        targets = [g for g in groups if g['emails'] and _region_has_data(g, data)]
    else:
        report_type, ncd_id, error = _parse_group(payload)
        if error:
            return jsonify({'success': False, 'error': error}), 400
        targets = [g for g in groups if g['report_type'] == report_type and g['ncd_id'] == ncd_id]
        if not targets:
            return jsonify({'success': False, 'error': 'Report group not found'}), 404
        if not targets[0]['emails']:
            return jsonify({'success': False, 'error': 'Add at least one email address before sending'}), 400
        if not _region_has_data(targets[0], data):
            return jsonify({'success': False, 'error': 'No portfolio data is mapped to this region'}), 400

    period = f"{MONTHS_LONG[data['meta']['reportMonth'] - 1]} {data['meta']['reportYear']}"
    from Model_Email import send_email_with_attachments

    results = []
    for group in targets:
        error_message = None
        snapshot_id = None
        try:
            context = build_report_context(data, group['region'], commentary)
            report_html = render_template('kft_report.html', r=context)
            snapshot_id = save_report_snapshot(group['report_type'], group['ncd_id'], period, report_html,
                                               get_current_user_id())
            report_url = report_snapshot_url(snapshot_id) if snapshot_id else None
            body_html = render_template('kft_report_email.html', r=context, report_name=group['name'],
                                        report_url=report_url)
            subject = f"KFT {group['name'] if group['region'] is None else 'Regional Report – ' + group['name']} – {period}"
            sent = send_email_with_attachments(
                subject=subject,
                email_list=group['emails'],
                message=None,
                html_message=body_html,
                attachments=[{
                    'filename': _report_filename(group, data),
                    'content': report_html.encode('utf-8'),
                    'content_type': 'text/html; charset=utf-8',
                }],
            )
            if not sent:
                error_message = 'Email server rejected the message'
        except Exception as e:
            print('send management report exception:- ', str(e))
            error_message = str(e)

        log_report_email(group['report_type'], group['ncd_id'], period, group['emails'], commentary,
                         error_message is None, error_message, get_current_user_id(), snapshot_id)
        results.append({'name': group['name'], 'recipients': group['emails'],
                        'success': error_message is None, 'error': error_message})

    return jsonify({'success': all(r['success'] for r in results), 'results': results})
