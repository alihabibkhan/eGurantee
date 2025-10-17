from imports import *


def get_all_post_disbursement_info_by_id(id):
    sql_part = """"""

    if get_current_user_role() != '4':
        sql_part = f"""
                INNER JOIN tbl_branches b ON b.branch_code = p.branch_code AND b.live_branch = '1'
                INNER JOIN tbl_users u ON u.assigned_branch = b.role
                WHERE u.role = '{str(get_current_user_role())}' AND p.id = '{str(id)}'
            """

    query = f"""
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
            p.collateral_title
        FROM tbl_post_disbursement p
        WHERE
        p.id = '{str(id)}'
    """

    result = fetch_records(query)
    # print(result)
    return result


def get_all_post_disbursement_info():

    sql_part = """"""

    if get_current_user_role() != '4':
        sql_part = f"""
            INNER JOIN tbl_branches b ON b.branch_code = p.branch_code AND b.live_branch = '1'
            INNER JOIN tbl_users u ON u.assigned_branch = b.role
            WHERE u.role = '{str(get_current_user_role())}'
        """

    query = f"""
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
            p.collateral_title
        FROM tbl_post_disbursement p
        {sql_part if get_current_user_id() != 'ADMIN' else f'WHERE p.id = "{str(id)}" '}
    """
    print(query)

    result = fetch_records(query)
    # print(result)
    return result


# def post_disbursement_by_booked_on():
#     query = """
#         SELECT
#             TO_CHAR(booked_on, 'FMMonth') AS month,
#             EXTRACT(YEAR FROM booked_on) AS year,
#             SUM(disbursed_amount) AS count
#         FROM
#             tbl_post_disbursement
#         WHERE
#           DATE_TRUNC('month', mis_date) = (
#                   SELECT DATE_TRUNC('month', MAX(mis_date)) FROM tbl_post_disbursement
#                )
#         GROUP BY
#             TO_CHAR(booked_on, 'FMMonth'),
#             EXTRACT(YEAR FROM booked_on)
#         ORDER BY
#             EXTRACT(YEAR FROM booked_on),
#             TO_DATE(TO_CHAR(booked_on, 'FMMonth'), 'Month');
#     """
#     result = fetch_records(query)
#     return result


def post_disbursement_by_booked_on():
    # query = """
    #     SELECT
    #     TO_CHAR(booked_on, 'FMMonth') AS month,
    #     EXTRACT(YEAR FROM booked_on) AS year,
    #     SUM(disbursed_amount) AS monthly_disbursement,
    #     SUM(SUM(disbursed_amount)) OVER (PARTITION BY EXTRACT(YEAR FROM booked_on)) AS yearly_disbursement,
    #     SUM(SUM(disbursed_amount)) OVER (PARTITION BY EXTRACT(YEAR FROM booked_on)) /
    #     COUNT(TO_CHAR(booked_on, 'FMMonth')) OVER (PARTITION BY EXTRACT(YEAR FROM booked_on)) AS monthly_average
    # FROM
    #     tbl_post_disbursement
    # WHERE
    #     DATE_TRUNC('month', mis_date) = (
    #         SELECT DATE_TRUNC('month', MAX(mis_date)) FROM tbl_post_disbursement
    #     )
    # GROUP BY
    #     TO_CHAR(booked_on, 'FMMonth'),
    #     EXTRACT(YEAR FROM booked_on)
    # ORDER BY
    #     EXTRACT(YEAR FROM booked_on),
    #     TO_DATE(TO_CHAR(booked_on, 'FMMonth'), 'Month');
    # """
    query = """
        WITH base_data AS (
            SELECT 
                TO_CHAR(booked_on, 'FMMonth') AS month,
                EXTRACT(YEAR FROM booked_on) AS year,
                disbursed_amount,
                cnic
            FROM 
                tbl_post_disbursement
            WHERE
                DATE_TRUNC('month', mis_date) = (
                    SELECT DATE_TRUNC('month', MAX(mis_date)) FROM tbl_post_disbursement
                )
        ),
        monthly_agg AS (
            SELECT
                month,
                year,
                SUM(disbursed_amount) AS monthly_disbursement
            FROM 
                base_data
            GROUP BY 
                month, year
        ),
        yearly_agg AS (
            SELECT
                year,
                SUM(disbursed_amount) AS yearly_disbursement,
                COUNT(DISTINCT cnic) AS yearly_beneficiaries_count
            FROM 
                base_data
            GROUP BY 
                year
        ),
        month_count AS (
            SELECT 
                year,
                COUNT(DISTINCT month) AS months_in_year
            FROM 
                base_data
            GROUP BY 
                year
        )
        
        SELECT 
            m.month,
            m.year,
            m.monthly_disbursement,
            y.yearly_disbursement,
            ROUND(y.yearly_disbursement::numeric / mc.months_in_year, 2) AS monthly_average,
            y.yearly_beneficiaries_count
        FROM 
            monthly_agg m
        JOIN 
            yearly_agg y ON m.year = y.year
        JOIN
            month_count mc ON m.year = mc.year
        ORDER BY 
            m.year,
            TO_DATE(m.month, 'Month');
    """
    result = fetch_records(query)
    print(result)
    return result

