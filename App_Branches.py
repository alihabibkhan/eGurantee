from imports import *
from application import application


@application.route('/manage-branches')
def manage_branches():
    try:
        if is_login() and is_admin():
            content = {'get_all_branches_info': get_all_branches_info()}
            return render_template('manage_branches.html', result=content)
    except Exception as e:
        print('manage branches exception:- ', str(e.__dict__))
    return redirect(url_for('login'))
