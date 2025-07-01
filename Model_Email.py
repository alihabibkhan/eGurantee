from imports import *
from application import mail


# Reusable email sending method
def send_email(subject, email_list, message, html_message=None, attachment=None, filename=None, content_type=None):
    try:
        msg = Message(subject, recipients=email_list)
        if html_message:
            msg.html = html_message
        else:
            msg.body = message
        if attachment:
            msg.attach(filename or 'attachment.pdf', content_type or 'application/octet-stream', attachment)
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email sending error: {str(e)}")
        return False