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