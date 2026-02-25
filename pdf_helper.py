from application import application
from imports import *


def generate_anomalies_html(anomaly_applications):
    """
    Generate an HTML report containing anomalies for pre and post disbursement
    Args:
        anomaly_applications: List of application numbers that have anomalies
    Returns:
        Path to the generated HTML file
    """
    application.logger.debug(
        f"generate_anomalies_html: Generating HTML report for {len(anomaly_applications)} applications")

    if not anomaly_applications:
        application.logger.debug("generate_anomalies_html: No anomalies to report")
        return None

    # Format application numbers for SQL IN clause
    app_list = ",".join("'" + str(app).replace("'", "''") + "'" for app in anomaly_applications)

    # Fetch pre-disbursement anomalies
    pre_query = f"""
    SELECT 
        t."Application_No" as application_no,
        t."CNIC" as cnic,
        t."Borrower_Name" as borrower_name,
        t."Branch_Name" as branch_name,
        a.details,
        a.created_date as detected_at
    FROM tbl_pre_disb_anomalies a
    JOIN tbl_pre_disbursement_temp t ON a.pre_disb_id = t.pre_disb_temp_id
    WHERE t."Application_No" IN ({app_list})
    ORDER BY t."Application_No", a.created_date DESC
    """

    print(pre_query)

    pre_records = fetch_records(pre_query)
    print('pre_records')
    print(pre_records)
    pre_anomalies = [dict(row) for row in pre_records] if pre_records else []
    print('pre_anomalies:- ')
    print(pre_anomalies)

    # Fetch post-disbursement anomalies
    post_query = f"""
    SELECT 
        a.application_no as customer_id,
        t.loan_no,
        t.cnic,
        t.branch_name,
        a.details,
        a.created_date as detected_at
    FROM tbl_post_disbursement_anomalies a
    LEFT JOIN tbl_post_disbursement t ON a.application_no = t.customer_id
    WHERE a.application_no IN ({app_list})
    ORDER BY a.application_no, a.created_date DESC
    """

    post_records = fetch_records(post_query)
    post_anomalies = [dict(row) for row in post_records] if post_records else []

    # Prepare template data
    template_data = {
        'generation_date': str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        'pre_anomalies': pre_anomalies,
        'post_anomalies': post_anomalies,
        'pre_count': len(pre_anomalies),
        'post_count': len(post_anomalies),
        'total_count': len(pre_anomalies) + len(post_anomalies),
        'total_applications': len(anomaly_applications)
    }

    # Render HTML template
    try:
        from flask import render_template
        html_content = render_template('anomalies_report.html', **template_data)
    except Exception as e:
        application.logger.error(f"generate_anomalies_html: Template rendering failed: {str(e)}")
        # Fallback to simple HTML if template fails
        html_content = generate_fallback_html(template_data)

    # Save HTML file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_filename = f"Anomalies_Report_{timestamp}.html"
    html_path = os.path.join(current_app.config['UPLOAD_FOLDER'], html_filename)

    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        application.logger.debug(f"generate_anomalies_html: HTML generated at {html_path}")
        return html_path
    except Exception as e:
        application.logger.error(f"generate_anomalies_html: Failed to save HTML: {str(e)}")
        return None


def generate_fallback_html(data):
    """Generate a simple HTML report if template rendering fails"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Anomalies Report</title>
        <style>
            body {{ font-family: Arial; margin: 20px; }}
            h1 {{ color: #dc3545; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th {{ background: #343a40; color: white; padding: 8px; }}
            td {{ border: 1px solid #ddd; padding: 8px; }}
            .anomaly {{ background: #f8d7da; padding: 5px; }}
        </style>
    </head>
    <body>
        <h1>Anomalies Report</h1>
        <p>Generated: {data['generation_date']}</p>
        <p>Total Applications: {data['total_applications']}</p>
        <p>Pre Anomalies: {data['pre_count']}, Post Anomalies: {data['post_count']}</p>
    </body>
    </html>
    """
    return html