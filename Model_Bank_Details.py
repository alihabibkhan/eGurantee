from imports import *


def escape_sql_string(value):
    """Basic escaping for SQL string values to prevent injection."""
    if value is None:
        return 'NULL'

    # Escape single quotes by doubling them
    value = re.sub(r"'", "''", value)

    return f"'{value}'"


def get_all_bank_details():
    query = """
        SELECT 
            b.bank_id, 
            b.bank_code,
            b.bank_name, 
            b.branch_of_account, 
            b.currency, 
            b.IBAN, 
            b.account_title, 
            b.date_account_opened, 
            b.date_account_closed,
            b.status, 
            u1.name AS created_by_name, 
            b.created_date, 
            u2.name AS modified_by_name, 
            b.modified_date
        FROM tbl_bank_details b 
        LEFT JOIN tbl_users u1 ON u1.user_id = b.created_by
        LEFT JOIN tbl_users u2 ON u2.user_id = b.modifed_by
        WHERE 
            b.status != '3' 
    """
    result = fetch_records(query)
    return result


def get_all_banks_last_entry_records():
    query = """
        SELECT *
        FROM (
            SELECT bem.bank_entry_id, bem.bank_id, bem.date_posted, bem.mode, bem.general_ledger,
                   bem.nature_of_transaction, bem.withdrawal, bem.deposit, bem.balance,
                   bem.date_reconciled, bem.status, bd.bank_code, bem.inst_no, bem.narration,
                   ROW_NUMBER() OVER (PARTITION BY bem.bank_id ORDER BY bem.date_posted DESC) AS rn
            FROM tbl_bank_entry_management bem
            INNER JOIN tbl_bank_details bd ON bd.bank_id = bem.bank_id AND bd.status = '1'
            WHERE bem.status = '1'
        ) AS sub
        WHERE sub.rn = 1
        ORDER BY sub.bank_id DESC
        LIMIT 1;
    """
    result = fetch_records(query)
    return result

