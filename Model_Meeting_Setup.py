from imports import *

def get_all_meeting_categories():
    query = """
        SELECT mc.meeting_category_id, mc.meeting_category_code, mc.meeting_category_name, mc.status, 
               u.name AS created_by, mc.created_date
        FROM tbl_meeting_categories mc
        LEFT JOIN tbl_users u ON u.user_id = mc.created_by AND u.active = '1'
        WHERE mc.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result

def get_all_meeting_frequencies():
    query = """
        SELECT mf.meeting_freq_id, mf.meeting_freq_title, mf.min_freq, mf.max_freq, mf.status, 
               u.name AS created_by, mf.created_date
        FROM tbl_meeting_frequencies mf
        LEFT JOIN tbl_users u ON u.user_id = mf.created_by AND u.active = '1'
        WHERE mf.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result

def get_all_meeting_priorities():
    query = """
        SELECT mp.meeting_priority_id, mp.meeting_priority_name, mp.status, 
               u.name AS created_by, mp.created_date
        FROM tbl_meeting_priorities mp
        LEFT JOIN tbl_users u ON u.user_id = mp.created_by AND u.active = '1'
        WHERE mp.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result

def get_all_pre_meeting_status():
    query = """
        SELECT pms.pre_ms_id, pms.pre_ms_name, pms.status, 
               u.name AS created_by, pms.created_date
        FROM tbl_pre_meeting_status pms
        LEFT JOIN tbl_users u ON u.user_id = pms.created_by AND u.active = '1'
        WHERE pms.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result

def get_all_post_meeting_status():
    query = """
        SELECT pms.post_ms_id, pms.post_ms_name, pms.status, 
               u.name AS created_by, pms.created_date
        FROM tbl_post_meeting_status pms
        LEFT JOIN tbl_users u ON u.user_id = pms.created_by AND u.active = '1'
        WHERE pms.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result

def get_all_meeting_action_items():
    query = """
        SELECT mai.mai_id, mai.mai_name, mai.status, 
               u.name AS created_by, mai.created_date
        FROM tbl_meeting_action_items mai
        LEFT JOIN tbl_users u ON u.user_id = mai.created_by AND u.active = '1'
        WHERE mai.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result

def get_all_meeting_action_items_priorities():
    query = """
        SELECT maip.maip_id, maip.maip_name, maip.status, 
               u.name AS created_by, maip.created_date
        FROM tbl_meeting_action_items_priorities maip
        LEFT JOIN tbl_users u ON u.user_id = maip.created_by AND u.active = '1'
        WHERE maip.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result

def get_all_meeting_action_items_status():
    query = """
        SELECT mais.mais_id, mais.mais_name, mais.status, 
               u.name AS created_by, mais.created_date
        FROM tbl_meeting_action_items_status mais
        LEFT JOIN tbl_users u ON u.user_id = mais.created_by AND u.active = '1'
        WHERE mais.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result

def get_all_mandatory_meetings():
    query = """
        SELECT mm.mand_meet_id, mm.meeting_category_id, mc.meeting_category_name, mc.meeting_category_code,
               mm.meeting_freq_id, mf.meeting_freq_title, mm.proposed_month, ncd.national_council_distribution_name as nc_disb_id, 
               mm.resp_committ, mm.meeting_priority_id, mp.meeting_priority_name, mm.status, 
               u.name AS created_by, mm.created_date
        FROM tbl_mandatory_meetings mm
        LEFT JOIN tbl_meeting_categories mc ON mc.meeting_category_id = mm.meeting_category_id
        LEFT JOIN tbl_meeting_frequencies mf ON mf.meeting_freq_id = mm.meeting_freq_id
        LEFT JOIN tbl_national_council_distribution ncd ON ncd.national_council_distribution_id = mm.nc_disb_id
        LEFT JOIN tbl_meeting_priorities mp ON mp.meeting_priority_id = mm.meeting_priority_id
        LEFT JOIN tbl_users u ON u.user_id = mm.created_by AND u.active = '1'
        WHERE mm.status = 1
    """
    result = fetch_records(query)
    print(result)
    return result



