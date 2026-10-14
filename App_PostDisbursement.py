from imports import *
from application import application


@application.route('/manage_post_disbursement')
def manage_post_disbursement():
    try:
        if is_login():
            # The rows are loaded by the page from /manage_post_disbursement/data (the full list is ~60k rows)
            return render_template('manage_post_disbursement.html', result={})
    except Exception as e:
        print(e)
        print('manage post disbursement exception:- ', str(e.__dict__))
    return redirect(url_for('login'))


@application.route('/manage_post_disbursement/data')
def manage_post_disbursement_data():
    """Same records as before, as compact arrays (much smaller than HTML rows):
    [id, mis_date, branch_code, branch_name, loan_no, loan_title, cnic, disbursed, outstanding, loan_status, overdue_days]"""
    if not is_login():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        def iso(d):
            return d.isoformat()[:10] if hasattr(d, 'isoformat') else (str(d)[:10] if d else None)
        def num(v):
            try:
                return float(v) if v not in (None, '') else None
            except (TypeError, ValueError):
                return None
        rows = [[r['id'], iso(r['mis_date']), r['branch_code'], r['branch_name'], r['loan_no'], r['loan_title'], r['cnic'],
                 num(r['disbursed_amount']), num(r['principal_outstanding']), r['loan_status'],
                 int(num(r['overdue_days']) or 0)]
                for r in get_all_post_disbursement_info()]
        return jsonify({'success': True, 'rows': rows})
    except Exception as e:
        print('manage post disbursement data exception:- ', str(e))
        return jsonify({'success': False, 'error': 'Could not load the records'}), 500


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
        if not is_login():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        # Get CNIC from query parameter
        cnic = request.args.get('cnic')
        if not cnic:
            return jsonify({'success': False, 'error': 'CNIC is required'}), 400


        current_time = datetime.now().strftime('%Y-%m-%d')

        # Query to fetch on-going loan details
        query = """
            SELECT DISTINCT loan_no, cnic, loan_closed_on, mis_date, disbursed_amount, product_code,
            booked_on, markup_outstanding, principal_outstanding, loan_closed_on, overdue_days,
            loan_status, purpose
            FROM tbl_post_disbursement
            WHERE CNIC = %s
            group by mis_date, loan_no, cnic, loan_closed_on, disbursed_amount, product_code,
            booked_on, markup_outstanding, principal_outstanding, loan_closed_on, overdue_days,
            loan_status, purpose
            ORDER BY mis_date
            DESC LIMIT 3;
        """
        result = fetch_records(query, params=(cnic,))
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
        if is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/post_disbursement_report")):
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
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/post_disbursement_report"))):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        filters = request.get_json()
        params = []
        query = """
            SELECT 
                p.id,
                p.mis_date,
                p.area,
                p.sector_code,
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

        # Apply filters: values are passed as parameters (never pasted into the SQL)
        if filters.get('mis_date'):
            query += " AND DATE(p.mis_date) = %s"
            params.append(filters['mis_date'])

        if filters.get('product_code'):
            query += " AND p.product_code = ANY(%s)"
            params.append([str(v) for v in filters['product_code']])

        if filters.get('gender'):
            query += " AND p.gender = %s"
            params.append(filters['gender'])

        if filters.get('disbursed_amount_min'):
            query += f" AND p.disbursed_amount >= {float(filters['disbursed_amount_min'])}"

        if filters.get('disbursed_amount_max'):
            query += f" AND p.disbursed_amount <= {float(filters['disbursed_amount_max'])}"

        if filters.get('principal_outstanding_min'):
            query += f" AND p.principal_outstanding >= {float(filters['principal_outstanding_min'])}"

        if filters.get('principal_outstanding_max'):
            query += f" AND p.principal_outstanding <= {float(filters['principal_outstanding_max'])}"

        # Loans with no overdue_days are treated as 0 days overdue
        if filters.get('overdue_days_min'):
            query += f" AND COALESCE(p.overdue_days, 0) >= {int(float(filters['overdue_days_min']))}"

        if filters.get('overdue_days_max'):
            query += f" AND COALESCE(p.overdue_days, 0) <= {int(float(filters['overdue_days_max']))}"

        for key, column in [('loan_status', 'p.loan_status'), ('branch', 'b.branch'), ('bank_area', 'b.area'),
                            ('bank_distribution', 'CAST(b.bank_distribution AS VARCHAR)'),
                            ('nc_distribution', 'CAST(b.national_council_distribution AS VARCHAR)'),
                            ('kft_distribution', 'CAST(b.kft_distribution AS VARCHAR)')]:
            if filters.get(key):
                query += f" AND {column} = ANY(%s)"
                params.append([str(v) for v in filters[key]])

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

        rows = fetch_records(query, params=tuple(params))
        # Task 004: Sector code and Sector show Education / Enterprise from the product code (same list as the dashboard);
        # an unknown product code keeps the sector code from the MIS file
        for r in rows or []:
            category = get_product_category(r.get('product_code'))
            r['sector_code'] = SECTOR_NAMES.get(category, r.get('sector_code'))
            r['sector'] = SECTOR_NAMES.get(category, r.get('sector'))   # 'Enterprise', not 'Enterprise - Trading' etc.

        return jsonify({'success': True, 'records': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

