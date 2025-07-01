from imports import *
from application import application


@application.route('/manage-budget')
def manage_budget():
    try:
        if is_login() and is_admin():
            content = {'get_all_budget_info': get_all_budget_info()}
            return render_template('manage_budget.html', result=content)
    except Exception as e:
        print('manage budget exception:- ', str(e))
    return redirect(url_for('login'))
