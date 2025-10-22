from imports import *
from application import application


@application.route('/manage_post_disbursement')
def manage_post_disbursement():
    try:
        if is_login():
            # print('record fetch post disbursement:- ', len(get_all_post_disbursement_info()))
            content = {'get_all_post_disbursement_info': get_all_post_disbursement_info()}
            return render_template('manage_post_disbursement.html', result=content)
    except Exception as e:
        print(e)
        print('manage post disbursement exception:- ', str(e.__dict__))
    return redirect(url_for('login'))


@application.route('/get_disbursement_details/<int:post_disb_id>')
def get_disbursement_details(post_disb_id):
    try:
        if is_login():  # Add any other permission checks you need

            disbursement = get_all_post_disbursement_info_by_id(post_disb_id)[0]

            if disbursement:
                # Create a detailed HTML view of the record
                details_html = f"""
                <div class="row">
                    <div class="col-md-6">
                        <h5>Loan Information</h5>
                        <table class="table table-sm">
                            <tr>
                                <th>Loan Number:</th>
                                <td>{disbursement['loan_no']}</td>
                            </tr>
                            <tr>
                                <th>Loan Title:</th>
                                <td>{disbursement['loan_title']}</td>
                            </tr>
                            <tr>
                                <th>Product Code:</th>
                                <td>{disbursement['product_code']}</td>
                            </tr>
                            <tr>
                                <th>Disbursed Amount:</th>
                                <td>{disbursement['disbursed_amount']}</td>
                            </tr>
                            <tr>
                                <th>Principal Outstanding:</th>
                                <td>{disbursement['principal_outstanding']}</td>
                            </tr>
                        </table>
                    </div>
                    <div class="col-md-6">
                        <h5>Customer Information</h5>
                        <table class="table table-sm">
                            <tr>
                                <th>CNIC:</th>
                                <td>{disbursement['cnic']}</td>
                            </tr>
                            <tr>
                                <th>Gender:</th>
                                <td>{disbursement['gender']}</td>
                            </tr>
                            <tr>
                                <th>Branch:</th>
                                <td>{disbursement['branch_name']} ({disbursement['branch_code']})</td>
                            </tr>
                            <tr>
                                <th>Area:</th>
                                <td>{disbursement['area']}</td>
                            </tr>
                        </table>
                    </div>
                </div>
                <div class="row mt-3">
                    <div class="col-md-12">
                        <h5>Additional Details</h5>
                        <table class="table table-sm">
                            <tr>
                                <th>Booked On:</th>
                                <td>{disbursement['booked_on']}</td>
                            </tr>
                            <tr>
                                <th>Repayment Type:</th>
                                <td>{disbursement['repayment_type']}</td>
                            </tr>
                            <tr>
                                <th>Sector:</th>
                                <td>{disbursement['sector']}</td>
                            </tr>
                            <tr>
                                <th>Purpose:</th>
                                <td>{disbursement['purpose']}</td>
                            </tr>
                            <tr>
                                <th>Loan Status:</th>
                                <td>{disbursement['loan_status']}</td>
                            </tr>
                            <tr>
                                <th>Overdue Days:</th>
                                <td>{disbursement['overdue_days']}</td>
                            </tr>
                        </table>
                    </div>
                </div>
                """
                return details_html
            else:
                return "<div class='alert alert-warning'>Record not found</div>"
        else:
            return "<div class='alert alert-danger'>Unauthorized access</div>"
    except Exception as e:
        print(f"Error fetching disbursement details: {str(e)}")
        return "<div class='alert alert-danger'>Error loading details</div>"


@application.route('/get_on_going_loan_details')
def get_on_going_loan_details():
    try:
        # Get CNIC from query parameter
        cnic = request.args.get('cnic')
        if not cnic:
            return jsonify({'success': False, 'error': 'CNIC is required'}), 400


        current_time = datetime.now().strftime('%Y-%m-%d')

        # Query to fetch on-going loan details
        query = f"""
            SELECT loan_no, cnic, loan_closed_on, mis_date, disbursed_amount, product_code,
            booked_on, markup_outstanding, principal_outstanding, loan_closed_on, overdue_days,
            loan_status, purpose
            FROM tbl_post_disbursement
            WHERE CNIC = '{cnic}' ORDER BY mis_date DESC LIMIT 3
        """
        result = fetch_records(query)
        print(result)
        # Convert result to list of dictionaries
        records = []
        for row in result:
            record = {
                'loan_no': row['loan_no'],
                'cnic': row['cnic'],
                'disbursed_amount': row['disbursed_amount'],
                'booked_on': row['booked_on'],
                'principal_outstanding': row['principal_outstanding'],
                'markup_outstanding': row['markup_outstanding'],
                'purpose': row['purpose'],
                'loan_status': row['loan_status'],
                'overdue_days': row['overdue_days'],
                'loan_closed_on': row['loan_closed_on'],
                'mis_date': row['mis_date'].strftime('%Y-%m-%d %H:%M:%S') if row['mis_date'] else None,
                'product_code': row['product_code']
            }
            records.append(record)

        return jsonify({'success': True, 'records': records})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@application.route('/post_disbursement_report')
