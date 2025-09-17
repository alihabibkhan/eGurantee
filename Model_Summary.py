from imports import *


def send_email_of_pending_applications():
    # Get count of status by branch name
    query = """
        SELECT 
            "Branch_Name",
            CASE 
                WHEN Status = '1' THEN 'Under Review'
                WHEN Status = '2' THEN 'Agreed'
                WHEN Status = '3' THEN 'Disagreed'
                WHEN Status = '5' THEN 'Recommended for Agreement'
                WHEN Status = '6' THEN 'Recommended for Disagreement'
                ELSE 'Unknown'
            END AS Status,
            COUNT(*) AS Count
        FROM 
            tbl_pre_disbursement_temp
        GROUP BY 
            "Branch_Name", Status
        ORDER BY 
            "Branch_Name", Status;
    """

    result = fetch_records(query)

    # Print the original result (status counts by branch)
    print("Status Counts by Branch:", result)

    # Extract unique branch codes by splitting Branch_Name and taking the first part
    unique_branches_code = sorted(list(set(
        str(row[0]).split('-')[0].strip() if isinstance(row, tuple) else str(row['Branch_Name']).split('-')[0].strip() for row in result
    )))

    # Print unique branch codes
    print("Unique Branch Codes:", unique_branches_code)

    # Get branch information to map roles to branch codes
    branch_records = get_all_branches_records()
    print("Branch Records:", branch_records)

    # Create a mapping of role to list of branch codes
    role_to_branch_codes = {}
    for branch in branch_records:
        role = branch['role'] if isinstance(branch, dict) else branch[0]  # Adjust based on get_all_branches_records return format
        branch_code = branch['branch_code'] if isinstance(branch, dict) else branch[1]
        if role not in role_to_branch_codes:
            role_to_branch_codes[role] = []
        role_to_branch_codes[role].append(branch_code)

    # Create a query to fetch user details for the unique branch codes
    query = f"""
        SELECT DISTINCT 
            u.user_id, 
            u.name, 
            u.email, 
            u.rights, 
            u.volunteer_id, 
            u.gender, 
            u.dob, 
            u.phone, 
            u.country_of_residence, 
            u.date_of_joining, 
            u.orientation_completed_on, 
            u.manager_id, 
            u.assigned_branch, 
            u.date_of_retirement, 
            u.reason, 
            u.created_date 
        FROM tbl_users u 
        INNER JOIN tbl_branches b 
            ON u.assigned_branch = b.role 
            AND b.branch_code IN ({str(unique_branches_code)[1:-1]}) 
            AND b."live_branch" = '1'
    """

    # Execute the query to fetch user details
    user_result = fetch_records(query)

    # Print user details
    print("User Details for Branches:", user_result)

    # Group application data by branch for easy lookup
    branch_data = {}
    for row in result:
        branch_name = str(row[0]) if isinstance(row, tuple) else str(row['Branch_Name'])
        branch_code = branch_name.split('-')[0].strip()
        if branch_code not in branch_data:
            branch_data[branch_code] = []
        status = row[1] if isinstance(row, tuple) else row['status']
        count = row[2] if isinstance(row, tuple) else row['count']
        branch_data[branch_code].append({'status': status, 'count': count, 'branch_name': branch_name})

    # Generate and send email for each user
    for user in user_result:
        user_email = user[2] if isinstance(user, tuple) else user['email']
        user_name = user[1] if isinstance(user, tuple) else user['name']
        assigned_branch = user[12] if isinstance(user, tuple) else user['assigned_branch']

        # Get all branch codes for the user's assigned_branch (role)
        user_branch_codes = role_to_branch_codes.get(assigned_branch, [])
        if not user_branch_codes:
            print(f"No branch codes found for role {assigned_branch} for user {user_email}")
            continue

        # Filter branch codes that have data
        relevant_branch_codes = [code for code in user_branch_codes if code in branch_data]
        if not relevant_branch_codes:
            print(f"No data found for branches {user_branch_codes} for user {user_email}")
            continue

        # Generate HTML report
        html_report = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; background-color: #f4f4f4; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                h2 {{ color: #2c3e50; text-align: center; }}
                h3 {{ color: #34495e; margin-top: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border: 1px solid #ddd; }}
                th {{ background-color: #3498db; color: white; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 14px; color: #7f8c8d; }}
                .header {{ text-align: center; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Pending Applications Report</h2>
                </div>
                <p>Dear {user_name},</p>
                <p>Below is the report of pending applications for your assigned branch ({assigned_branch}) as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S PKT')}:</p>
        """

        # Add data for each branch code
        for branch_code in relevant_branch_codes:
            branch_name = next((entry['branch_name'] for entry in branch_data[branch_code]), branch_code)
            html_report += f"""
                <h3>Branch: {branch_name}</h3>
                <table>
                    <tr>
                        <th>Status</th>
                        <th>Count</th>
                    </tr>
            """
            for entry in branch_data[branch_code]:
                html_report += f"""
                    <tr>
                        <td>{entry['status']}</td>
                        <td>{entry['count']}</td>
                    </tr>
                """
            html_report += "</table>"

        html_report += f"""
                <p>Thank you for your attention to these pending applications.</p>
                <div class="footer">
                    <p><strong>Khushali Foundation</strong></p>
                    <p>Empowering Communities, Transforming Lives</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Send email using Model_Email's send_email function
        subject = f"Pending Applications Report for {assigned_branch}"
        try:
            from Model_Email import send_email
            send_email(subject, [user_email], None, html_message=html_report)
            print(f"Email sent to {user_email} for branch role {assigned_branch}")
        except Exception as e:
            print(f"Failed to send email to {user_email}: {str(e)}")

    return unique_branches_code