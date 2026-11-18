from imports import *
from application import application
from decimal import Decimal
from Model_PLAR import *

PLAR_EVIDENCE_DIR = os.path.join(application.root_path, 'plar_evidence')   # outside /uploads, served only through a login check

# ---------------------------------------------------------------------------------------------
# PLAR - Post Loan-Disbursement Assurance Review (web routes)
#   Dashboard                : Executive Approver (3), Admin (4), or the /plar-dashboard permission
#   Work screens             : the same roles, or the /plar-review permission (PLAR reviewer)
#   Saving a review / sample : Admin (4) or the /plar-review permission
# ---------------------------------------------------------------------------------------------


def plar_can_dashboard():
    return is_login() and (get_current_user_role() in ['3', '4']
                           or PermissionHelper.has_permission(get_current_user_id(), '/plar-dashboard'))


def plar_can_view():
    return is_login() and (get_current_user_role() in ['3', '4']
                           or PermissionHelper.has_permission(get_current_user_id(), '/plar-review'))


def plar_can_review():
    return is_login() and (get_current_user_role() == '4'
                           or PermissionHelper.has_permission(get_current_user_id(), '/plar-review'))


def plar_json_safe(value):
    """Make dates, decimals and nested rows JSON friendly."""
    if isinstance(value, dict):
        return {k: plar_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plar_json_safe(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat() if value.year > 1901 else None
    if isinstance(value, Decimal):
        return float(value)
    return value


def plar_page_guard(check):
    """None when allowed, otherwise the redirect to send."""
    if not is_login():
        return redirect(url_for('login'))
    if not check():
        flash('You do not have permission to open this page.', 'danger')
        return redirect(url_for('index'))
    return None


def plar_month_from_request(data=None):
    raw = (data or {}).get('month') or request.args.get('month')
    if raw:
        return plar_month_start(raw)
    months = get_plar_months()
    return plar_month_start(months[0]['month']) if months else date.today().replace(day=1)


# ---------------------------------------------------------------- 1. Reconciliation
@application.route('/plar/reconciliation')
def plar_reconciliation():
    blocked = plar_page_guard(plar_can_view)
    if blocked:
        return blocked
    return render_template('plar_reconciliation.html', result={
        'months': get_plar_months(), 'can_review': plar_can_review(), 'active': 'reconciliation',
        'can_dashboard': plar_can_dashboard()})


@application.route('/plar/reconciliation/data', methods=['POST'])
def plar_reconciliation_data():
    if not plar_can_view():
        return jsonify({'success': False, 'error': 'Not allowed'}), 403
    try:
        month = plar_month_from_request(request.get_json(silent=True))
        rows = get_plar_population(month)
        not_disbursed = get_plar_approved_not_disbursed(month, rows)
        for r in not_disbursed:
            r['days_waiting'] = (date.today() - r['approved_date'].date()).days if r['approved_date'] else None
        return jsonify(plar_json_safe({'success': True, 'month': month.strftime('%Y-%m'), 'rows': rows,
                                       'not_disbursed': not_disbursed, 'summary': plar_summary(rows, not_disbursed)}))
    except Exception as e:
        print('plar reconciliation exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not load the reconciliation'}), 500


# ---------------------------------------------------------------- 2. Exceptions
@application.route('/plar/exceptions')
def plar_exceptions():
    blocked = plar_page_guard(plar_can_view)
    if blocked:
        return blocked
    return render_template('plar_exceptions.html', result={
        'months': get_plar_months(), 'can_review': plar_can_review(), 'active': 'exceptions',
        'can_dashboard': plar_can_dashboard(),
        'codes': [{'code': k, 'name': v[0], 'severity': v[1]} for k, v in PLAR_EXCEPTIONS.items()]})


@application.route('/plar/exceptions/data', methods=['POST'])
def plar_exceptions_data():
    if not plar_can_view():
        return jsonify({'success': False, 'error': 'Not allowed'}), 403
    try:
        month = plar_month_from_request(request.get_json(silent=True))
        records, rows = get_plar_exception_records(month)
        return jsonify(plar_json_safe({'success': True, 'month': month.strftime('%Y-%m'), 'records': records,
                                       'population': len(rows), 'cases': plar_case_summary(records)}))
    except Exception as e:
        print('plar exceptions exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not load the exceptions'}), 500


