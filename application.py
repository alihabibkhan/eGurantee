import os

from imports import *
from flask_mail import Mail, Message

application = Flask(__name__)


logging.basicConfig(level=logging.DEBUG)

application.config['SECRET_KEY'] = "Your_secret_string"
application.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
application.config['SESSION_COOKIE_SECURE'] = True
application.config['UPLOAD_FOLDER'] = os.path.join(application.root_path, 'uploads')
application.config['ALLOWED_EXTENSIONS'] = {'xlsx'}

# Email Configuration (using Gmail as an example)
application.config['MAIL_SERVER'] = 'smtp.gmail.com'
application.config['MAIL_PORT'] = 587
application.config['MAIL_USE_TLS'] = True
application.config['MAIL_USE_SSL'] = False
application.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
application.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
application.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(application)

# Ensure upload folder exists
os.makedirs(application.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in application.config['ALLOWED_EXTENSIONS']


# --- Custom Filters ---
@application.template_filter('format_currency')
def format_currency(value):
    if value is None:
        return "0.00"
    return "{:,.2f}".format(float(value))


@application.template_filter('format_date')
def format_date(value):
    if value is None:
        return ""
    return value.strftime('%d-%m-%Y')


@application.template_filter('date_format')
def date_format(value):
    """Format a datetime object to YYYY-MM-DD for HTML date input."""
    if value is None:
        return ''
    try:
        return value.strftime('%Y-%m-%d')
    except (AttributeError, ValueError):
        return ''


@application.template_filter('month_year_short')
def month_year_short(value):
    """
    Format a date or datetime as 'Mon-YY', e.g. 'Jan-25' or 'Oct-25'.
    """
    if not value:
        return ""
    try:
        return value.strftime("%b-%y").title()
    except AttributeError:
        return value


# --- Custom Error Handlers ---
@application.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@application.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


@application.context_processor
def utility_processor():
    announcments_data = get_active_marquee_content(limit=50)

    return {
        'announcments_data': announcments_data,
        'logged_in_user': str(get_current_user_id()),
        'PermissionHelper': PermissionHelper
    }


# Add this route to serve files from uploads directory
@application.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve files from the uploads directory"""
    try:
        # Get the upload folder path from config
        upload_folder = application.config.get('UPLOAD_FOLDER', '/opt/render/project/src/uploads')

        # Security: prevent directory traversal attacks
        if '..' in filename or filename.startswith('/'):
            abort(404)

        # Send the file
        return send_from_directory(upload_folder, filename)
    except Exception as e:
        print(f"Error serving file {filename}: {str(e)}")
        abort(404)


@application.route('/')
@application.route('/Index')
@application.route('/index')
@application.route('/Dashboard')
@application.route('/dashboard')
def index():
    try:
        if is_login():
            content = {
                'is_admin':is_admin(),
                'is_reviewer': is_reviewer(),
                'is_approver': is_approver(),
                'is_executive_approver': is_executive_approver(),
                'get_disbursed_loan_count': get_disbursed_loan_count(),
                'get_outstanding_loans': get_outstanding_loans(),
                'get_non_performing_loan_count': get_non_performing_loan_count(),
                'total_loan_beneficiary_count': total_loan_beneficiary_count(),
                'area_metrics': get_loan_details_by_national_council(),
                'get_latest_portfolio_date': get_latest_portfolio_date()
            }
            return render_template('dashboard.html', result=content)
    except Exception as e:
        print('dashboard exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/dashboard/kft-data')
def kft_dashboard_data():
    if not is_login():
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    try:
        data = get_kft_dashboard_data(force_refresh=request.args.get('refresh') == '1')
        if data is None:
            return jsonify({'success': False, 'error': 'No post-disbursement data available'}), 404
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        print('kft dashboard data exception:- ', str(e))
        return jsonify({'success': False, 'error': str(e)}), 500


AWAITING_ROLE_NAMES = {'1': 'Reviewer', '2': 'Approver', '3': 'Executive Approver', '4': 'Admin', '5': 'Executive'}
# Statuses that are waiting for this role's own action (highlighted on the page); 'X' = executive approval
AWAITING_MY_ACTION = {'1': ['1'], '2': ['5', '6', '7', '8'], '3': ['X'], '5': ['5', '6', '7', '8', 'X']}


def can_view_awaiting_service():
    # Reviewer, Approver, Executive Approver, Admin and Executive all open the page (scoped in the model);
    # anyone else needs the /awaiting-Service web permission.
    return str(session.get('rights')) in AWAITING_ROLE_NAMES or \
        PermissionHelper.has_permission(str(get_current_user_id()), '/awaiting-Service')


@application.route('/awaiting-Service/count')
def awaiting_service_count():
    # Badge on the dashboard's "Awaiting Services" button: pending applications only, in the user's own scope.
    if not is_login():
        return jsonify({'success': False}), 401
    if not can_view_awaiting_service():
        return jsonify({'success': False}), 403
    from Model_PreDisbursement import get_awaiting_pending_count
    return jsonify({'success': True, 'total': get_awaiting_pending_count()})


@application.route('/awaiting-Service')
def awaiting_service():
    if not is_login():
        return redirect(url_for('login'))
    if not can_view_awaiting_service():
        flash('You do not have permission to view Awaiting Services.', 'danger')
        return redirect(url_for('dashboard'))
    viewer = {'mine': AWAITING_MY_ACTION.get(str(session.get('rights')), [])}
    return render_template('pending_applications.html', viewer=viewer)


@application.route('/awaiting-Service/data')
def awaiting_service_data():
    if not is_login():
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    if not can_view_awaiting_service():
        return jsonify({'success': False, 'error': 'Not allowed'}), 403
    from Model_PreDisbursement import get_awaiting_services_rows
    try:
        rows = []
        for r in get_awaiting_services_rows():
            rows.append({
                'id': r['id'],
                'app_no': r['app_no'],
                'borrower': r['borrower'],
                'cnic': r['cnic'],
                'product': r['product'] or 'Unknown',
                'amount': float(r['amount']) if r['amount'] is not None else None,
                'status': str(r['status']),
                'exec_pending': int(r['exec_pending']),
                'branch': r['branch'] or 'Unassigned',
                'council': r['council'] or 'Unassigned',
                'uploaded_date': r['uploaded_date'].isoformat() if r['uploaded_date'] else None,
                'reviewed_date': r['reviewed_date'].isoformat() if r['reviewed_date'] else None,
                'reviewed_by': r['reviewed_by'],
                'decision_date': r['decision_date'].isoformat() if r['decision_date'] else None,
                'decided_by': r['decided_by'],
            })
        return jsonify({'success': True, 'rows': rows, 'today': datetime.now().date().isoformat()})
    except Exception as e:
        print('awaiting service data exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not load applications'}), 500



@application.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy.html')

from App_Auth import *
from App_Users import *
from App_Budget import *
from App_Branches import *
from App_PreDisbursement import *
from App_PostDisbursement import *
from App_File_Uploading_Validation import *
from App_Email import *
from App_LoanProducts import *
from App_Occupations import *
from App_ExperienceRanges import *
from App_LoanMetrics import *
from App_Summary import *
from App_Bank_Details import *
from App_Bank_Entry import *
from App_User_Service_Hours import *
from App_Reports import *
from App_Bank_Distribution import *
from App_National_Council_Distribution import *
from App_KFT_Distribution import *
from App_Branch_Role import *
from App_User_Self_Update_Community import *
from App_Meeting_Setup import *
from App_Announcements import *
from Manage_Web_Permission import *
from Manage_User_Permission import *
from App_Application_Assistant import *
from App_Report_Configuration import *

if __name__ == '__main__':
    application.run(debug=True, port=8000)

