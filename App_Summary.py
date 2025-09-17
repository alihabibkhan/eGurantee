from imports import *
from application import application



@application.route('/send_summary', methods=['POST', 'GET'])
def send_summary():
    try:
        if is_login() and is_admin():
            send_email_of_pending_applications()
            return 'Sent'
    except Exception as e:
        print('send summary exception:- ', e)
    return 'Failed!'


class WeeklySummaryService:
    def __init__(self, test_mode=False):
        self.test_mode = test_mode
        self.summary_sent = False  # Tracks whether today's summary was sent

    def summary_checker(self):
        while True:
            now = datetime.now()
            # Check if it's Monday (weekday() == 0 for Monday)
            is_monday = now.weekday() == 0

            if self.test_mode:
                # Test mode: send summary daily at midnight
                if now.hour == 0 and not self.summary_sent:
                    send_email_of_pending_applications()
                    self.summary_sent = True
                elif now.hour != 0:
                    self.summary_sent = False
            else:
                # Production mode: send summary every Monday at midnight
                if is_monday and now.hour == 0 and not self.summary_sent:
                    send_email_of_pending_applications()
                    self.summary_sent = True
                elif not is_monday or now.hour != 0:
                    self.summary_sent = False

            time.sleep(60)  # Check every 60 seconds

    def start(self):
        thread = threading.Thread(target=self.summary_checker, daemon=True)
        thread.start()


# Initialize and start the service
service = WeeklySummaryService(test_mode=False)
service.start()
