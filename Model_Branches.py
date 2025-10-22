from imports import *


def get_all_branches_info():
    # query = """
    #     SELECT b.branch_id, b.branch_code, b.role, b.branch_name, b.area, b.branch, b.area_name, b.branch_manager, b.email,
    #            b.bank_id, b.bank_distribution, b.national_council_distribution, b.kft_distribution,
    #            u.name AS createdBy, b.created_date, bd.bank_code
    #     FROM tbl_branches b
    #     LEFT JOIN tbl_users u ON u.user_id = b.created_by AND u.active = '1'
    #     LEFT JOIN tbl_bank_details bd ON bd.bank_id = b.bank_id
    #     WHERE b.live_branch = '1'
    # """
    query = """
        SELECT b.branch_id, b.branch_code, br.branch_role_name AS role, b.branch_name, b.area, b.branch, b.area_name, 
               b.branch_manager, b.email, b.bank_id, bd.bank_code, 
               bdd.bank_distribution_name AS bank_distribution, 
               ncd.national_council_distribution_name AS national_council_distribution, 
               kd.kft_distribution_name AS kft_distribution, 
               u.name AS createdBy, b.created_date
        FROM tbl_branches b 
        LEFT JOIN tbl_users u ON u.user_id = b.created_by AND u.active = '1'
        LEFT JOIN tbl_bank_details bd ON bd.bank_id = b.bank_id
        LEFT JOIN tbl_bank_distribution bdd ON bdd.bank_distribution_id = b.bank_distribution
        LEFT JOIN tbl_national_council_distribution ncd ON ncd.national_council_distribution_id = b.national_council_distribution
        LEFT JOIN tbl_kft_distribution kd ON kd.kft_distribution_id = b.kft_distribution
        LEFT JOIN tbl_branch_role br ON br.branch_role_id = b.role
        WHERE b.live_branch = '1'
    """
    result = fetch_records(query)
    print(result)
    return result


def get_distinct_branches_roles():
    query = """
        select  DISTINCT(b.role)
        from tbl_branches b 
    """
    result = fetch_records(query)
    print(result)
    return result


def get_all_branches_records():
    query = """
        select b.branch_id, b.branch_code, br.branch_role_name AS role, b.branch_name, b.area, b.email, b.created_date 
        from tbl_branches b 
        LEFT JOIN tbl_branch_role br ON br.branch_role_id = b.role
    """
    result = fetch_records(query)
    print(result)
    return result
