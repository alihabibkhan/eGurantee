import pandas as pd
from datetime import datetime
import os
from werkzeug.security import generate_password_hash

def generate_branch_inserts():
    # Column mapping from Excel to Database
    COLUMN_MAPPING = {
        'Branch Code': 'branch_code',
        'ROLE': 'role',
        'Branch Name': 'branch_name',
        'Branch': 'branch',
        'Area': 'area',
        'Area_Name': 'area_name',
        'Email': 'email',
        'Live_Branch': 'live_branch'
    }

    # File paths
    excel_file = 'eGuarantee_Setup_Files.xlsx'
    output_file = 'branch_inserts.sql'

    try:
        # Check if Excel file exists
        if not os.path.exists(excel_file):
            raise FileNotFoundError(f"Excel file '{excel_file}' not found in current directory")

        # Read the Excel file, specifying branch_code should be read as string
        df = pd.read_excel(
            excel_file,
            sheet_name='Branch',
            dtype={'Branch Code': str}  # Force branch_code to be read as string
        )

        # Rename columns to match database names
        df.rename(columns=COLUMN_MAPPING, inplace=True)

        # Prepare the output file
        with open(output_file, 'w', encoding='utf-8') as f:
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for _, row in df.iterrows():
                # Convert Live_Branch 'Y'/'N' to 1/0
                live_branch = 1 if str(row.get('live_branch', 'N')).strip().upper() == 'Y' else 0

                # Ensure branch_code maintains leading zeros
                branch_code = str(row.get('branch_code', '')).strip().zfill(
                    3)  # Pad with leading zeros to make 3 digits

                # Create the INSERT query
                insert_query = f"""INSERT INTO tbl_branches (
    branch_code, role, branch_name, branch, 
    area, area_name, email, live_branch, created_by, created_date
) VALUES (
    '{branch_code.replace("'", "''")}', 
    '{str(row.get('role', '')).replace("'", "''")}', 
    '{str(row.get('branch_name', '')).replace("'", "''")}', 
    '{str(row.get('branch', '')).replace("'", "''")}', 
    '{str(row.get('area', '')).replace("'", "''")}', 
    '{str(row.get('area_name', '')).replace("'", "''")}', 
    '{str(row.get('email', '')).replace("'", "''")}', 
    {live_branch}, 
    1, 
    '{current_date}'
);\n"""
                f.write(insert_query)

        print(f"Successfully generated INSERT queries in {output_file}")
        print(f"Total rows processed: {len(df)}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


def generate_budget_inserts():
    # Column mapping from Excel to Database
    COLUMN_MAPPING = {
        'MIS_DATE': 'mis_date',
        'Branch Code': 'branch_code',
        'Amount': 'amount'
    }

    # File paths
    excel_file = 'eGuarantee_Setup_Files.xlsx'
    output_file = 'budget_inserts.sql'

    try:
        # Check if Excel file exists
        if not os.path.exists(excel_file):
            raise FileNotFoundError(f"Excel file '{excel_file}' not found in current directory")

        # Read the Excel file
        df = pd.read_excel(
            excel_file,
            sheet_name='Budget',
            dtype={'Branch Code': str}  # Force branch_code to be read as string
        )

        # Rename columns to match database names
        df.rename(columns=COLUMN_MAPPING, inplace=True)

        # Prepare the output file
        with open(output_file, 'w', encoding='utf-8') as f:
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for _, row in df.iterrows():
                # Ensure branch_code maintains leading zeros
                branch_code = str(row.get('branch_code', '')).strip().zfill(3)

                # Format date properly (assuming Excel date format)
                mis_date = pd.to_datetime(row['mis_date']).strftime('%Y-%m-%d')

                # Create the INSERT query with additional fields
                insert_query = f"""INSERT INTO tbl_budget (
    mis_date, branch_code, amount, created_by, created_date
) VALUES (
    '{mis_date}', 
    '{branch_code.replace("'", "''")}', 
    {row.get('amount', 0)},
    1, 
    '{current_date}'
);\n"""
                f.write(insert_query)

        print(f"Successfully generated INSERT queries in {output_file}")
        print(f"Total rows processed: {len(df)}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except KeyError as e:
        print(f"Error: Column {e} not found in Budget sheet - please check your Excel column names")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


def generate_user_inserts():
    # Column mapping from Excel to Database
    COLUMN_MAPPING = {
        'UserID': 'email',
        'Name': 'name',
        'Role': 'role',
        'Active': 'active',
        'Signature': 'signature'
    }

    # File paths
    excel_file = 'eGuarantee_Setup_Files.xlsx'
    output_file = 'user_inserts.sql'

    # Default password configuration
    DEFAULT_PASSWORD = "@Test123"

    try:
        # Check if Excel file exists
        if not os.path.exists(excel_file):
            raise FileNotFoundError(f"Excel file '{excel_file}' not found in current directory")

        # Read the Excel file
        df = pd.read_excel(
            excel_file,
            sheet_name='Users',
            dtype={'UserID': str}  # Force email to be read as string
        )

        # Rename columns to match database names
        df.rename(columns=COLUMN_MAPPING, inplace=True)

        # Generate password hash
        password_hash = generate_password_hash(DEFAULT_PASSWORD, method='pbkdf2:sha256')

        # Prepare the output file
        with open(output_file, 'w', encoding='utf-8') as f:
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for _, row in df.iterrows():
                # Convert Active (Y/N) to 1/0
                active = 1 if str(row.get('active', 'N')).strip().upper() == 'Y' else 0

                # Convert Signature (Yes/No) to 1/0
                signature = 1 if str(row.get('signature', 'No')).strip().lower() == 'yes' else 0

                # Create the INSERT query with hashed password
                insert_query = f"""INSERT INTO tbl_users (
    name, email, role, password, signature, scan_sign, active, created_by, created_date
) VALUES (
    '{str(row.get('name', '')).replace("'", "''")}', 
    '{str(row.get('email', '')).replace("'", "''")}', 
    '{str(row.get('role', '')).replace("'", "''")}', 
    '{password_hash}',  -- Hashed default password: {DEFAULT_PASSWORD}
    {signature},
    '',  -- Empty scan_sign (LONGBLOB)
    {active},
    1,  -- Default created_by
    '{current_date}'
);\n"""
                f.write(insert_query)

        print(f"Successfully generated INSERT queries in {output_file}")
        print(f"Total users processed: {len(df)}")
        print(f"Default password for all users: {DEFAULT_PASSWORD}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except KeyError as e:
        print(f"Error: Column {e} not found in Users sheet - please check your Excel column names")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    # generate_branch_inserts()
    # generate_budget_inserts()
    generate_user_inserts()