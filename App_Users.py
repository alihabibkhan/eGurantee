from imports import *
from application import application


@application.route('/manage-users')
def manage_users():
    try:
        if is_login() and is_admin():
            content = {'get_all_user_data': get_all_user_data()}
            return render_template('manage_users.html', result=content)
    except Exception as e:
        print('manage users exception:- ', str(e))
    return redirect(url_for('login'))
