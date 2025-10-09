from imports import *


def get_all_bank_entries_info():
    query = """
        SELECT bem.bank_entry_id, bem.bank_id, bem.date_posted, bem.mode, bem.general_ledger, bem.nature_of_transaction,
               bem.withdrawal, bem.deposit, bem.balance, bem.date_reconciled, bem.status, 
               u.name AS created_by, bem.created_date, 
               u2.name AS modified_by, bem.modified_date, 
               bd.bank_code, bem.inst_no, bem.narration
        FROM tbl_bank_entry_management bem
        LEFT JOIN tbl_users u ON u.user_id = bem.created_by AND u.active = '1'
        LEFT JOIN tbl_users u2 ON u2.user_id = bem.modified_by AND u2.active = '1'
        INNER JOIN tbl_bank_details bd ON bd.bank_id = bem.bank_id AND bd.status = '1'
        WHERE bem.status = '1' ORDER BY bem.bank_entry_id DESC
    """
    print(query)
    result = fetch_records(query)
    return result