def post_disbursement_report():
    try:
        if is_login() and (is_admin() or is_executive_approver()):
            query = "select DISTINCT(product_code) from tbl_loan_products"
            product_list = fetch_records(query)

            query = "select branch from tbl_branches"
            branch_list = fetch_records(query)

            query = "select DISTINCT(area) from tbl_branches"
            area_list = fetch_records(query)

            query = "select DISTINCT(loan_status) from tbl_post_disbursement"
            loan_status_list = fetch_records(query)

            content = {
                'product_list': product_list,
                'branch_list': branch_list,
                'area_list': area_list,
                'loan_status_list': loan_status_list,
                'get_all_bank_distributions': get_all_bank_distributions(),
                'get_all_national_council_distributions': get_all_national_council_distributions(),
                'get_all_kft_distributions': get_all_kft_distributions(),
            }
            return render_template('post_disbursement_report.html', result=content)
    except Exception as e:
        print(e)
        print('manage post post_disbursement_report exception:- ', str(e.__dict__))
    return redirect(url_for('login'))


@application.route('/get_post_disbursement_report_data', methods=['POST'])
def get_post_disbursement_report_data():
    try:
        filters = request.get_json()
        query = """
            SELECT 
                p.id,
                p.mis_date,
                p.area,
                p.branch_code,
                p.branch_name,
                p.cnic,
                p.gender,
                p.mobile_no,
                p.loan_no,
                p.loan_title,
                p.product_code,
                p.booked_on,
                p.disbursed_amount,
                p.principal_outstanding,
                p.markup_outstanding,
                p.repayment_type,
                p.sector,
                p.purpose,
                p.loan_status,
                p.overdue_days,
                p.loan_closed_on,
                p.collateral_title,
                bdd.bank_distribution_name as bank_distribution,
                ncd.national_council_distribution_name as national_council_distribution,
                kd.kft_distribution_name as kft_distribution,
                b.branch,
                b.area,
                b.branch_manager
            FROM tbl_post_disbursement p
            LEFT JOIN tbl_branches b ON p.branch_code = b.branch_code
            LEFT JOIN tbl_bank_details bd ON bd.bank_id = b.bank_id
            LEFT JOIN tbl_bank_distribution bdd ON bdd.bank_distribution_id = b.bank_distribution
            LEFT JOIN tbl_national_council_distribution ncd ON ncd.national_council_distribution_id = b.national_council_distribution
            LEFT JOIN tbl_kft_distribution kd ON kd.kft_distribution_id = b.kft_distribution
            WHERE 1=1
        """

        # Apply filters using f-strings
        if filters.get('mis_date'):
            query += f" AND DATE(p.mis_date) = '{filters['mis_date']}'"

        if filters.get('product_code'):
            product_codes = "', '".join(filters['product_code'])
            query += f" AND p.product_code IN ('{product_codes}')"

        if filters.get('gender'):
            query += f" AND p.gender = '{filters['gender']}'"

        if filters.get('disbursed_amount_min'):
            query += f" AND p.disbursed_amount >= {float(filters['disbursed_amount_min'])}"

        if filters.get('disbursed_amount_max'):
            query += f" AND p.disbursed_amount <= {float(filters['disbursed_amount_max'])}"

        if filters.get('principal_outstanding_min'):
            query += f" AND p.principal_outstanding >= {float(filters['principal_outstanding_min'])}"

        if filters.get('principal_outstanding_max'):
            query += f" AND p.principal_outstanding <= {float(filters['principal_outstanding_max'])}"

        if filters.get('loan_status'):
            loan_statuses = "', '".join(filters['loan_status'])
            query += f" AND p.loan_status IN ('{loan_statuses}')"

        if filters.get('branch'):
            branches = "', '".join(filters['branch'])
            query += f" AND b.branch IN ('{branches}')"

        if filters.get('bank_area'):
            bank_areas = "', '".join(filters['bank_area'])
            query += f" AND b.area IN ('{bank_areas}')"

        if filters.get('bank_distribution'):
            bank_distributions = "', '".join(filters['bank_distribution'])
            query += f" AND b.bank_distribution IN ('{bank_distributions}')"

        if filters.get('nc_distribution'):
            nc_distributions = "', '".join(filters['nc_distribution'])
            query += f" AND b.national_council_distribution IN ('{nc_distributions}')"

        if filters.get('kft_distribution'):
            kft_distributions = "', '".join(filters['kft_distribution'])
            query += f" AND b.kft_distribution IN ('{kft_distributions}')"

        # Sorting
        sort_field = {
            'asc': 'ASC',
            'desc': 'DESC'
        }
        if filters.get('booked_on'):
            query += f" ORDER BY p.booked_on {sort_field.get(filters['booked_on'], 'ASC')}"
        elif filters.get('loan_closed_on'):
            query += f" ORDER BY p.loan_closed_on {sort_field.get(filters['loan_closed_on'], 'ASC')}"
        elif filters.get('repayment_type'):
            query += f" ORDER BY p.repayment_type {sort_field.get(filters['repayment_type'], 'ASC')}"
        elif filters.get('sector'):
            query += f" ORDER BY p.sector {sort_field.get(filters['sector'], 'ASC')}"
        elif filters.get('purpose'):
            query += f" ORDER BY p.purpose {sort_field.get(filters['purpose'], 'ASC')}"

        print(query)

        rows = fetch_records(query)

        return jsonify({'success': True, 'records': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

