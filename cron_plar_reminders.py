"""
PLAR daily job: remind owners of overdue / soon-due corrective actions and escalate overdue High/Critical ones
to KFT management. Schedule it once a day, e.g. on Render: `python cron_plar_reminders.py`.

    python cron_plar_reminders.py            # send the emails
    python cron_plar_reminders.py --dry-run  # only report what would be sent
"""
import sys
from application import application
from Model_PLAR import remind_plar_actions, escalate_plar_actions, get_plar_actions

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    with application.test_request_context():     # Flask-Mail needs an app context; there is no signed-in user here
        if dry_run:
            acts = get_plar_actions()
            due = [a for a in acts if a['status'] not in ('Resolved', 'Closed')]
            print(f"DRY RUN: {len(due)} open action(s), {sum(1 for a in due if a['overdue'])} overdue, "
                  f"{sum(1 for a in due if a['overdue'] and a['severity'] in ('High', 'Critical') and not a['escalated'])} to escalate")
        else:
            reminded, emails, no_user = remind_plar_actions()
            count, sent, recipients = escalate_plar_actions()
            print(f"Reminders: {reminded} action(s), {emails} email(s), {no_user} without an EGS user. "
                  f"Escalated: {count} action(s), emailed={sent}, managers={len(recipients)}")
