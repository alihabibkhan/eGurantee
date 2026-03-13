import os
from application import Message, mail


# Reusable email sending method
def send_email(subject, email_list, message, html_message=None, attachment=None, filename=None, content_type=None, add_cc_list=False, cc_list=[]):
    try:

        if len(cc_list):
            cc_list = cc_list
        else:
            cc_list = str(os.getenv('MAIL_CC')).split(',')

        if add_cc_list:
            msg = Message(subject, recipients=email_list, cc=cc_list)
        else:
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


def get_cron_success_email_body(job_name, summary_data):
    """
    Returns a clean, modern HTML email body for cron job success notification
    """
    started_at = summary_data.get('started_at', 'N/A')
    finished_at = summary_data.get('finished_at', 'N/A')
    duration = summary_data.get('duration_seconds', 'N/A')
    emails_found = summary_data.get('emails_found', 0)
    files_processed = summary_data.get('files_processed', 0)
    new_records = summary_data.get('new_records_count', 0)
    duplicates = summary_data.get('duplicates_count', 0)
    anomalies = summary_data.get('anomalies_count', 0)

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cron Job Completed Successfully</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background-color: #f4f6f9;
                margin: 0;
                padding: 0;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 30px auto;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }}
            .header {{
                background: linear-gradient(135deg, #0d6efd, #0b5ed7);
                color: white;
                padding: 30px 40px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                padding: 30px 40px;
            }}
            .success-badge {{
                display: inline-block;
                background: #d4edda;
                color: #155724;
                padding: 8px 16px;
                border-radius: 30px;
                font-weight: bold;
                margin-bottom: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px 15px;
                text-align: left;
                border-bottom: 1px solid #eee;
            }}
            th {{
                background: #f8f9fa;
                font-weight: 600;
            }}
            .footer {{
                background: #f8f9fa;
                padding: 20px;
                text-align: center;
                font-size: 13px;
                color: #666;
                border-top: 1px solid #eee;
            }}
            .highlight {{
                color: #0d6efd;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Cron Job Completed Successfully</h1>
            </div>
            <div class="content">
                <div class="success-badge">SUCCESS</div>

                <p>Dear Team,</p>

                <p>The <strong>{job_name}</strong> cron job has completed successfully.</p>

                <table>
                    <tr>
                        <th>Started At</th>
                        <td>{started_at}</td>
                    </tr>
                    <tr>
                        <th>Finished At</th>
                        <td>{finished_at}</td>
                    </tr>
                    <tr>
                        <th>Duration</th>
                        <td>{duration} seconds</td>
                    </tr>
                    <tr>
                        <th>Emails Found</th>
                        <td class="highlight">{emails_found}</td>
                    </tr>
                    <tr>
                        <th>Files Processed</th>
                        <td class="highlight">{files_processed}</td>
                    </tr>
                    <tr>
                        <th>New Records Added</th>
                        <td class="highlight">{new_records}</td>
                    </tr>
                    <tr>
                        <th>Duplicates Skipped</th>
                        <td>{duplicates}</td>
                    </tr>
                    <tr>
                        <th>Anomalies Detected</th>
                        <td>{anomalies}</td>
                    </tr>
                </table>

                <p>If anomalies were detected, please review the attached report (if generated).</p>

                <p>Best regards,<br>
                <strong>eGuarantee System</strong><br>
                Automated Cron Notification</p>
            </div>
            <div class="footer">
                This is an automated message from the eGuarantee System.
            </div>
        </div>
    </body>
    </html>
    """

    return html