# auto_approve_student_finance.py
from imports import *
from application import application
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import json
import logging
from typing import Dict, List, Optional, Tuple
from Model_Email import send_email

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StudentFinanceAutoApprover:
    """Handles auto-approval of Student Finance applications"""

    def __init__(self, dry_run: bool = False):
        """
        Initialize the auto-approver.

        Args:
            dry_run: If True, no database changes will be made (no updates/inserts)
        """
        self.approval_status = '2'  # 'Agreed' status
        self.auto_approval_log = []
        self.dry_run = dry_run

        # Business Type Classification
        self.home_based_businesses = [
            'Livestock',
            'Agriculture',
            'Pension',
            'Services'
        ]

        self.shop_based_businesses = [
            'Salary',
            'Salaried',
            'Enterprise Services',
            'Trading',
            'Manufacturing',
            'Enterprise Trading'
        ]

        # Default mapping for any business not in lists
        self.default_business_type = 'Shop Based'  # Default assumption

        if self.dry_run:
            logger.info("=" * 60)
            logger.info("🔍 DRY RUN MODE ENABLED - No database changes will be made")
            logger.info("=" * 60)

    def get_auto_approval_approver(self) -> Optional[Dict]:
        """
        Get the user who is designated as auto-approval signatory from tbl_loan_products.
        Returns user details including signature path.
        """
        # First get the auto_approval_signature user_id from product
        product_query = f"""
            SELECT auto_approval_signature 
            FROM tbl_loan_products 
            WHERE product_code = 'Student Finance'
            AND auto_approve = '1'
            LIMIT 1
        """

        product_result = fetch_records(product_query)

        if not product_result or len(product_result) == 0:
            logger.error("No Student Finance product found with auto_approve = 1")
            return None

        auto_approval_signature_user_id = product_result[0].get('auto_approval_signature')

        if not auto_approval_signature_user_id:
            logger.error("auto_approval_signature not set for Student Finance product")
            return None

        # Get the user details with signature
        query = f"""
            SELECT DISTINCT
                u.user_id,
                u.name,
                u.email,
                u.scan_sign,
                u.rights
            FROM tbl_users u
            WHERE 
                u.user_id = {auto_approval_signature_user_id}
                AND u.active = 1
                AND u.scan_sign IS NOT NULL
                AND u.scan_sign != ''
            LIMIT 1
        """

        logger.info(f"Fetching auto-approval signatory with user_id: {auto_approval_signature_user_id}")
        result = fetch_records(query)

        if result and len(result) > 0:
            logger.info(f"Found auto-approval signatory: {result[0]['name']}")
            return result[0]
        else:
            logger.error(f"No active user found with signature for user_id {auto_approval_signature_user_id}")
            return None

    def get_auto_approval_max_amount(self) -> float:
        """
        Get the auto_approval_max_amount from tbl_loan_products.
        Returns: Max amount allowed for auto-approval (default 0.00)
        """
        query = f"""
            SELECT auto_approval_max_amount 
            FROM tbl_loan_products 
            WHERE product_code = 'Student Finance'
            AND auto_approve = '1'
            LIMIT 1
        """

        result = fetch_records(query)

        if result and len(result) > 0:
            max_amount = float(result[0].get('auto_approval_max_amount', 0))
            logger.info(f"Auto-approval max amount: {max_amount}")
            return max_amount

        logger.warning("No auto_approval_max_amount found, defaulting to 0")
        return 0.00

    def check_auto_approval_max_amount(self, record: Dict, max_amount: float) -> Tuple[bool, str]:
        """
        Check if loan amount is within auto-approval max limit.
        This is a MANDATORY check.
        Returns (pass, message)
        """
        loan_amount = float(record.get('Loan_Amount', 0))

        if max_amount <= 0:
            # If max_amount is 0 or not set, this check passes (no limit)
            return True, "✓ No auto-approval max limit set"

        if loan_amount <= max_amount:
            return True, f"✓ Loan amount {loan_amount:.2f} within auto-approval limit {max_amount:.2f}"
        else:
            return False, f"✗ Loan amount {loan_amount:.2f} exceeds auto-approval limit {max_amount:.2f}"

    def get_approvers_and_executive_approvers(self) -> List[Dict]:
        """
        Get all users with Approver (rights=2) or Executive Approver (rights=3) or Admin (rights=4) roles.
        """
        query = f"""
            SELECT DISTINCT
                u.user_id,
                u.name,
                u.email,
                u.rights
            FROM tbl_users u
            WHERE
                u.active = 1
                AND u.email IS NOT NULL
                AND u.email != ''
                AND (
                    u.rights = 3  -- Executive Approver
                    OR u.rights = 4  -- Admin
                )
        """

        result = fetch_records(query)
        logger.info(f"Found {len(result)} approvers/executive approvers to notify")
        return result

    def generate_email_html_summary(self, summary: Dict, approved_apps: List, failed_apps: List,
                                    run_datetime: datetime) -> str:
        """
        Generate HTML email body with summary of auto-approval cycle.
        """
        mode_text = "DRY RUN" if self.dry_run else "LIVE"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Student Finance Auto-Approval Summary</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: #1e3a8a;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 5px;
                }}
                .summary-box {{
                    background-color: #f0fdf4;
                    border-left: 4px solid #22c55e;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .warning-box {{
                    background-color: #fef2f2;
                    border-left: 4px solid #ef4444;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .info-box {{
                    background-color: #eff6ff;
                    border-left: 4px solid #3b82f6;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                    font-size: 13px;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px 10px;
                    text-align: left;
                }}
                th {{
                    background-color: #f3f4f6;
                    font-weight: bold;
                }}
                tr:nth-child(even) {{
                    background-color: #f9fafb;
                }}
                .badge-success {{
                    background-color: #22c55e;
                    color: white;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-size: 11px;
                }}
                .badge-danger {{
                    background-color: #ef4444;
                    color: white;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-size: 11px;
                }}
                .badge-warning {{
                    background-color: #f59e0b;
                    color: white;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-size: 11px;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    font-size: 12px;
                    color: #666;
                    text-align: center;
                }}
                h2 {{
                    color: #1e3a8a;
                    margin-top: 25px;
                }}
                h3 {{
                    color: #374151;
                    margin-top: 20px;
                }}
                .branch-breakdown {{
                    margin: 10px 0;
                    padding: 5px 0;
                }}
                .branch-list {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                    margin: 10px 0;
                }}
                .branch-item {{
                    background-color: #f3f4f6;
                    padding: 8px 15px;
                    border-radius: 20px;
                    font-size: 13px;
                    border: 1px solid #e5e7eb;
                }}
                .branch-item strong {{
                    color: #1e3a8a;
                }}
                .branch-count {{
                    background-color: #1e3a8a;
                    color: white;
                    padding: 2px 10px;
                    border-radius: 12px;
                    font-size: 11px;
                    margin-left: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎓 Student Finance Auto-Approval Report</h1>
                    <p><strong>Mode:</strong> {mode_text} | <strong>Date/Time:</strong> {run_datetime.strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
        """

        # Summary Statistics
        html += f"""
                <div class="summary-box">
                    <h2>📊 Summary Statistics</h2>
                    <table>
                        <tr>
                            <th>Total Eligible Applications</th>
                            <td><strong>{summary['total_eligible']}</strong></td>
                        </tr>
                        <tr>
                            <th>Total Auto-Approved</th>
                            <td><strong style="color: #22c55e;">{summary['total_approved']}</strong></td>
                        </tr>
                        <tr>
                            <th>├─ Salary/Salaried Bypass</th>
                            <td>{summary['salary_approved']}</td>
                        </tr>
                        <tr>
                            <th>└─ Full Metrics Check Pass</th>
                            <td>{summary['metrics_approved']}</td>
                        </tr>
                        <tr>
                            <th>Total Not Approved (Manual Review Required)</th>
                            <td><strong style="color: #ef4444;">{summary['total_failed']}</strong></td>
                        </tr>
                    </table>
                </div>
        """

        # Gender Breakdown
        if summary['male_approved'] > 0 or summary['female_approved'] > 0:
            html += f"""
                <div class="info-box">
                    <h2>👥 Gender Breakdown</h2>
                    <table>
                        <tr>
                            <th>Male Approved</th>
                            <td>{summary['male_approved']}</td>
                        </tr>
                        <tr>
                            <th>Female Approved</th>
                            <td>{summary['female_approved']}</td>
                        </tr>
                    </table>
                </div>
            """

        # ============================================================
        # BRANCH BREAKDOWN - Both Approved and Failed
        # ============================================================

        # Approved Branch Breakdown
        branch_breakdown_approved = {}
        for app in approved_apps:
            branch = app.get('branch', 'Unknown')
            branch_breakdown_approved[branch] = branch_breakdown_approved.get(branch, 0) + 1

        # Failed Branch Breakdown
        branch_breakdown_failed = {}
        for app in failed_apps:
            branch = app.get('branch', 'Unknown')
            branch_breakdown_failed[branch] = branch_breakdown_failed.get(branch, 0) + 1

        # All branches with status
        all_branches = set(list(branch_breakdown_approved.keys()) + list(branch_breakdown_failed.keys()))

        if all_branches:
            html += f"""
                <div class="info-box">
                    <h2>🏦 Branch Breakdown</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Branch Name</th>
                                <th>Approved</th>
                                <th>Not Approved</th>
                                <th>Total</th>
                            </tr>
                        </thead>
                        <tbody>
            """

            total_approved = 0
            total_failed = 0

            for branch in sorted(all_branches):
                approved_count = branch_breakdown_approved.get(branch, 0)
                failed_count = branch_breakdown_failed.get(branch, 0)
                total_count = approved_count + failed_count

                total_approved += approved_count
                total_failed += failed_count

                html += f"""
                            <tr>
                                <td><strong>{branch}</strong></td>
                                <td style="color: #22c55e;">{approved_count}</td>
                                <td style="color: #ef4444;">{failed_count}</td>
                                <td>{total_count}</td>
                            </tr>
                """

            # Grand Total Row
            html += f"""
                            <tr style="background-color: #f3f4f6; font-weight: bold;">
                                <td><strong>TOTAL</strong></td>
                                <td style="color: #22c55e;">{total_approved}</td>
                                <td style="color: #ef4444;">{total_failed}</td>
                                <td>{total_approved + total_failed}</td>
                            </tr>
            """

            html += """
                        </tbody>
                    </table>
                </div>
            """

        # ============================================================
        # BRANCH SUMMARY CARDS (Alternative visual representation)
        # ============================================================
        if all_branches and len(all_branches) > 1:
            html += f"""
                <div class="info-box">
                    <h2>🏢 Branch Summary Cards</h2>
                    <div class="branch-list">
            """

            for branch in sorted(all_branches):
                approved_count = branch_breakdown_approved.get(branch, 0)
                failed_count = branch_breakdown_failed.get(branch, 0)
                total_count = approved_count + failed_count

                html += f"""
                        <div class="branch-item">
                            <strong>{branch}</strong>
                            <br>
                            ✅ Approved: {approved_count}
                            <br>
                            ❌ Failed: {failed_count}
                            <br>
                            <span class="branch-count">Total: {total_count}</span>
                        </div>
                """

            html += """
                    </div>
                </div>
            """

        # Approved Applications Details
        if approved_apps:
            html += f"""
                <h2>✅ AUTO-APPROVED APPLICATIONS ({len(approved_apps)})</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Application No</th>
                            <th>Borrower Name</th>
                            <th>Gender</th>
                            <th>Branch</th>
                            <th>Loan Amount</th>
                            <th>Nature of Business</th>
                            <th>Predicted Type</th>
                            <th>Approval Type</th>
                            <th>Approved By</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for app in approved_apps:
                amount = app.get('amount', 0)
                try:
                    amount = float(amount)
                except (TypeError, ValueError):
                    amount = 0.0

                html += f"""
                        <tr>
                            <td>{app.get('application_no', 'N/A')}</td>
                            <td>{app.get('borrower_name', 'N/A')}</td>
                            <td>{app.get('gender', 'N/A')}</td>
                            <td>{app.get('branch', 'N/A')}</td>
                            <td>{amount:,.2f}</td>
                            <td>{app.get('nature_of_business', 'N/A')}</td>
                            <td>{app.get('predicted_business_type', 'N/A')}</td>
                            <td><span class="badge-success">{app.get('approval_type', 'N/A')}</span></td>
                            <td>{app.get('approver', 'N/A')}</td>
                        </tr>
                """
            html += """
                    </tbody>
                </table>
            """

        # Not Approved Applications Details
        if failed_apps:
            html += f"""
                <h2>⚠️ NOT APPROVED - REQUIRES MANUAL REVIEW ({len(failed_apps)})</h2>
                <div class="warning-box">
                    <p><strong>Note:</strong> These applications remain in "Under Review" status and require manual processing.</p>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Application No</th>
                            <th>Gender</th>
                            <th>Branch</th>
                            <th>Nature of Business</th>
                            <th>Predicted Type</th>
                            <th>Reason for Not Approved</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for app in failed_apps:
                reason = app.get('reason', 'N/A')
                if len(reason) > 100:
                    reason = reason[:100] + "..."

                html += f"""
                        <tr>
                            <td>{app.get('application_no', 'N/A')}</td>
                            <td>{app.get('gender', 'N/A')}</td>
                            <td>{app.get('branch', 'N/A')}</td>
                            <td>{app.get('nature_of_business', 'N/A')}</td>
                            <td>{app.get('predicted_business_type', 'N/A')}</td>
                            <td style="color: #dc2626;">{reason}</td>
                        </tr>
                """
            html += """
                    </tbody>
                </table>
            """

        # Footer
        html += f"""
                <div class="footer">
                    <p>This is an auto-generated report from Student Finance Auto-Approval System.</p>
                    <p>For questions or support, please contact the system administrator.</p>
                    <hr>
                    <p><small>Report generated on: {run_datetime.strftime('%Y-%m-%d %H:%M:%S')}</small></p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def generate_text_summary(self, summary: Dict, approved_apps: List, failed_apps: List,
                              run_datetime: datetime) -> str:
        """
        Generate plain text email body (fallback).
        """
        mode_text = "DRY RUN" if self.dry_run else "LIVE"

        text = f"""
    {'=' * 80}
    STUDENT FINANCE AUTO-APPROVAL SUMMARY REPORT - {mode_text}
    {'=' * 80}

    Run Time: {run_datetime.strftime('%Y-%m-%d %H:%M:%S')}

    {'=' * 80}
    SUMMARY STATISTICS
    {'=' * 80}
    Total Eligible Applications: {summary['total_eligible']}
    Total Auto-Approved: {summary['total_approved']}
      ├─ Salary/Salaried Bypass: {summary['salary_approved']}
      └─ Full Metrics Check Pass: {summary['metrics_approved']}
    Total Not Approved (Manual Review Required): {summary['total_failed']}

    {'=' * 80}
    GENDER BREAKDOWN
    {'=' * 80}
    Male Approved: {summary['male_approved']}
    Female Approved: {summary['female_approved']}

    """

        # Branch Breakdown - Both Approved and Failed
        branch_breakdown_approved = {}
        for app in approved_apps:
            branch = app.get('branch', 'Unknown')
            branch_breakdown_approved[branch] = branch_breakdown_approved.get(branch, 0) + 1

        branch_breakdown_failed = {}
        for app in failed_apps:
            branch = app.get('branch', 'Unknown')
            branch_breakdown_failed[branch] = branch_breakdown_failed.get(branch, 0) + 1

        all_branches = set(list(branch_breakdown_approved.keys()) + list(branch_breakdown_failed.keys()))

        if all_branches:
            text += f"""
    {'=' * 80}
    BRANCH BREAKDOWN
    {'=' * 80}
    """
            text += f"{'Branch Name':<30} {'Approved':<12} {'Not Approved':<15} {'Total':<10}\n"
            text += "-" * 80 + "\n"

            total_approved = 0
            total_failed = 0

            for branch in sorted(all_branches):
                approved_count = branch_breakdown_approved.get(branch, 0)
                failed_count = branch_breakdown_failed.get(branch, 0)
                total_count = approved_count + failed_count

                total_approved += approved_count
                total_failed += failed_count

                text += f"{branch:<30} {approved_count:<12} {failed_count:<15} {total_count:<10}\n"

            text += "-" * 80 + "\n"
            text += f"{'TOTAL':<30} {total_approved:<12} {total_failed:<15} {total_approved + total_failed:<10}\n"

        # Approved Applications
        if approved_apps:
            text += f"""
    {'=' * 80}
    AUTO-APPROVED APPLICATIONS ({len(approved_apps)})
    {'=' * 80}
    """
            for app in approved_apps:
                text += f"""
      Application: {app.get('application_no', 'N/A')}
        Borrower: {app.get('borrower_name', 'N/A')}
        Gender: {app.get('gender', 'N/A')}
        Branch: {app.get('branch', 'N/A')}
        Amount: {app.get('amount', 0):,.2f}
        Nature: {app.get('nature_of_business', 'N/A')}
        Type: {app.get('approval_type', 'N/A')}
        Approved By: {app.get('approver', 'N/A')}
        {'-' * 40}
    """

        # Not Approved Applications
        if failed_apps:
            text += f"""
    {'=' * 80}
    NOT APPROVED - REQUIRES MANUAL REVIEW ({len(failed_apps)})
    {'=' * 80}
    """
            for app in failed_apps:
                text += f"""
      Application: {app.get('application_no', 'N/A')}
        Gender: {app.get('gender', 'N/A')}
        Branch: {app.get('branch', 'N/A')}
        Nature: {app.get('nature_of_business', 'N/A')}
        Reason: {app.get('reason', 'N/A')}
        {'-' * 40}
    """

        text += f"""
    {'=' * 80}
    End of Report
    {'=' * 80}
    """

        return text

    def send_summary_email_to_approvers(self, summary: Dict, approved_apps: List, failed_apps: List,
                                        run_datetime: datetime) -> bool:
        """
        Send summary email to all Approvers and Executive Approvers.
        """
        if self.dry_run:
            logger.info("🔍 [DRY RUN] Would send summary email to all approvers")
            return True

        # Get all approvers and executive approvers
        approvers = self.get_approvers_and_executive_approvers()

        if not approvers:
            logger.warning("No approvers/executive approvers found to send email")
            return False

        email_list = [a['email'] for a in approvers if a.get('email')]

        if not email_list:
            logger.warning("No valid email addresses found for approvers")
            return False

        # Prepare email subject
        mode_text = "DRY RUN" if self.dry_run else "LIVE"
        subject = f"[KFT] Student Finance Auto-Approval Summary - {run_datetime.strftime('%Y-%m-%d')} - {mode_text}"

        # Generate HTML and plain text versions
        html_body = self.generate_email_html_summary(summary, approved_apps, failed_apps, run_datetime)
        text_body = self.generate_text_summary(summary, approved_apps, failed_apps, run_datetime)

        # Also create a PDF version (optional - for attachment)
        pdf_attachment = self.generate_pdf_summary(summary, approved_apps, failed_apps, run_datetime)

        logger.info(f"Sending summary email to {len(email_list)} recipients")

        # Send email using your existing send_email function
        try:
            success = send_email(
                subject=subject,
                email_list=email_list,
                message=text_body,
                html_message=html_body,
                attachment=pdf_attachment,
                filename=f"auto_approval_summary_{run_datetime.strftime('%Y%m%d_%H%M%S')}.pdf",
                content_type='application/pdf',
                add_cc_list=True,
                cc_list=[]
            )

            if success:
                logger.info(f"✓ Summary email sent successfully to {len(email_list)} approvers")
            else:
                logger.error("Failed to send summary email")

            return success

        except Exception as e:
            logger.error(f"Failed to send summary email: {str(e)}")
            return False

    def generate_pdf_summary(self, summary: Dict, approved_apps: List, failed_apps: List, run_datetime: datetime) -> \
    Optional[bytes]:
        """
        Generate PDF version of the summary report for attachment.
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from io import BytesIO

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
            styles = getSampleStyleSheet()
            story = []

            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor=colors.HexColor('#1e3a8a'),
                alignment=1
            )
            story.append(Paragraph("Student Finance Auto-Approval Summary", title_style))
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph(f"Run Time: {run_datetime.strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            story.append(Spacer(1, 0.3 * inch))

            # Summary table
            summary_data = [
                ['Metric', 'Count'],
                ['Total Eligible Applications', str(summary['total_eligible'])],
                ['Total Auto-Approved', str(summary['total_approved'])],
                ['  Salary/Salaried Bypass', str(summary['salary_approved'])],
                ['  Full Metrics Check Pass', str(summary['metrics_approved'])],
                ['Total Not Approved', str(summary['total_failed'])],
                ['Male Approved', str(summary['male_approved'])],
                ['Female Approved', str(summary['female_approved'])],
            ]

            summary_table = Table(summary_data, colWidths=[3 * inch, 1.5 * inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 0.3 * inch))

            # Approved Applications Table
            if approved_apps:
                story.append(Paragraph(f"Auto-Approved Applications ({len(approved_apps)})", styles['Heading2']))
                story.append(Spacer(1, 0.1 * inch))

                approved_data = [['App No', 'Borrower', 'Branch', 'Amount', 'Nature', 'Approval Type']]
                for app in approved_apps[:20]:
                    approved_data.append([
                        app.get('application_no', 'N/A'),
                        app.get('borrower_name', 'N/A'),
                        app.get('branch', 'N/A'),
                        f"{app.get('amount', 0):,.0f}",
                        app.get('nature_of_business', 'N/A')[:30],
                        app.get('approval_type', 'N/A')
                    ])

                if len(approved_apps) > 20:
                    approved_data.append(['', f"... and {len(approved_apps) - 20} more applications", '', '', '', ''])

                approved_table = Table(approved_data,
                                       colWidths=[1.2 * inch, 1.5 * inch, 1.2 * inch, 0.8 * inch, 1.5 * inch, 1 * inch])
                approved_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#22c55e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                ]))
                story.append(approved_table)

            doc.build(story)
            buffer.seek(0)
            return buffer.getvalue()

        except ImportError:
            logger.warning("Reportlab not installed, skipping PDF attachment")
            return None
        except Exception as e:
            logger.error(f"Failed to generate PDF: {str(e)}")
            return None

    def get_branch_email(self, branch_name: str) -> Optional[str]:
        """
        Get the email address for a branch.
        """
        try:
            branch_code = branch_name.split('-')[0].strip()

            query = f"""
                SELECT email, branch_code, branch_name 
                FROM tbl_branches 
                WHERE branch_code = '{branch_code}'
                AND live_branch = '1'
                LIMIT 1
            """

            result = fetch_records(query)

            if result and len(result) > 0 and result[0].get('email'):
                branch_email = result[0]['email']
                logger.info(f"Found branch email: {branch_email} for branch {branch_name}")
                return branch_email
            else:
                logger.warning(f"No email found for branch {branch_name}")
                return None

        except Exception as e:
            logger.error(f"Error fetching branch email: {str(e)}")
            return None

    def predict_business_type(self, nature_of_business: str) -> str:
        """
        Auto-predict if business is Home Based or Shop Based
        """
        if not nature_of_business:
            return self.default_business_type

        nature_lower = nature_of_business.lower().strip()

        for business in self.home_based_businesses:
            if business.lower() == nature_lower:
                logger.info(f"Predicted '{nature_of_business}' as Home Based")
                return 'Home Based'

        for business in self.shop_based_businesses:
            if business.lower() == nature_lower:
                logger.info(f"Predicted '{nature_of_business}' as Shop Based")
                return 'Shop Based'

        logger.warning(f"Unknown business type '{nature_of_business}', defaulting to {self.default_business_type}")
        return self.default_business_type

    def calculate_experience_years(self, experience_start_date) -> float:
        """Calculate years of experience from start date"""
        if not experience_start_date:
            return 0

        try:
            if isinstance(experience_start_date, str):
                for date_format in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']:
                    try:
                        start_date = datetime.strptime(experience_start_date, date_format).date()
                        break
                    except ValueError:
                        continue
                else:
                    return 0
            elif isinstance(experience_start_date, date):
                start_date = experience_start_date
            else:
                return 0

            today = date.today()
            difference = relativedelta(today, start_date)
            years = difference.years + (difference.months / 12)

            logger.info(f"Experience start date: {start_date}, Years calculated: {years:.2f}")
            return years

        except Exception as e:
            logger.error(f"Error calculating experience years: {str(e)}")
            return 0

    def predict_experience_level(self, experience_start_date) -> str:
        """Auto-predict experience level based on start date"""
        years = self.calculate_experience_years(experience_start_date)

        if years >= 3:
            logger.info(f"Experience level predicted as '3Yrs Plus' ({years:.2f} years)")
            return '3Yrs Plus'
        else:
            logger.info(f"Experience level predicted as '0 to 3 years' ({years:.2f} years)")
            return '0 to 3 years'

    def get_eligible_applications(self) -> List[Dict]:
        """
        Fetch all Student Finance applications eligible for auto-approval.
        """
        query = f"""
            SELECT 
                DISTINCT
                pdt."pre_disb_temp_id",
                pdt."Application_No",
                pdt."Annual_Business_Incomes",
                pdt."Annual_Disposable_Income",
                pdt."Annual_Expenses",
                pdt."ApplicationDate",
                pdt."Bcc_Approval_Date",
                pdt."Borrower_Name",
                pdt."Branch_Area",
                pdt."Branch_Name",
                pdt."Business_Expense_Description",
                pdt."Business_Experiense_Since",
                pdt."Business_Premises",
                pdt."CNIC",
                pdt."Collage_Univeristy",
                pdt."Collateral_Type",
                pdt."Contact_No",
                pdt."Credit_History_Ecib",
                pdt."Current_Residencial",
                pdt."Dbr",
                pdt."Education_Level",
                pdt."Enrollment_Status",
                pdt."Enterprise_Premises",
                pdt."Existing_Loan_Number",
                pdt."Existing_Loan_Limit",
                pdt."Existing_Loan_Status",
                pdt."Existing_Outstanding_Loan_Schedules",
                pdt."Experiense_Start_Date",
                pdt."Family_Monthly_Income",
                pdt."Father_Husband_Name",
                pdt."Gender",
                pdt."KF_Remarks",
                pdt."Loan_Amount",
                pdt."Loan_Cycle",
                pdt."LoanProductCode",
                pdt."Loan_Status",
                pdt."Monthly_Repayment_Capacity",
                pdt."Nature_Of_Business",
                pdt."No_Of_Family_Members",
                pdt."Permanent_Residencial",
                pdt."Premises",
                pdt."Purpose_Of_Loan",
                pdt."Requested_Loan_Amount",
                pdt."Residance_Type",
                pdt."Student_Name",
                pdt."Student_Co_Borrower_Gender",
                pdt."Student_Relation_With_Borrower",
                pdt."Tenor_Of_Month",
                pdt."Type_of_Business",
                pdt.reviewed_date,
                pdt.Existing_Loan_Exposure_Per_ECIB,
                pdt.KFT_Approved_Loan_Limit,
                pdt."annual_income",
                pdt."notes",
                pdt."status",
                pdt."uploaded_date",
                pdt."approved_date",
                pdt."email_status",
                lp.product_code,
                lp.name as product_name,
                lp.max_exp_per_prud_reg,
                lp.gender as product_gender,
                lp.auto_approval_max_amount,
                lp.auto_approval_signature
            FROM tbl_pre_disbursement_temp pdt
            INNER JOIN tbl_loan_products lp ON lp.product_code = pdt."LoanProductCode" and pdt."Gender" = lp.gender
            WHERE 
                pdt."LoanProductCode" = 'Student Finance'
                AND pdt.status = '1'
                AND lp.auto_approve = '1'
            ORDER BY pdt.uploaded_date ASC
        """

        logger.info(f"Fetching eligible Student Finance applications")
        result = fetch_records(query)
        logger.info(f"Found {len(result)} eligible applications")

        return result

    def get_loan_metrics_for_product(self, product_code: str, gender: str,
                                     business_type: str = None,
                                     experience_level: str = None) -> Optional[Dict]:
        """
        Fetch loan metrics from tbl_loan_metrics based on product, gender, business type, and experience level
        """
        logger.info(f"Fetching product metrics for {product_code} with gender {gender}")
        product_result = get_loan_metric_by_product_code_and_gender(gender=gender, product_code=product_code)

        if not product_result or len(product_result) == 0:
            logger.warning(f"No product found for {product_code} with gender {gender}")
            return None

        product_metrics = product_result[0]

        product_code = product_code.replace("'", "''")
        gender = gender.replace("'", "''")
        business_type = business_type.replace("'", "''") if business_type else ""
        experience_level = experience_level.replace("'", "''") if experience_level else ""

        # Get additional loan metrics if available
        metrics_result = get_loan_metric_by_product_code_and_gender_and_occupation_experience_year(
            gender=gender,
            product_code=product_code,
            occupation=business_type,
            experience_year=experience_level
        )

        combined_metrics = product_metrics.copy()

        if metrics_result and len(metrics_result) > 0:
            logger.info(f"Found additional loan metrics: {metrics_result[0]}")
            for key, value in metrics_result[0].items():
                if value is not None and value != '':
                    combined_metrics[key] = value

        logger.info(f"Combined metrics for {product_code} ({gender}): {combined_metrics}")
        return combined_metrics

    # ============================================================
    # OPTIONAL LOAN METRICS CHECKS (These are optional)
    # ============================================================

    def check_paid_off_requirement(self, record: Dict, loan_metric: Dict) -> Tuple[bool, str]:
        """OPTIONAL: Check if the paid-off requirement is met for repeat loans"""
        loan_cycle = int(record.get('Loan_Cycle', 1))

        if loan_cycle <= 1:
            return True, "First cycle loan - paid off check not applicable"

        cnic = record.get('CNIC', '').replace("'", "''")
        query = f"""
            SELECT 
                disbursed_amount,
                principal_outstanding,
                markup_outstanding,
                loan_status
            FROM tbl_post_disbursement
            WHERE cnic = '{cnic}'
            ORDER BY booked_on DESC
            LIMIT 1
        """

        ongoing_loan = fetch_records(query)

        if not ongoing_loan or len(ongoing_loan) == 0:
            logger.info(f"No previous loan record found for CNIC {cnic} - paid off check passed by default")
            return True, "✓ No previous loan found - paid off check not applicable"

        ongoing = ongoing_loan[0]
        existing_loan_limit = float(ongoing.get('disbursed_amount', 0))
        outstanding = float(ongoing.get('principal_outstanding', 0)) + float(ongoing.get('markup_outstanding', 0))

        required_paid_off_percent = float(loan_metric.get('required_paid_off', 0)) / 100
        required_paid_off = existing_loan_limit * required_paid_off_percent
        actual_paid_off = existing_loan_limit - outstanding

        if actual_paid_off >= required_paid_off:
            return True, f"✓ Paid-off requirement met: {actual_paid_off:.2f} >= {required_paid_off:.2f}"
        else:
            return False, f"✗ Paid-off requirement not met: {actual_paid_off:.2f} < {required_paid_off:.2f}"

    def check_loan_ceiling_requirement(self, record: Dict, loan_metric: Dict) -> Tuple[bool, str]:
        """OPTIONAL: Check if loan amount is within the global loan ceiling"""
        requested_amount = float(record.get('Loan_Amount', 0))
        max_ceiling = float(loan_metric.get('global_loan_ceiling', 0))

        min_loan = float(loan_metric.get('min_loan_amount', 0))
        max_loan = float(loan_metric.get('max_loan_amount', 0))

        if min_loan > 0 and requested_amount < min_loan:
            return False, f"✗ Loan amount {requested_amount:.2f} below minimum {min_loan:.2f}"

        if max_loan > 0 and requested_amount > max_loan:
            return False, f"✗ Loan amount {requested_amount:.2f} exceeds maximum {max_loan:.2f}"

        if requested_amount <= max_ceiling:
            return True, f"✓ Loan amount {requested_amount:.2f} within ceiling {max_ceiling:.2f}"
        else:
            return False, f"✗ Loan amount {requested_amount:.2f} exceeds ceiling {max_ceiling:.2f}"

    def check_repeat_increment_requirement(self, record: Dict, loan_metric: Dict) -> Tuple[bool, str]:
        """OPTIONAL: Check if repeat loan increment meets KFT matrix requirements"""
        loan_cycle = int(record.get('Loan_Cycle', 1))

        if loan_cycle <= 1:
            return True, "First cycle loan - repeat increment check not applicable"

        cnic = record.get('CNIC', '').replace("'", "''")
        query = f"""
            SELECT 
                disbursed_amount
            FROM tbl_post_disbursement
            WHERE cnic = '{cnic}'
            ORDER BY booked_on DESC
            LIMIT 1
        """

        ongoing_loan = fetch_records(query)

        if not ongoing_loan or len(ongoing_loan) == 0:
            logger.info(f"No previous loan record found for CNIC {cnic} - repeat increment check passed by default")
            return True, "✓ No previous loan found - repeat increment check not applicable"

        previous_loan_amount = float(ongoing_loan[0].get('disbursed_amount', 0))
        current_loan_amount = float(record.get('Loan_Amount', 0))
        increment_percent = float(loan_metric.get('repeat_increment', 0))

        max_allowed_increment = previous_loan_amount * (increment_percent / 100)
        actual_increment = current_loan_amount - previous_loan_amount

        if actual_increment <= max_allowed_increment:
            return True, f"✓ Increment {actual_increment:.2f} within allowed {max_allowed_increment:.2f}"
        else:
            return False, f"✗ Increment {actual_increment:.2f} exceeds allowed {max_allowed_increment:.2f}"

    def check_prudential_regulation(self, record: Dict, loan_metric: Dict) -> Tuple[bool, str]:
        """OPTIONAL: Check if loan exposure is within prudential regulations"""
        cnic = record.get('CNIC', '').replace("'", "''")
        max_exposure = float(loan_metric.get('max_exp_per_prud_reg', 0))

        query = f"""
            SELECT COALESCE(SUM(disbursed_amount), 0) as total_exposure
            FROM tbl_post_disbursement
            WHERE cnic = '{cnic}'
            AND loan_status NOT IN ('Closed', 'Settled')
        """

        existing_exposure_result = fetch_records(query)
        existing_exposure = float(
            existing_exposure_result[0].get('total_exposure', 0)) if existing_exposure_result else 0

        requested_amount = float(record.get('Loan_Amount', 0))
        total_exposure = existing_exposure + requested_amount

        if total_exposure <= max_exposure:
            return True, f"✓ Total exposure {total_exposure:.2f} within limit {max_exposure:.2f}"
        else:
            return False, f"✗ Total exposure {total_exposure:.2f} exceeds limit {max_exposure:.2f}"

    def check_dbr_requirement(self, record: Dict) -> Tuple[bool, str]:
        """OPTIONAL: Check if Debt Burden Ratio (DBR) is acceptable (<= 50%)"""
        dbr = record.get('Dbr', 0)

        try:
            dbr_value = float(dbr) if dbr else 0
        except (ValueError, TypeError):
            dbr_value = 0

        if dbr_value <= 50:
            return True, f"✓ DBR {dbr_value:.2f}% within acceptable limit"
        else:
            return False, f"✗ DBR {dbr_value:.2f}% exceeds acceptable limit"

    def check_credit_history(self, record: Dict) -> Tuple[bool, str]:
        """OPTIONAL: Check if credit history is acceptable"""
        credit_history = record.get('credit_history_ecib', '').lower() if record.get('credit_history_ecib') else ''

        if credit_history in ['good', 'clean', 'satisfactory', 'no default']:
            return True, f"✓ Credit history is {credit_history}"
        elif credit_history in ['bad', 'default', 'written off']:
            return False, f"✗ Credit history is {credit_history} - not acceptable"
        else:
            return True, f"✓ Credit history is {credit_history or 'unknown'} - acceptable"

    def check_loan_metrics_for_non_salary(self, record: Dict, business_type: str, experience_level: str) -> Tuple[
        bool, List[str]]:
        """
        OPTIONAL: Run ALL loan metric checks for non-salary applicants.
        If any check fails, the application can still be approved.
        Only the auto_approval_max_amount check is mandatory.
        """
        messages = []

        product_code = record.get('LoanProductCode')
        gender = record.get('Gender')

        logger.info(f"Fetching loan metrics for Product: {product_code}, Gender: {gender}")

        loan_metric = self.get_loan_metrics_for_product(
            product_code,
            gender,
            business_type,
            experience_level
        )

        if not loan_metric:
            messages.append(f"⚠️ No matching loan metrics found - skipping optional checks")
            logger.warning(f"No loan metrics found, skipping optional checks")
            return True, messages

        logger.info(f"Using gender-specific loan metrics: {loan_metric}")

        # Check 1: DBR (Optional)
        dbr_pass, dbr_msg = self.check_dbr_requirement(record)
        messages.append(dbr_msg)
        if not dbr_pass:
            logger.info(f"DBR check failed (optional): {dbr_msg}")

        # Check 2: Credit History (Optional)
        credit_pass, credit_msg = self.check_credit_history(record)
        messages.append(credit_msg)
        if not credit_pass:
            logger.info(f"Credit history check failed (optional): {credit_msg}")

        # Check 3: Loan Ceiling (Optional)
        ceiling_pass, ceiling_msg = self.check_loan_ceiling_requirement(record, loan_metric)
        messages.append(ceiling_msg)
        if not ceiling_pass:
            logger.info(f"Loan ceiling check failed (optional): {ceiling_msg}")

        # Check 4: Prudential Regulation (Optional)
        prudential_pass, prudential_msg = self.check_prudential_regulation(record, loan_metric)
        messages.append(prudential_msg)
        if not prudential_pass:
            logger.info(f"Prudential regulation check failed (optional): {prudential_msg}")

        # Check 5: Paid-off requirement (Optional)
        paid_off_pass, paid_off_msg = self.check_paid_off_requirement(record, loan_metric)
        messages.append(paid_off_msg)
        if not paid_off_pass:
            logger.info(f"Paid-off requirement check failed (optional): {paid_off_msg}")

        # Check 6: Repeat increment requirement (Optional)
        increment_pass, increment_msg = self.check_repeat_increment_requirement(record, loan_metric)
        messages.append(increment_msg)
        if not increment_pass:
            logger.info(f"Repeat increment check failed (optional): {increment_msg}")

        # ALWAYS return True for optional checks - they don't block approval
        return True, messages

    def evaluate_application(self, record: Dict) -> Tuple[bool, List[str], str, Dict]:
        """
        Evaluate if application meets all auto-approval criteria.

        MANDATORY: auto_approval_max_amount check
        OPTIONAL: All loan metrics checks (they don't block approval)

        Returns (approved, messages, approval_type, predictions)
        """
        nature_of_business = record.get('Nature_Of_Business', '')
        experience_start_date = record.get('experiense_start_date')
        gender = record.get('Gender', '')

        # Auto-predict business type
        business_type = self.predict_business_type(nature_of_business)

        # Auto-predict experience level
        experience_level = self.predict_experience_level(experience_start_date)

        predictions = {
            'original_nature': nature_of_business,
            'predicted_business_type': business_type,
            'experience_start_date': experience_start_date,
            'predicted_experience_level': experience_level,
            'calculated_years': self.calculate_experience_years(experience_start_date),
            'gender': gender
        }

        # ============================================================
        # MANDATORY CHECK: Auto-Approval Max Amount
        # ============================================================
        max_amount = self.get_auto_approval_max_amount()
        amount_pass, amount_msg = self.check_auto_approval_max_amount(record, max_amount)

        if not amount_pass:
            logger.error(f"Application {record.get('Application_No')} failed mandatory amount check: {amount_msg}")
            return False, [amount_msg], 'Amount_Limit_Failed', predictions

        # ============================================================
        # OPTIONAL: Loan Metrics Checks (Don't block approval)
        # ============================================================
        if nature_of_business and nature_of_business.lower() in ['salary', 'salaried']:
            logger.info(
                f"Application {record.get('Application_No')} has {nature_of_business} - auto-approving without metrics check")
            return True, [
                "✓ Salary/Salaried category - automatic approval without loan metrics check",
                amount_msg
            ], 'Salary_Bypass', predictions

        # For non-salary, run optional loan metrics checks (they don't block approval)
        logger.info(
            f"Application {record.get('Application_No')} (Gender: {gender}) has {nature_of_business} - running optional loan metrics check")
        logger.info(f"Predicted Business Type: {business_type}, Experience Level: {experience_level}")

        # Run optional checks - they always return True
        _, messages = self.check_loan_metrics_for_non_salary(record, business_type, experience_level)

        # Add the amount check message to the list
        messages.insert(0, amount_msg)

        return True, messages, 'Full_Metrics', predictions

    def send_approval_email(self, pre_disb_temp_id: int, approved_by: int, recipient_email: str, application_no: str) -> \
    Tuple[bool, str]:
        """
        Send approval letter email to branch and update email_status.
        """
        if self.dry_run:
            logger.info(f"🔍 [DRY RUN] Would send email to: {recipient_email}")
            logger.info(f"  - Application: {application_no}")
            logger.info(f"  - Would update email_status to 2")
            return True, f"[DRY RUN] Would send email to {recipient_email}"

        try:
            import requests

            email_url = "http://localhost:8000/send-email"

            payload = {
                "app_no": str(pre_disb_temp_id),
                "recipient_email": recipient_email,
                "user_id": approved_by
            }

            response = requests.post(email_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    update_email_query = f"""
                        UPDATE tbl_pre_disbursement_temp 
                        SET email_status = 2
                        WHERE pre_disb_temp_id = {pre_disb_temp_id}
                    """
                    execute_command(update_email_query)

                    logger.info(f"✓ Email sent and email_status updated to 2 for application {application_no}")
                    return True, f"Email sent to {recipient_email}"
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"✗ Failed to send email: {error_msg}")
                    return False, f"Failed to send email: {error_msg}"
            else:
                logger.error(f"✗ Email API returned status {response.status_code}")
                return False, f"Email API error: {response.status_code}"

        except Exception as e:
            logger.error(f"✗ Email sending failed: {str(e)}")
            return False, f"Email sending failed: {str(e)}"

    def auto_approve_application(self, record: Dict, approver: Dict, approval_type: str, predictions: Dict) -> Tuple[
        bool, str]:
        """
        Auto-approve a single application
        """
        pre_disb_temp_id = record.get('pre_disb_temp_id')
        application_no = record.get('Application_No')
        branch_name = record.get('Branch_Name')
        Approved_Amount = record.get('Loan_Amount')

        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime('%Y-%m-%d %H:%M:%S')

        predicted_business_type = predictions.get('predicted_business_type', '').replace("'", "''")
        predicted_experience_level = predictions.get('predicted_experience_level', '').replace("'", "''")
        gender = predictions.get('gender', '').replace("'", "''")

        if self.dry_run:
            logger.info(f"🔍 [DRY RUN] Would auto-approve application {application_no}")
            logger.info(f"  - Gender: {gender}")
            logger.info(f"  - Status would change from '{record.get('status')}' to '2'")
            logger.info(f"  - Approved by: {approver['name']}")
            logger.info(f"  - Approval date: {formatted_datetime}")
            logger.info(f"  - Approval type: {approval_type}")

            branch_email = self.get_branch_email(branch_name)
            if branch_email:
                logger.info(f"  - Would send email to branch: {branch_email}")
                logger.info(f"  - Would update email_status to 2")
            else:
                logger.warning(f"  - No branch email found for {branch_name}")

            self.log_auto_approval(record, approver, current_datetime, approval_type, predictions, dry_run=True)
            return True, f"[DRY RUN] Would auto-approve {application_no}"

        # Normal mode: Execute the update
        update_query = f"""
            UPDATE tbl_pre_disbursement_temp
            SET 
                status = '2',
                kft_approved_loan_limit = '{str(Approved_Amount)}',
                approved_by = '{approver['user_id']}',
                approved_date = '{formatted_datetime}',
                auto_approved = true,
                auto_approved_by = 'System',
                auto_approved_date = '{formatted_datetime}',
                auto_approval_type = '{approval_type}',
                predicted_business_type = '{predicted_business_type}',
                predicted_experience_level = '{predicted_experience_level}'
            WHERE pre_disb_temp_id = {pre_disb_temp_id}
        """

        try:
            execute_command(update_query)
            logger.info(f"Auto-approved application {application_no}")

            self.log_auto_approval(record, approver, current_datetime, approval_type, predictions, dry_run=False)

            # Send email to branch
            branch_email = self.get_branch_email(branch_name)

            if branch_email:
                logger.info(f"Sending approval email to branch: {branch_email}")
                email_success, email_message = self.send_approval_email(pre_disb_temp_id, approver['user_id'],
                                                                        branch_email, application_no)

                if email_success:
                    logger.info(f"✓ Email sent successfully")
                else:
                    logger.warning(f"⚠️ Email sending failed: {email_message}")
            else:
                logger.warning(f"No email found for branch {branch_name}, skipping email")

            return True, f"Successfully auto-approved {application_no}"

        except Exception as e:
            error_msg = f"Failed to auto-approve {application_no}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def log_auto_approval(self, record: Dict, approver: Dict, approved_datetime: datetime,
                          approval_type: str, predictions: Dict, dry_run: bool = False):
        """Log auto-approval details for audit trail"""
        predicted_business_type = predictions.get('predicted_business_type', '').replace("'", "''")
        predicted_experience_level = predictions.get('predicted_experience_level', '').replace("'", "''")
        calculated_years = predictions.get('calculated_years', 0)
        gender = predictions.get('gender', '')

        if dry_run:
            logger.info(f"🔍 [DRY RUN] Would insert into tbl_auto_approval_log:")
            logger.info(f"  record_id: {record.get('pre_disb_temp_id')}")
            logger.info(f"  application_no: {record.get('Application_No')}")
            logger.info(f"  borrower_name: {record.get('Borrower_Name')}")
            logger.info(f"  gender: {gender}")
            logger.info(f"  branch_name: {record.get('Branch_Name')}")
            logger.info(f"  loan_amount: {record.get('Loan_Amount')}")
            logger.info(f"  nature_of_business: {record.get('Nature_Of_Business')}")
            logger.info(f"  predicted_business_type: {predicted_business_type}")
            logger.info(f"  predicted_experience_level: {predicted_experience_level}")
            logger.info(f"  approval_type: {approval_type}")
            logger.info(f"  approved_by: {approver['name']}")
            return

        log_query = f"""
            INSERT INTO tbl_auto_approval_log (
                record_id,
                module,
                application_no,
                cnic,
                borrower_name,
                branch_name,
                loan_amount,
                gender,
                nature_of_business,
                predicted_business_type,
                experience_start_date,
                predicted_experience_level,
                calculated_experience_years,
                approval_type,
                approved_by,
                approved_by_id,
                approved_date,
                status,
                remarks
            ) VALUES (
                {record.get('pre_disb_temp_id')},
                'Student Finance',
                '{record.get('Application_No', '').replace("'", "''")}',
                '{record.get('CNIC', '').replace("'", "''")}',
                '{record.get('Borrower_Name', '').replace("'", "''")}',
                '{record.get('Branch_Name', '').replace("'", "''")}',
                {float(record.get('Loan_Amount', 0))},
                '{gender}',
                '{record.get('Nature_Of_Business', '').replace("'", "''")}',
                '{predicted_business_type}',
                '{record.get('experiense_start_date', '')}',
                '{predicted_experience_level}',
                {calculated_years},
                '{approval_type}',
                '{approver['name'].replace("'", "''")}',
                {approver.get('user_id', 0)},
                '{approved_datetime.strftime('%Y-%m-%d %H:%M:%S')}',
                'Approved',
                'Auto-approved by system - Type: {approval_type}, Gender: {gender}'
            )
        """

        try:
            execute_command(log_query)
            logger.info(f"Logged auto-approval for record {record.get('pre_disb_temp_id')}")
        except Exception as e:
            logger.error(f"Failed to log auto-approval: {str(e)}")

    def run_auto_approval_cycle(self) -> Dict:
        """
        Main method to run the auto-approval cycle
        """
        mode_text = "DRY RUN" if self.dry_run else "LIVE"
        logger.info("=" * 60)
        logger.info(f"Starting Student Finance Auto-Approval Cycle - {mode_text} MODE")
        logger.info("=" * 60)

        run_datetime = datetime.now()
        approved_applications = []
        failed_applications = []
        salary_approved = 0
        metrics_approved = 0
        male_approved = 0
        female_approved = 0

        # Get eligible applications
        eligible_apps = self.get_eligible_applications()

        if not eligible_apps:
            logger.info("No eligible applications found")
            return {
                'success': True,
                'dry_run': self.dry_run,
                'total_eligible': 0,
                'total_approved': 0,
                'total_failed': 0,
                'salary_approved': 0,
                'metrics_approved': 0,
                'male_approved': 0,
                'female_approved': 0,
                'approved_applications': [],
                'failed_applications': [],
                'run_timestamp': run_datetime.strftime('%Y-%m-%d %H:%M:%S')
            }

        logger.info(f"Found {len(eligible_apps)} eligible applications")

        # Get the auto-approval signatory (user with signature)
        approver = self.get_auto_approval_approver()

        if not approver:
            logger.error("No auto-approval approver found with signature. Aborting cycle.")
            return {
                'success': False,
                'dry_run': self.dry_run,
                'total_eligible': len(eligible_apps),
                'total_approved': 0,
                'total_failed': len(eligible_apps),
                'salary_approved': 0,
                'metrics_approved': 0,
                'male_approved': 0,
                'female_approved': 0,
                'approved_applications': [],
                'failed_applications': [
                    {'application_no': 'N/A', 'reason': 'No auto-approval signatory found with signature'}],
                'run_timestamp': run_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'error': 'No auto-approval signatory found'
            }

        # Process each application
        for app in eligible_apps:
            logger.info(f"\n{'=' * 50}")
            logger.info(f"Processing: {app.get('Application_No')}")
            logger.info(f"{'=' * 50}")
            logger.info(f"Gender: {app.get('Gender')}")
            logger.info(f"Original Nature: {app.get('Nature_Of_Business')}")
            logger.info(f"Experience Start Date: {app.get('experiense_start_date')}")
            logger.info(f"Loan Amount: {app.get('Loan_Amount')}")
            logger.info(f"Loan Cycle: {app.get('Loan_Cycle')}")
            logger.info(f"DBR: {app.get('Dbr')}")
            logger.info(f"Credit History: {app.get('credit_history_ecib')}")

            # Evaluate application
            approved, evaluation_messages, approval_type, predictions = self.evaluate_application(app)

            # Log predictions
            logger.info(f"\n📊 Predictions:")
            logger.info(f"  Gender: {predictions['gender']}")
            logger.info(f"  Predicted Business Type: {predictions['predicted_business_type']}")
            logger.info(f"  Predicted Experience Level: {predictions['predicted_experience_level']}")
            logger.info(f"  Calculated Years: {predictions['calculated_years']:.2f}")

            logger.info(f"\n📋 Evaluation Results:")
            for msg in evaluation_messages:
                logger.info(f"  {msg}")

            if approved:
                success, message = self.auto_approve_application(app, approver, approval_type, predictions)

                if success:
                    if approval_type == 'Salary_Bypass':
                        salary_approved += 1
                    else:
                        metrics_approved += 1

                    # Track by gender
                    if app.get('Gender', '').lower() == 'male':
                        male_approved += 1
                    elif app.get('Gender', '').lower() == 'female':
                        female_approved += 1

                    approved_applications.append({
                        'application_no': app.get('Application_No'),
                        'borrower_name': app.get('Borrower_Name'),
                        'gender': app.get('Gender'),
                        'branch': app.get('Branch_Name'),
                        'amount': app.get('Loan_Amount'),
                        'nature_of_business': app.get('Nature_Of_Business'),
                        'predicted_business_type': predictions['predicted_business_type'],
                        'predicted_experience_level': predictions['predicted_experience_level'],
                        'approval_type': approval_type,
                        'approver': approver['name'],
                        'messages': evaluation_messages
                    })

                    if self.dry_run:
                        logger.info(f"✅ [DRY RUN] WOULD APPROVE: {app.get('Application_No')}")
                    else:
                        logger.info(f"✅ APPROVED: {app.get('Application_No')}")
                else:
                    failed_applications.append({
                        'application_no': app.get('Application_No'),
                        'gender': app.get('Gender'),
                        'nature_of_business': app.get('Nature_Of_Business'),
                        'predicted_business_type': predictions['predicted_business_type'],
                        'reason': message
                    })
                    logger.error(f"❌ FAILED: {app.get('Application_No')} - {message}")
            else:
                failed_applications.append({
                    'application_no': app.get('Application_No'),
                    'gender': app.get('Gender'),
                    'nature_of_business': app.get('Nature_Of_Business'),
                    'predicted_business_type': predictions['predicted_business_type'],
                    'predicted_experience_level': predictions['predicted_experience_level'],
                    'reason': ' | '.join(evaluation_messages)
                })
                logger.info(f"❌ NOT APPROVED: {app.get('Application_No')}")

        # Generate summary
        summary = {
            'dry_run': self.dry_run,
            'run_timestamp': run_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'total_eligible': len(eligible_apps),
            'total_approved': len(approved_applications),
            'total_failed': len(failed_applications),
            'salary_approved': salary_approved,
            'metrics_approved': metrics_approved,
            'male_approved': male_approved,
            'female_approved': female_approved,
            'approved_applications': approved_applications,
            'failed_applications': failed_applications
        }

        logger.info("\n" + "=" * 60)
        logger.info(f"CYCLE COMPLETE - {mode_text} MODE")
        logger.info(f"  Total Eligible: {summary['total_eligible']}")
        logger.info(f"  Total Approved: {summary['total_approved']}")
        logger.info(f"  Total Failed: {summary['total_failed']}")
        logger.info(f"  Salary Bypass: {salary_approved}")
        logger.info(f"  Full Metrics: {metrics_approved}")
        logger.info(f"  Male Approved: {male_approved}")
        logger.info(f"  Female Approved: {female_approved}")
        if self.dry_run:
            logger.info("⚠️  DRY RUN - No actual changes were made to the database")
        logger.info("=" * 60)

        # Send summary email to all approvers
        if not self.dry_run or (self.dry_run and len(eligible_apps) > 0):
            self.send_summary_email_to_approvers(summary, approved_applications, failed_applications, run_datetime)
        else:
            logger.info("No eligible applications found, skipping summary email")

        return summary


# Standalone function to run auto-approval
def run_student_finance_auto_approval(dry_run: bool = False):
    """
    Entry point for running auto-approval.

    Args:
        dry_run: If True, no database changes will be made (preview only)
    """
    approver = StudentFinanceAutoApprover(dry_run=dry_run)
    result = approver.run_auto_approval_cycle()

    # Print detailed summary
    mode_text = "DRY RUN (Preview Only)" if dry_run else "LIVE"
    print("\n" + "=" * 80)
    print(f"AUTO-APPROVAL SUMMARY REPORT - {mode_text}")
    print("=" * 80)
    print(f"Run Time: {result['run_timestamp']}")
    print(f"Total Eligible Applications: {result['total_eligible']}")
    print(f"Total Approved: {result['total_approved']}")
    print(f"  ├─ Salary/Salaried Bypass: {result['salary_approved']}")
    print(f"  └─ Full Metrics Check: {result['metrics_approved']}")
    print(f"\nGender Breakdown:")
    print(f"  ├─ Male Approved: {result['male_approved']}")
    print(f"  └─ Female Approved: {result['female_approved']}")
    print(f"\nTotal Failed: {result['total_failed']}")

    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes were made to the database")
        print("   Remove dry_run=True to execute actual approvals\n")

    if result['approved_applications']:
        print("\n" + "─" * 80)
        print("✓ APPROVED APPLICATIONS:")
        print("─" * 80)
        for app in result['approved_applications']:
            print(f"\n  Application: {app['application_no']}")
            print(f"    Borrower: {app['borrower_name']}")
            print(f"    Gender: {app['gender']}")
            print(f"    Branch: {app['branch']}")
            print(f"    Amount: {app['amount']}")
            print(f"    Original Nature: {app['nature_of_business']}")
            print(f"    Predicted Business Type: {app['predicted_business_type']}")
            print(f"    Predicted Experience: {app['predicted_experience_level']}")
            print(f"    Approval Type: {app['approval_type']}")
            print(f"    Approved By: {app['approver']}")

    if result['failed_applications']:
        print("\n" + "─" * 80)
        print("✗ FAILED APPLICATIONS:")
        print("─" * 80)
        for app in result['failed_applications']:
            print(f"\n  Application: {app['application_no']}")
            print(f"    Gender: {app.get('gender', 'N/A')}")
            print(f"    Nature: {app['nature_of_business']}")
            print(f"    Predicted Type: {app.get('predicted_business_type', 'N/A')}")
            print(f"    Reason: {app['reason']}")

    print("\n" + "=" * 80)

    # Save summary to file
    filename = f"auto_approval_summary_{'DRYRUN' if dry_run else 'LIVE'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n📄 Summary saved to: {filename}")

    return result


# Example usage
if __name__ == "__main__":

    with application.app_context():
        import sys

        # Check command line arguments
        if len(sys.argv) > 1 and sys.argv[1].lower() == '--dry-run':
            print("\n🔍 Running in DRY RUN mode - No database changes will be made\n")
            result = run_student_finance_auto_approval(dry_run=True)
        else:
            print("\n⚠️  Running in LIVE mode - Database changes WILL be made")
            confirm = input("Are you sure you want to run LIVE approval? (yes/no): ")
            if confirm.lower() == 'yes':
                result = run_student_finance_auto_approval(dry_run=False)
            else:
                result = run_student_finance_auto_approval(dry_run=True)