@application.route('/plar/exceptions/resolve', methods=['POST'])
def plar_exceptions_resolve():
    """Resolve (note required, file optional) or reopen one exception. Multipart form."""
    if not plar_can_review():
        return jsonify({'success': False, 'error': 'Only a PLAR reviewer can resolve an exception.'}), 403
    try:
        month = plar_month_start(request.form.get('month'))
        pre_id = request.form.get('pre_disb_temp_id')
        pre_id = int(pre_id) if str(pre_id or '').isdigit() else None
        f = request.files.get('file')
        name = None
        if f and f.filename:
            name = secure_filename(f.filename)
            if '.' not in name or name.rsplit('.', 1)[1].lower() not in PLAR_EVIDENCE_EXTENSIONS:
                return jsonify({'success': False, 'error': 'Allowed files: ' + ', '.join(sorted(PLAR_EVIDENCE_EXTENSIONS))}), 400
        case_id, error = set_plar_case_state(month, str(request.form.get('code') or ''), str(request.form.get('loan_no') or ''),
                                             pre_id, str(request.form.get('status') or ''), request.form.get('note'))
        if error:
            return jsonify({'success': False, 'error': error}), 400
        if name:
            folder = os.path.join(PLAR_EVIDENCE_DIR, 'exc', str(case_id))
            os.makedirs(folder, exist_ok=True)
            stored = f"{datetime.now():%Y%m%d%H%M%S}_{name}"
            f.save(os.path.join(folder, stored))
            if os.path.getsize(os.path.join(folder, stored)) > PLAR_EVIDENCE_MAX_BYTES:
                os.remove(os.path.join(folder, stored))
                return jsonify({'success': False, 'error': 'The note was saved but the file is larger than 10 MB.'}), 400
            add_plar_case_evidence(case_id, name, f'exc/{case_id}/{stored}')
        return jsonify({'success': True})
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid request.'}), 400
    except Exception as e:
        print('plar exception resolve exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not save.'}), 500


@application.route('/plar/exceptions/evidence/<int:evidence_id>')
def plar_exceptions_evidence_download(evidence_id):
    if not plar_can_view():
        abort(403)
    rec = get_plar_case_evidence_file(evidence_id)
    if not rec or not re.fullmatch(r'exc/\d+/[\w.\-]+', rec['file_path']):
        abort(404)
    _exc, case_id, stored = rec['file_path'].split('/')
    return send_from_directory(os.path.join(PLAR_EVIDENCE_DIR, 'exc', case_id), stored, as_attachment=True,
                               download_name=rec['file_name'])


# ---------------------------------------------------------------- 3. Sampling
@application.route('/plar/sampling')
def plar_sampling():
    blocked = plar_page_guard(plar_can_view)
    if blocked:
        return blocked
    return render_template('plar_sampling.html', result={
        'months': get_plar_months(), 'can_review': plar_can_review(), 'active': 'sampling',
        'can_dashboard': plar_can_dashboard(), 'min_pct': PLAR_MIN_PCT, 'max_pct': PLAR_MAX_PCT,
        'min_cases': PLAR_MIN_CASES})


@application.route('/plar/sampling/data', methods=['POST'])
def plar_sampling_data():
    if not plar_can_view():
        return jsonify({'success': False, 'error': 'Not allowed'}), 403
    try:
        month = plar_month_from_request(request.get_json(silent=True))
        return jsonify(plar_json_safe({'success': True, 'month': month.strftime('%Y-%m'),
                                       **plar_sampling_overview(month)}))
    except Exception as e:
        print('plar sampling exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not load the sample'}), 500


@application.route('/plar/sampling/pct', methods=['POST'])
def plar_sampling_pct():
    if not plar_can_review():
        return jsonify({'success': False, 'error': 'Only a PLAR reviewer can change the sample %.'}), 403
    data = request.get_json(silent=True) or {}
    try:
        error = set_plar_region_pct(plar_month_from_request(data), data.get('region_id'), data.get('pct'))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid request.'}), 400
    if error:
        return jsonify({'success': False, 'error': error}), 400
    return jsonify({'success': True})


@application.route('/plar/sampling/generate', methods=['POST'])
def plar_sampling_generate():
    if not plar_can_review():
        return jsonify({'success': False, 'error': 'Only a PLAR reviewer can generate the sample.'}), 403
    try:
        count, error = generate_plar_sample(plar_month_from_request(request.get_json(silent=True)))
    except Exception as e:
        print('plar sample generate exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not generate the sample.'}), 500
    if error:
        return jsonify({'success': False, 'error': error}), 400
    return jsonify({'success': True, 'count': count})


