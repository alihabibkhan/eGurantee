from imports import *
from application import application


@application.route('/fund-projection-report')
def fund_projection_report():
    try:
        if is_login() and (is_admin() or is_executive_approver()):
            content = {
                'get_all_bank_details': get_all_bank_details(),
                'get_all_banks_last_entry_records': get_all_banks_last_entry_records(),
                'get_outstanding_loans': get_outstanding_loans(),
                'post_disbursement_by_booked_on': post_disbursement_by_booked_on()
            }
            return render_template('fund_projection_report.html', result=content)
    except Exception as e:
        print('fund projection report exception:- ', str(e))
    return redirect(url_for('login'))