def get_user_committee_meetings_current_month():
    try:
        current_user_id = get_current_user_id()
        query = f"""
            SELECT mm.mand_meet_id, mc.meeting_category_name, mf.meeting_freq_title, 
                   mm.proposed_month, mm.nc_disb_id, ncd.national_council_distribution_name,
                   mm.resp_committ, mp.meeting_priority_name, mm.status, 
                   mm.created_by, mm.created_date
            FROM tbl_mandatory_meetings mm
            LEFT JOIN tbl_user_privileges up ON up.committee = mm.resp_committ
            LEFT JOIN tbl_meeting_categories mc ON mm.meeting_category_id = mc.meeting_category_id
            LEFT JOIN tbl_meeting_frequencies mf ON mm.meeting_freq_id = mf.meeting_freq_id
            LEFT JOIN tbl_meeting_priorities mp ON mm.meeting_priority_id = mp.meeting_priority_id
            LEFT JOIN tbl_national_council_distribution ncd ON mm.nc_disb_id = ncd.national_council_distribution_id
            LEFT JOIN tbl_schedule_meetings sm ON mm.mand_meet_id = sm.mand_meet_id AND sm.status != 3
            WHERE up.user_id = {current_user_id}
            AND mm.status != 3
            AND DATE_TRUNC('month', mm.proposed_month) = DATE_TRUNC('month', CURRENT_DATE)
            AND sm.mand_meet_id IS NULL
            ORDER BY mm.proposed_month
        """
        result = fetch_records(query)
        for record in result:
            if record['proposed_month']:
                if isinstance(record['proposed_month'], str):
                    if not re.match(r'^\d{4}-\d{2}-\d{2}$', record['proposed_month']):
                        print(f"Warning: Invalid date format for proposed_month: {record['proposed_month']}")
                    record['proposed_month'] = record['proposed_month']
                else:
                    record['proposed_month'] = record['proposed_month'].strftime('%Y-%m-%d')
        return result
    except Exception as e:
        print('get_user_committee_meetings_current_month exception:- ', str(e))
        return []

def get_mandatory_meeting_details_by_id(mand_meet_id):
    try:
        query = f"""
            SELECT mm.mand_meet_id, mc.meeting_category_name, mf.meeting_freq_title, 
                   mm.proposed_month, mm.resp_committ, mp.meeting_priority_name, 
                   ncd.national_council_distribution_name
            FROM tbl_mandatory_meetings mm
            LEFT JOIN tbl_meeting_categories mc ON mm.meeting_category_id = mc.meeting_category_id
            LEFT JOIN tbl_meeting_frequencies mf ON mm.meeting_freq_id = mf.meeting_freq_id
            LEFT JOIN tbl_meeting_priorities mp ON mm.meeting_priority_id = mp.meeting_priority_id
            LEFT JOIN tbl_national_council_distribution ncd ON mm.nc_disb_id = ncd.national_council_distribution_id
            WHERE mm.mand_meet_id = {mand_meet_id} AND mm.status != 3
        """
        result = fetch_records(query)
        if result:
            if result[0]['proposed_month']:
                if isinstance(result[0]['proposed_month'], str):
                    if not re.match(r'^\d{4}-\d{2}-\d{2}$', result[0]['proposed_month']):
                        print(f"Warning: Invalid date format for proposed_month: {result[0]['proposed_month']}")
                    result[0]['proposed_month'] = result[0]['proposed_month']
                else:
                    result[0]['proposed_month'] = result[0]['proposed_month'].strftime('%Y-%m-%d')
            return result[0]
        return None
    except Exception as e:
        print('get_mandatory_meeting_details_by_id exception:- ', str(e))
        return None