# ---------------------------------------------------------------- 4. Case review
@application.route('/plar/review')
def plar_review():
    blocked = plar_page_guard(plar_can_view)
    if blocked:
        return blocked
    return render_template('plar_review.html', result={
        'months': get_plar_months(), 'can_review': plar_can_review(), 'active': 'review',
        'can_dashboard': plar_can_dashboard(), 'checks': [{'key': k, 'label': l, 'optional': k in PLAR_OPTIONAL_CHECKS}
                                                          for k, l, _c in PLAR_CHECKS],
        'check_values': PLAR_CHECK_VALUES, 'statuses': PLAR_REVIEW_STATUSES, 'categories': PLAR_CATEGORIES,
        'severities': PLAR_SEVERITIES,
        'users': fetch_records("SELECT user_id, name FROM tbl_users WHERE active = 1 ORDER BY name", is_print=False),
        'sample_id': request.args.get('sample_id', ''), 'month': request.args.get('month', '')})


@application.route('/plar/review/list', methods=['POST'])
def plar_review_list():
    if not plar_can_view():
        return jsonify({'success': False, 'error': 'Not allowed'}), 403
    try:
        month = plar_month_from_request(request.get_json(silent=True))
        run = get_plar_run(month)
        return jsonify(plar_json_safe({'success': True, 'month': month.strftime('%Y-%m'),
                                       'locked': bool(run and run['sample_locked']), 'sample': get_plar_sample(run)}))
    except Exception as e:
        print('plar review list exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not load the sample'}), 500


@application.route('/plar/review/case', methods=['POST'])
def plar_review_case():
    if not plar_can_view():
        return jsonify({'success': False, 'error': 'Not allowed'}), 403
    try:
        case = get_plar_case((request.get_json(silent=True) or {}).get('sample_id'))
        if not case:
            return jsonify({'success': False, 'error': 'Case not found'}), 404
        conflict = plar_reviewer_conflict(case)
        out = dict(case)
        out['conflict'] = conflict
        out['can_edit'] = plar_can_review() and not conflict
        return jsonify(plar_json_safe({'success': True, **out}))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid request.'}), 400
    except Exception as e:
        print('plar review case exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not load the case'}), 500


@application.route('/plar/review/save', methods=['POST'])
def plar_review_save():
    if not plar_can_review():
        return jsonify({'success': False, 'error': 'Only a PLAR reviewer can save a review.'}), 403
    data = request.get_json(silent=True) or {}
    try:
        case = get_plar_case(data.get('sample_id'))
        if not case:
            return jsonify({'success': False, 'error': 'Case not found'}), 404
        if plar_reviewer_conflict(case):
            return jsonify({'success': False, 'error': 'You approved or reviewed this case in EGS, so you cannot review it here.'}), 403
        clean, error = validate_plar_review(data, case)
        if error:
            return jsonify({'success': False, 'error': error}), 400
        owner_name, due, owner_user = str(data.get('owner_name') or '').strip(), None, None
        if clean['status'] in ('Issue Identified', 'Clarification Required') and not case['actions']:
            try:
                due = datetime.strptime(str(data.get('due_date') or ''), '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'error': 'Set the corrective-action deadline.'}), 400
            if not owner_name:
                return jsonify({'success': False, 'error': 'Name the responsible official for the corrective action.'}), 400
            if due < date.today():
                return jsonify({'success': False, 'error': 'The deadline cannot be in the past.'}), 400
            if str(data.get('owner_user_id') or '').isdigit():
                owner_user = int(data['owner_user_id'])
        action_id = save_plar_review(data.get('sample_id'), clean, case, owner_name, owner_user, due)
        return jsonify({'success': True, 'action_id': action_id})
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid request.'}), 400
    except Exception as e:
        print('plar review save exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not save the review.'}), 500


# ---------------------------------------------------------------- 5. Corrective actions


@application.route('/plar/actions')
def plar_actions():
    blocked = plar_page_guard(plar_can_view)
    if blocked:
        return blocked
    return render_template('plar_actions.html', result={
        'can_review': plar_can_review(), 'active': 'actions', 'can_dashboard': plar_can_dashboard(),
        'statuses': PLAR_ACTION_STATUSES})


@application.route('/plar/actions/data', methods=['POST'])
def plar_actions_data():
    if not plar_can_view():
        return jsonify({'success': False, 'error': 'Not allowed'}), 403
    try:
        return jsonify(plar_json_safe({'success': True, 'actions': get_plar_actions()}))
    except Exception as e:
        print('plar actions exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not load the actions'}), 500


@application.route('/plar/actions/status', methods=['POST'])
def plar_actions_status():
    if not plar_can_review():
        return jsonify({'success': False, 'error': 'Only a PLAR reviewer can change an action.'}), 403
    data = request.get_json(silent=True) or {}
    try:
        error = update_plar_action_status(data.get('action_id'), str(data.get('status') or ''))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid request.'}), 400
    if error:
        return jsonify({'success': False, 'error': error}), 400
    return jsonify({'success': True})


