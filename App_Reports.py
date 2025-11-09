from imports import *
from application import application


@application.route('/fund-projection-report')
def fund_projection_report():
    try:
        if is_login() and (is_admin() or is_executive_approver()):
            content = {
                'get_all_bank_details': get_all_bank_details(),
                'get_all_banks_last_entry_records': get_all_banks_last_entry_records(),
                'get_outstanding_loans': get_outstanding_loans(),
                'post_disbursement_by_booked_on': post_disbursement_by_booked_on()
            }
            return render_template('fund_projection_report.html', result=content)
    except Exception as e:
        print('fund projection report exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/save_fund_projection', methods=['POST'])
def save_fund_projection():
    try:
        data = request.get_json()

        # Extract data from JSON
        bank_id = data.get('bank_id')
        account_balance = data.get('account_balance', 'NULL').replace(',', '') or 'NULL'
        actual_data_date = data.get('actual_data_date', 'NULL') or 'NULL'
        report_date = data.get('report_date', 'NULL') or 'NULL'
        actual_portfolio = data.get('actual_portfolio', 'NULL').replace(',', '') or 'NULL'
        ten_percent_lien = data.get('ten_percent_lien', 'NULL').replace(',', '') or 'NULL'
        total_lien_amount = data.get('total_lien_amount', 'NULL').replace(',', '') or 'NULL'
        actual_collateral_balance = data.get('actual_collateral_balance', 'NULL').replace(',', '') or 'NULL'
        surplus_shortfall = data.get('surplus_shortfall', 'NULL').replace(',', '') or 'NULL'
        projected_disbursement = data.get('projected_disbursement', 'NULL') or 'NULL'
        seasonal_affects = data.get('seasonal_affects', 'NULL') or 'NULL'
        new_product_affects = data.get('new_product_affects', 'NULL') or 'NULL'
        total_projected_disbursement = data.get('total_projected_disbursement', 'NULL').replace(',', '') or 'NULL'
        projected_recoveries = data.get('projected_recoveries', 'NULL').replace(',', '') or 'NULL'
        projected_monthly_change = data.get('projected_monthly_change', 'NULL').replace(',', '') or 'NULL'
        actual_portfolio_opening = data.get('actual_portfolio_opening', 'NULL').replace(',', '') or 'NULL'
        add_projected_monthly_change = data.get('add_projected_monthly_change', 'NULL').replace(',', '') or 'NULL'
        projected_portfolio_closing = data.get('projected_portfolio_closing', 'NULL').replace(',', '') or 'NULL'
        cushion_ten_percent = data.get('cushion_ten_percent', 'NULL').replace(',', '') or 'NULL'
        projected_collateral_balance = data.get('projected_collateral_balance', 'NULL').replace(',', '') or 'NULL'
        actual_collateral_balance_req = data.get('actual_collateral_balance_req', 'NULL').replace(',', '') or 'NULL'
        surplus_shortfall_req = data.get('surplus_shortfall_req', 'NULL').replace(',', '') or 'NULL'

        # Construct SQL query using f-string
        query = f"""
        INSERT INTO tbl_fund_projection_reports (
            bank_id, account_balance, actual_data_date, report_date, actual_portfolio,
            ten_percent_lien, total_lien_amount, actual_collateral_balance, surplus_shortfall,
            projected_disbursement, seasonal_affects, new_product_affects,
            total_projected_disbursement, projected_recoveries, projected_monthly_change,
            actual_portfolio_opening, add_projected_monthly_change, projected_portfolio_closing,
            cushion_ten_percent, projected_collateral_balance, actual_collateral_balance_req,
            surplus_shortfall_req
        ) VALUES (
            {bank_id}, {account_balance}, '{actual_data_date}', '{report_date}', {actual_portfolio},
            {ten_percent_lien}, {total_lien_amount}, {actual_collateral_balance}, {surplus_shortfall},
            {projected_disbursement}, {seasonal_affects}, {new_product_affects},
            {total_projected_disbursement}, {projected_recoveries}, {projected_monthly_change},
            {actual_portfolio_opening}, {add_projected_monthly_change}, {projected_portfolio_closing},
            {cushion_ten_percent}, {projected_collateral_balance}, {actual_collateral_balance_req},
            {surplus_shortfall_req}
        )
        """

        # Execute the query using execute_command
        execute_command(query)

        return jsonify({'status': 'success', 'message': 'Fund projection report saved successfully'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# New route to fetch available report dates
@application.route('/get_report_dates', methods=['GET'])
def get_report_dates():
    try:
        bank_id = request.args.get('bank_id')
        print('bank_id:- ', bank_id)
        if not bank_id:
            return jsonify({'status': 'error', 'message': 'Bank ID is required'}), 400

        query = f"""
        SELECT DISTINCT created_at
        FROM tbl_fund_projection_reports
        WHERE bank_id = {bank_id}
        ORDER BY created_at DESC
        """

        # Assuming execute_command returns a list of records
        result = fetch_records(query)
        print(result)
        dates = [row['created_at'] for row in result] if result else []

        return jsonify({'status': 'success', 'dates': dates}), 200

    except Exception as e:
        print('get_report_dates exception:- ', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


# New route to fetch report data for a specific date
@application.route('/get_report_data', methods=['GET'])
def get_report_data():
    try:
        bank_id = request.args.get('bank_id')
        report_date = request.args.get('report_date')
        if not bank_id or not report_date:
            return jsonify({'status': 'error', 'message': 'Bank ID and report date are required'}), 400

        # Parse the RFC1123 date string to a Python datetime object
        report_date_obj = datetime.strptime(str(report_date), '%a, %d %b %Y %H:%M:%S GMT')

        # Format the datetime object to a string compatible with PostgreSQL
        formatted_report_date = report_date_obj.strftime('%Y-%m-%d %H:%M:%S')
        report_date = formatted_report_date
        print('report_date:- ', report_date)

        query = f"""
            SELECT *
            FROM tbl_fund_projection_reports
            WHERE bank_id = '{bank_id}'
              AND date_trunc('second', created_at) = '{report_date}'::timestamp
            LIMIT 1;
        """

        # Assuming fetch_records returns a list of dictionaries
        result = fetch_records(query, is_print=True)
        print(result)
        if not result:
            return jsonify({'status': 'error', 'message': 'No report found for the selected date'}), 404

        # Extract the first record
        record = result[0]

        # Convert the result to a dictionary, handling Decimal and datetime
        report = {
            'bank_id': str(record['bank_id']),
            'account_balance': str(record['account_balance']) if record['account_balance'] is not None else '0',
            'actual_data_date': record['actual_data_date'].strftime('%Y-%m-%d') if isinstance(record['actual_data_date'], date) else str(record['actual_data_date']),
            'report_date': record['report_date'].strftime('%Y-%m-%d') if isinstance(record['report_date'], date) else str(record['report_date']),
            'actual_portfolio': str(record['actual_portfolio']) if record['actual_portfolio'] is not None else '0',
            'ten_percent_lien': str(record['ten_percent_lien']) if record['ten_percent_lien'] is not None else '0',
            'total_lien_amount': str(record['total_lien_amount']) if record['total_lien_amount'] is not None else '0',
            'actual_collateral_balance': str(record['actual_collateral_balance']) if record['actual_collateral_balance'] is not None else '0',
            'surplus_shortfall': str(record['surplus_shortfall']) if record['surplus_shortfall'] is not None else '0',
            'projected_disbursement': str(record['projected_disbursement']) if record['projected_disbursement'] is not None else '0',
            'seasonal_affects': str(record['seasonal_affects']) if record['seasonal_affects'] is not None else '0',
            'new_product_affects': str(record['new_product_affects']) if record['new_product_affects'] is not None else '0',
            'total_projected_disbursement': str(record['total_projected_disbursement']) if record['total_projected_disbursement'] is not None else '0',
            'projected_recoveries': str(record['projected_recoveries']) if record['projected_recoveries'] is not None else '0',
            'projected_monthly_change': str(record['projected_monthly_change']) if record['projected_monthly_change'] is not None else '0',
            'actual_portfolio_opening': str(record['actual_portfolio_opening']) if record['actual_portfolio_opening'] is not None else '0',
            'add_projected_monthly_change': str(record['add_projected_monthly_change']) if record['add_projected_monthly_change'] is not None else '0',
            'projected_portfolio_closing': str(record['projected_portfolio_closing']) if record['projected_portfolio_closing'] is not None else '0',
            'cushion_ten_percent': str(record['cushion_ten_percent']) if record['cushion_ten_percent'] is not None else '0',
            'projected_collateral_balance': str(record['projected_collateral_balance']) if record['projected_collateral_balance'] is not None else '0',
            'actual_collateral_balance_req': str(record['actual_collateral_balance_req']) if record['actual_collateral_balance_req'] is not None else '0',
            'surplus_shortfall_req': str(record['surplus_shortfall_req']) if record['surplus_shortfall_req'] is not None else '0'
        }

        return jsonify({'status': 'success', 'report': report}), 200

    except Exception as e:
        print('get_report_data exception:', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@application.route('/fund_projected_vs_disbursement')
def fund_projected_vs_disbursement():
    try:
        if is_login() and (is_admin() or is_executive_approver()):

            # query = """
            #     WITH LatestMonth AS (
            #         SELECT
            #             report_date,
            #             total_projected_disbursement,
            #             projected_recoveries,
            #             ROW_NUMBER() OVER (PARTITION BY TO_CHAR(report_date, 'Mon-YYYY')
            #                               ORDER BY created_at DESC) AS rn
            #         FROM tbl_fund_projection_reports
            #         WHERE TO_CHAR(report_date, 'YYYY-MM') = (
            #             SELECT TO_CHAR(MAX(report_date), 'YYYY-MM')
            #             FROM tbl_fund_projection_reports
            #         )
            #     ),
            #     Disbursement AS (
            #         SELECT
            #             SUM(disbursed_amount) AS disbursement
            #         FROM tbl_post_disbursement
            #         WHERE DATE_TRUNC('month', mis_date) = (
            #             SELECT DATE_TRUNC('month', MAX(mis_date))
            #             FROM tbl_post_disbursement
            #         )
            #     )
            #     SELECT
            #         TO_CHAR(lm.report_date, 'Mon-YYYY') AS month_year,
            #         lm.total_projected_disbursement,
            #         lm.projected_recoveries,
            #         d.disbursement
            #     FROM LatestMonth lm
            #     CROSS JOIN Disbursement d
            #     WHERE lm.rn = 1;
            # """


            # query = """
            #     WITH LatestMonth AS (
            #         SELECT
            #             report_date,
            #             total_projected_disbursement,
            #             projected_recoveries,
            #             ROW_NUMBER() OVER (PARTITION BY TO_CHAR(report_date, 'YYYY-MM')
            #                               ORDER BY created_at DESC) AS rn
            #         FROM tbl_fund_projection_reports
            #     ),
            #     Disbursement AS (
            #         SELECT
            #             SUM(disbursed_amount) AS disbursement
            #         FROM tbl_post_disbursement
            #         WHERE DATE_TRUNC('month', mis_date) = (
            #             SELECT DATE_TRUNC('month', MAX(mis_date))
            #             FROM tbl_post_disbursement
            #         )
            #     )
            #     SELECT
            #         TO_CHAR(lm.report_date, 'Mon-YYYY') AS month_year,
            #         lm.total_projected_disbursement,
            #         lm.projected_recoveries,
            #         d.disbursement
            #     FROM LatestMonth lm
            #     CROSS JOIN Disbursement d
            #     WHERE lm.rn = 1
            #     ORDER BY lm.report_date;
            # """

            query = """
                WITH LatestMonth AS (
                    SELECT 
                        report_date,
                        total_projected_disbursement,
                        projected_recoveries,
                        ROW_NUMBER() OVER (PARTITION BY TO_CHAR(report_date, 'YYYY-MM') 
                                          ORDER BY created_at DESC) AS rn
                    FROM tbl_fund_projection_reports
                ),
                Disbursement AS (
                    SELECT 
                        SUM(disbursed_amount) AS disbursement,
                        DATE_TRUNC('month', booked_on) AS booked_month
                    FROM tbl_post_disbursement
                    GROUP BY DATE_TRUNC('month', booked_on)
                )
                SELECT 
                    TO_CHAR(lm.report_date, 'Mon-YYYY') AS month_year,
                    lm.total_projected_disbursement,
                    lm.projected_recoveries,
                    d.disbursement
                FROM LatestMonth lm
                LEFT JOIN Disbursement d
                    ON DATE_TRUNC('month', lm.report_date) = d.booked_month
                WHERE lm.rn = 1
                ORDER BY lm.report_date;
            """

            result = fetch_records(query)

            content = {
                'fund_projection_data': result,
            }
            return render_template('fund_projected_vs_disbursement.html', result=content)
    except Exception as e:
        print('fund projected vs disbursement exception:- ', str(e))
    return redirect(url_for('login'))


# --------------------------------------------------------------
# 1. Render the page (same as before)
# --------------------------------------------------------------
@application.route('/loan_projection_report')
def loan_projection_report():
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
            return redirect(url_for('login'))

        # Product list
        prod_sql = "SELECT DISTINCT product_code FROM tbl_post_disbursement ORDER BY product_code"
        product_list = fetch_records(prod_sql)

        return render_template(
            'loan_projection_report.html',
            result={'product_list': product_list}
        )
    except Exception as e:
        print('loan_projection_report error:', e)
        return redirect(url_for('login'))


@application.route('/get_loan_projection_report_data', methods=['POST'])
def get_loan_projection_report_data():
    try:
        filters = request.get_json() or {}

        # ------------------------------------------------------------------
        # Base CTE – PostgreSQL (with fixes)
        # ------------------------------------------------------------------
        query = """
            WITH monthly_data AS (
                SELECT
                    TO_CHAR(booked_on, 'Mon-YYYY') AS "Month",
                    SUM(disbursed_amount) AS "Actual Disbursement",
                    COUNT(DISTINCT cnic)::INTEGER AS "Actual No of Beneficiaries",
                    MIN(booked_on) AS month_start
                FROM tbl_post_disbursement
                WHERE 1=1
        """

        # ------------------ FILTER: Product ------------------
        product_codes = [code for code in filters.get('product_code', []) if code]
        if product_codes:
            safe_codes = "', '".join(code.replace("'", "''") for code in product_codes)
            query += f" AND product_code IN ('{safe_codes}')"

        # ------------------ FILTER: Historical Growth ------------------
        growth = filters.get('historical_growth')
        if growth and growth != 'all':
            months_map = {
                'last_3_months': 3, 'last_6_months': 6,
                'last_9_months': 9, 'last_12_months': 12
            }
            months = months_map[growth]
            query += f" AND booked_on >= CURRENT_DATE - INTERVAL '{months} months'"

        # ------------------ FILTER: Projection For ------------------
        proj = filters.get('projection_for')
        if proj == 'current_month':
            query += " AND DATE_TRUNC('month', booked_on) = DATE_TRUNC('month', CURRENT_DATE)"
        elif proj == 'current_year':
            query += " AND DATE_PART('year', booked_on) = DATE_PART('year', CURRENT_DATE)"

        # ------------------ Complete monthly_data ------------------
        query += """
                GROUP BY TO_CHAR(booked_on, 'Mon-YYYY'), DATE_TRUNC('month', booked_on)
            ),
            ranked_data AS (
                SELECT
                    "Month",
                    "Actual Disbursement",
                    "Actual No of Beneficiaries",
                    month_start,
                    LAG("Actual Disbursement") OVER (ORDER BY month_start) AS prev_disbursement,
                    LAG("Actual No of Beneficiaries") OVER (ORDER BY month_start) AS prev_beneficiaries
                FROM monthly_data
            )
            SELECT
                "Month",
                "Actual Disbursement",
                "Actual No of Beneficiaries",
                CASE WHEN prev_disbursement IS NOT NULL
                     THEN "Actual Disbursement" - prev_disbursement
                     ELSE NULL END AS growth_disbursement_amount,
                CASE WHEN prev_disbursement IS NOT NULL AND prev_disbursement > 0
                     THEN ROUND((("Actual Disbursement" - prev_disbursement) * 100.0 / prev_disbursement), 2)
                     ELSE NULL END AS growth_disbursement_percentage,
                CASE WHEN prev_beneficiaries IS NOT NULL
                     THEN ("Actual No of Beneficiaries" - prev_beneficiaries)::INTEGER
                     ELSE NULL END AS growth_beneficiaries_count,
                CASE WHEN prev_beneficiaries IS NOT NULL AND prev_beneficiaries > 0
                     THEN ROUND((("Actual No of Beneficiaries" - prev_beneficiaries) * 100.0 / prev_beneficiaries), 2)
                     ELSE NULL END AS growth_beneficiaries_percentage
            FROM ranked_data
            ORDER BY month_start;  -- Chronological order
        """

        print("Final Query:\n", query)
        rows = fetch_records(query)

        return jsonify({'success': True, 'records': rows})

    except Exception as e:
        print("Error:", str(e))
        return jsonify({'success': False, 'error': str(e)})