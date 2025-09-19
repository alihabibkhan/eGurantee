from imports import *
from application import application


@application.route('/manage_loan_products')
def manage_loan_products():
    try:
        if is_login() and is_admin():
            content = {
                'get_all_loan_products': get_all_loan_products()
            }
            return render_template('manage_loan_products.html', result=content)
    except Exception as e:
        print('manage_loan_products exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/add-edit-loan-product', methods=['GET', 'POST'])
@application.route('/add-edit-loan-product/<int:product_id>', methods=['GET', 'POST'])
def add_edit_loan_product(product_id=None):
    try:
        if not is_login() or not is_admin():
            return redirect(url_for('login'))

        loan_product = None

        if product_id:
            query = f"""
                SELECT product_id, product_code, name, gender, description, status, created_by, created_date, modified_by, modified_date
                FROM tbl_loan_products 
                WHERE product_id = '{product_id}' AND status = '1'
            """
            print(query)
            loan_product = fetch_records(query)
            loan_product = loan_product[0] if loan_product else None

            print('loan_product record')
            print(loan_product)

        if request.method == 'POST':
            name = request.form.get('name')
            product_code = request.form.get('product_code')
            gender = request.form.get('gender', 'Male')
            description = request.form.get('description')

            current_user_id = str(get_current_user_id())
            current_timestamp = str(datetime.now())

            if product_id:
                update_query = f"""
                    UPDATE tbl_loan_products 
                    SET name = '{name}', product_code = '{product_code}', gender = '{gender}', description = '{description}', 
                        status = '{str(1)}', modified_by = '{current_user_id}', modified_date = '{current_timestamp}'
                    WHERE product_id = '{product_id}'
                """
                execute_command(update_query)
                flash('Loan product updated successfully.', 'success')
            else:
                insert_query = f"""
                    INSERT INTO tbl_loan_products (
                        name, product_code, gender, description, status, created_by, created_date, modified_by, modified_date
                    ) VALUES (
                        '{name}', '{product_code}', '{gender}', '{description}', '{str(1)}', '{current_user_id}', '{current_timestamp}', 
                        '{current_user_id}', '{current_timestamp}'
                    )
                """
                execute_command(insert_query)
                flash('Loan product added successfully.', 'success')

            return redirect(url_for('manage_loan_metrics') + '#loan-products')

        content = {
            'loan_product': loan_product,
            'product_id': product_id
        }
        return render_template('add_edit_loan_product.html', result=content)

    except Exception as e:
        print('add_edit_loan_product exception:- ', str(e))
        flash('An error occurred while processing the loan product.', 'danger')
        return redirect(url_for('manage_loan_metrics'))


@application.route('/delete-loan-product', methods=['GET'])
def delete_loan_product():
    try:
        if not is_login() or not is_admin():
            return redirect(url_for('login'))

        product_id = request.args.get('product_id')
        if product_id:
            delete_query = f"""
                UPDATE tbl_loan_products 
                SET status = '0'
                WHERE product_id = '{product_id}'
            """
            execute_command(delete_query)
            flash('Loan product deleted successfully.', 'success')
        else:
            flash('Invalid product ID.', 'danger')

        return redirect(url_for('manage_loan_metrics') + '#loan-products')

    except Exception as e:
        print('delete_loan_product exception:- ', str(e))
        flash('An error occurred while deleting the loan product.', 'danger')
        return redirect(url_for('manage_loan_products'))