@application.route('/plar/actions/evidence', methods=['POST'])
def plar_actions_evidence_upload():
    if not plar_can_review():
        return jsonify({'success': False, 'error': 'Only a PLAR reviewer can upload evidence.'}), 403
    try:
        action_id = int(request.form.get('action_id'))
        f = request.files.get('file')
        if not f or not f.filename:
            return jsonify({'success': False, 'error': 'Choose a file.'}), 400
        name = secure_filename(f.filename)
        if '.' not in name or name.rsplit('.', 1)[1].lower() not in PLAR_EVIDENCE_EXTENSIONS:
            return jsonify({'success': False, 'error': 'Allowed files: ' + ', '.join(sorted(PLAR_EVIDENCE_EXTENSIONS))}), 400
        if not fetch_records('SELECT 1 FROM tbl_plar_action WHERE action_id = %s', is_print=False, params=(action_id,)):
            return jsonify({'success': False, 'error': 'Action not found.'}), 404
        folder = os.path.join(PLAR_EVIDENCE_DIR, str(action_id))
        os.makedirs(folder, exist_ok=True)
        stored = f"{datetime.now():%Y%m%d%H%M%S}_{name}"
        f.save(os.path.join(folder, stored))
        if os.path.getsize(os.path.join(folder, stored)) > PLAR_EVIDENCE_MAX_BYTES:
            os.remove(os.path.join(folder, stored))
            return jsonify({'success': False, 'error': 'The file is larger than 10 MB.'}), 400
        add_plar_evidence(action_id, name, f'{action_id}/{stored}')
        return jsonify({'success': True})
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid request.'}), 400
    except Exception as e:
        print('plar evidence upload exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not save the file.'}), 500


@application.route('/plar/actions/evidence/<int:evidence_id>')
def plar_actions_evidence_download(evidence_id):
    if not plar_can_view():
        abort(403)
    rec = get_plar_evidence_file(evidence_id)
    if not rec:
        abort(404)
    path = rec['file_path']
    if not re.fullmatch(r'\d+/[\w.\-]+', path):      # only "<action id>/<stored name>" is ever written
        abort(404)
    folder, stored = path.split('/')
    return send_from_directory(os.path.join(PLAR_EVIDENCE_DIR, folder), stored, as_attachment=True,
                               download_name=rec['file_name'])


@application.route('/plar/actions/remind', methods=['POST'])
def plar_actions_remind():
    if not plar_can_review():
        return jsonify({'success': False, 'error': 'Only a PLAR reviewer can send reminders.'}), 403
    try:
        actions, emails, no_user = remind_plar_actions()
        return jsonify({'success': True, 'actions': actions, 'emails': emails, 'no_user': no_user})
    except Exception as e:
        print('plar remind exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not send the reminders.'}), 500


@application.route('/plar/actions/escalate', methods=['POST'])
def plar_actions_escalate():
    if not plar_can_review():
        return jsonify({'success': False, 'error': 'Only a PLAR reviewer can escalate.'}), 403
    try:
        count, sent, recipients = escalate_plar_actions()
        return jsonify({'success': True, 'count': count, 'emailed': sent, 'recipients': len(recipients)})
    except Exception as e:
        print('plar escalate exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not escalate.'}), 500


# ---------------------------------------------------------------- Audit trail
@application.route('/plar/audit')
def plar_audit_page():
    blocked = plar_page_guard(plar_can_view)
    if blocked:
        return blocked
    return render_template('plar_audit.html', result={'active': 'audit', 'can_dashboard': plar_can_dashboard(),
                                                      'can_review': plar_can_review()})


@application.route('/plar/audit/data', methods=['POST'])
def plar_audit_data():
    if not plar_can_view():
        return jsonify({'success': False, 'error': 'Not allowed'}), 403
    return jsonify(plar_json_safe({'success': True, 'rows': get_plar_audit()}))


# ---------------------------------------------------------------- Dashboard (Executive Approver, Admin)
@application.route('/plar/dashboard')
def plar_dashboard():
    blocked = plar_page_guard(plar_can_dashboard)
    if blocked:
        return blocked
    return render_template('plar_dashboard.html', result={
        'months': get_plar_months(), 'active': 'dashboard', 'can_dashboard': True, 'can_review': plar_can_review()})


@application.route('/plar/dashboard/data', methods=['POST'])
def plar_dashboard_data():
    if not plar_can_dashboard():
        return jsonify({'success': False, 'error': 'Not allowed'}), 403
    try:
        month = plar_month_from_request(request.get_json(silent=True))
        return jsonify(plar_json_safe({'success': True, 'month': month.strftime('%Y-%m'), **get_plar_dashboard(month)}))
    except Exception as e:
        print('plar dashboard exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not load the dashboard'}), 500
