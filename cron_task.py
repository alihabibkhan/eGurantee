from application import application


# Example task function that the cron will run (e.g., could be DB cleanup, email sending, etc.)
def cron_example_task():
    # Add your actual logic here, e.g., interact with a DB or API
    print("Cron task running: Performing maintenance...")
    # For real use, you might import models or use app.config for secrets


# Run in app context (useful if task needs config, DB, etc.)
with application.app_context():

    cron_example_task()
