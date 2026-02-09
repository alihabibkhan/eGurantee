import os

from imports import *
from flask_mail import Mail, Message

application = Flask(__name__)
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
        'announcments_data': announcments_data
    }


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


@application.route('/awaiting-Service')
def awaiting_service():
    # Fetch distinct national council distributions for table headers
    query_distributions = """
        SELECT DISTINCT ncd.national_council_distribution_name
        FROM tbl_national_council_distribution ncd
        INNER JOIN tbl_branches b
            ON b.national_council_distribution = ncd.national_council_distribution_id
        WHERE b.live_branch = '1'
        ORDER BY ncd.national_council_distribution_name
    """
    distributions = [row['national_council_distribution_name'] for row in fetch_records(query_distributions)]

    # Query for pending applications
    query_pending = """
        SELECT 
            ncd.national_council_distribution_name AS national_council_distribution,
            CASE 
                WHEN pdt."LoanProductCode" LIKE '%Enterprise%' THEN 'Enterprise'
                WHEN pdt."LoanProductCode" = 'Student' THEN 'Student'
                ELSE 'Other'
            END AS loan_product_category,
            CASE 
                WHEN u.rights = '1' THEN 'Reviewer'
                WHEN u.rights = '2' THEN 'Approver'
                ELSE 'Unknown'
            END AS user_role,
            COUNT(*) AS pending_application_count
        FROM tbl_pre_disbursement_temp pdt
        INNER JOIN tbl_branches b 
            ON pdt."Branch_Name" LIKE CONCAT('%', b."branch_code", '%') 
            AND b."live_branch" = '1'
        INNER JOIN tbl_users u 
            ON u.assigned_branch = b.role
            AND u."active" = '1' 
            AND u.rights IN ('1', '2')
        LEFT JOIN tbl_national_council_distribution ncd
            ON b.national_council_distribution = ncd.national_council_distribution_id
        WHERE pdt.Status = '1'
        GROUP BY 
            ncd.national_council_distribution_name,
            CASE 
                WHEN pdt."LoanProductCode" LIKE '%Enterprise%' THEN 'Enterprise'
                WHEN pdt."LoanProductCode" = 'Student' THEN 'Student'
                ELSE 'Other'
            END,
            u.rights
        ORDER BY 
            ncd.national_council_distribution_name,
            loan_product_category,
            user_role
    """
    records_pending = fetch_records(query_pending)
    print(records_pending)

    # Organize data for pending applications
    data_pending = {}
    for record in records_pending:
        dist = record['national_council_distribution'] or 'Unknown'
        prod = record['loan_product_category']
        role = record['user_role']
        count = record['pending_application_count']
        key = (dist, prod, role)
        data_pending[key] = data_pending.get(key, 0) + int(count)

    print(data_pending)

    # Query for agreed applications
    query_agreed = """
        SELECT 
            ncd.national_council_distribution_name AS national_council_distribution,
            COUNT(*) AS agreed_application_count
        FROM tbl_pre_disbursement_temp pdt
        INNER JOIN tbl_branches b 
            ON pdt."Branch_Name" LIKE CONCAT('%', b."branch_code", '%') 
            AND b."live_branch" = '1'
        LEFT JOIN tbl_national_council_distribution ncd
            ON b.national_council_distribution = ncd.national_council_distribution_id
        WHERE pdt.Status IN ('2', '5')
            AND DATE_TRUNC('month', pdt.approved_date) = DATE_TRUNC('month', CURRENT_DATE)
        GROUP BY ncd.national_council_distribution_name
        ORDER BY ncd.national_council_distribution_name
    """
    records_agreed = fetch_records(query_agreed)
    print(records_agreed)

    # Organize data for agreed applications
    data_agreed = {}
    for record in records_agreed:
        dist = record['national_council_distribution'] or 'Unknown'
        count = record['agreed_application_count']
        data_agreed[(dist,)] = data_agreed.get((dist,), 0) + int(count)

    print(data_agreed)

    # Query for rejected applications
    query_rejected = """
        SELECT 
            ncd.national_council_distribution_name AS national_council_distribution,
            COUNT(*) AS rejected_application_count
        FROM tbl_pre_disbursement_temp pdt
        INNER JOIN tbl_branches b 
            ON pdt."Branch_Name" LIKE CONCAT('%', b."branch_code", '%') 
            AND b."live_branch" = '1'
        LEFT JOIN tbl_national_council_distribution ncd
            ON b.national_council_distribution = ncd.national_council_distribution_id
        WHERE pdt.Status IN ('3', '6')
            AND DATE_TRUNC('month', pdt.approved_date) = DATE_TRUNC('month', CURRENT_DATE)
        GROUP BY ncd.national_council_distribution_name
        ORDER BY ncd.national_council_distribution_name
    """
    records_rejected = fetch_records(query_rejected)
    print(records_rejected)

    # Organize data for rejected applications
    data_rejected = {}
    for record in records_rejected:
        dist = record['national_council_distribution'] or 'Unknown'
        count = record['rejected_application_count']
        data_rejected[(dist,)] = data_rejected.get((dist,), 0) + int(count)

    print(data_rejected)
    return render_template('pending_applications.html', 
                         data_pending=data_pending, 
                         data_agreed=data_agreed, 
                         data_rejected=data_rejected, 
                         distributions=distributions)


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

if __name__ == '__main__':
    application.run(debug=True, port=8080)