def get_schedule_meeting(mand_meet_id):
    try:
        query = f"""
            SELECT schedule_meeting_id, mand_meet_id, meeting_title, meeting_aganda, 
                   schedule_date, pre_ms_id, status
            FROM tbl_schedule_meetings
            WHERE mand_meet_id = {mand_meet_id} AND status != 3
        """
        result = fetch_records(query)
        if result:
            if result[0]['schedule_date']:
                if isinstance(result[0]['schedule_date'], str):
                    if not re.match(r'^\d{4}-\d{2}-\d{2}$', result[0]['schedule_date']):
                        print(f"Warning: Invalid date format for schedule_date: {result[0]['schedule_date']}")
                    result[0]['schedule_date'] = result[0]['schedule_date']
                else:
                    result[0]['schedule_date'] = result[0]['schedule_date'].strftime('%Y-%m-%d')
            return result[0]
        return None
    except Exception as e:
        print('get_schedule_meeting exception:- ', str(e))
        return None


def get_all_schedule_meetings():
    try:
        current_user_id = get_current_user_id()
        today = datetime.now().date()  # Get current date (e.g., 2025-11-06)

        # Fetch pre_ms_name mappings upfront to avoid multiple queries
        pre_ms_query = """
            SELECT pre_ms_id, pre_ms_name
            FROM tbl_pre_meeting_status
            WHERE pre_ms_id IN (1, 2)
        """
        pre_ms_results = fetch_records(pre_ms_query)
        pre_ms_map = {row['pre_ms_id']: row['pre_ms_name'] for row in pre_ms_results} if pre_ms_results else {}

        # Fetch all scheduled meetings
        query = f"""
            SELECT sm.schedule_meeting_id, sm.mand_meet_id, sm.meeting_title, sm.meeting_aganda,
                   sm.schedule_date, sm.pre_ms_id, sm.status,
                   mc.meeting_category_code, pms.pre_ms_name
            FROM tbl_schedule_meetings sm
            LEFT JOIN tbl_mandatory_meetings mm ON mm.mand_meet_id = sm.mand_meet_id
            LEFT JOIN tbl_meeting_categories mc ON mm.meeting_category_id = mc.meeting_category_id
            LEFT JOIN tbl_meeting_frequencies mf ON mm.meeting_freq_id = mf.meeting_freq_id
            LEFT JOIN tbl_meeting_priorities mp ON mm.meeting_priority_id = mp.meeting_priority_id
            LEFT JOIN tbl_national_council_distribution ncd ON mm.nc_disb_id = ncd.national_council_distribution_id
            LEFT JOIN tbl_pre_meeting_status pms ON sm.pre_ms_id = pms.pre_ms_id
            LEFT JOIN tbl_user_privileges up ON up.committee = mm.resp_committ
            WHERE up.user_id = {current_user_id}
            AND sm.status != 3
            AND mm.status != 3
        """
        result = fetch_records(query)

        # Process each record
        for record in result:
            # Format and validate schedule_date
            if record['schedule_date']:
                if isinstance(record['schedule_date'], str):
                    if not re.match(r'^\d{4}-\d{2}-\d{2}$', record['schedule_date']):
                        print(f"Warning: Invalid date format for schedule_date: {record['schedule_date']}")
                        continue  # Skip invalid dates
                    record['schedule_date'] = record['schedule_date']
                else:
                    record['schedule_date'] = record['schedule_date'].strftime('%Y-%m-%d')

                # Check if schedule_date is in the past
                try:
                    schedule_date = datetime.strptime(record['schedule_date'], '%Y-%m-%d').date()
                    if schedule_date < today and record['pre_ms_id'] != 1:
                        # Update pre_ms_id to 1
                        update_query = f"""
                            UPDATE tbl_schedule_meetings
                            SET pre_ms_id = 1,
                                modified_by = {current_user_id},
                                modified_date = '{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}'
                            WHERE schedule_meeting_id = {record['schedule_meeting_id']}
                        """
                        execute_command(update_query)
                        # Update the record to reflect the new pre_ms_id
                        record['pre_ms_id'] = 1
                        # Set pre_ms_name from pre_ms_map
                        record['pre_ms_name'] = pre_ms_map.get(1, 'N/A')
                except ValueError as e:
                    print(f"Error parsing schedule_date for meeting {record['schedule_meeting_id']}: {str(e)}")
                    continue

        return result
    except Exception as e:
        print('get_all_schedule_meetings exception:- ', str(e))
        return []