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
application.config['MAIL_USERNAME'] = 'alihabib202299@gmail.com'  # Replace with your email
application.config['MAIL_PASSWORD'] = 'yaly ftoq rdtg syno'     # Use App Password for Gmail with 2FA
application.config['MAIL_DEFAULT_SENDER'] = 'zali9261@gmail.com'

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


# --- Custom Error Handlers ---
@application.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@application.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


@application.route('/')
@application.route('/Index')
@application.route('/index')
@application.route('/Dashboard')
@application.route('/dashboard')
def index():
    try:
        if is_login():
            content = {'is_admin':is_admin()}
            return render_template('dashboard.html', result=content)
    except Exception as e:
        print('dashboard exception:- ', str(e))
    return redirect(url_for('login'))


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

if __name__ == '__main__':
    application.run(debug=True, port=8080)
