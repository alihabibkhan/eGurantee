from imports import *
from application import application

@application.route('/manage-announcements')
def manage_announcements():
    try:
        if is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/manage-announcements")):
            # Fetch only non-deleted records (add status if you add it later)
            query = """
                SELECT 
                    id, title, message, start_date, end_date, is_active, priority,
                    background_color, text_color, link_url, link_text,
                    created_at, created_by
                FROM announcements
                WHERE
                    status = 1
                ORDER BY priority DESC, created_at DESC
            """
            announcements = fetch_records(query)
            content = {'announcements': announcements}
            return render_template('manage_announcements.html', result=content)
    except Exception as e:
        print('manage announcements exception:- ', str(e))
    return redirect(url_for('login'))


@application.route('/add-announcement', methods=['GET', 'POST'])
@application.route('/edit-announcement/<int:ann_id>', methods=['GET', 'POST'])
def add_edit_announcement(ann_id=None):
    try:
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/add-announcement"))):
            return redirect(url_for('login'))

        announcement = None
        if ann_id:
            # Fetch existing record for editing (status != 3 if you add soft delete later)
            query = f"""
                SELECT 
                    id, title, message, start_date, end_date, is_active, priority,
                    background_color, text_color, link_url, link_text,
                    created_at, created_by
                FROM announcements 
                WHERE id = {ann_id}
            """
            result = fetch_records(query)
            announcement = result[0] if result else None
            if not announcement:
                return redirect(url_for('manage_announcements'))

        if request.method == 'POST':
            # Get form data - exactly matching your PG table
            title               = request.form.get('title', '').strip()
            message             = request.form.get('message', '').strip()
            start_date          = request.form.get('start_date') or None
            end_date            = request.form.get('end_date') or None
            is_active           = True if request.form.get('is_active') == 'on' else False
            priority            = int(request.form.get('priority', '0'))
            background_color    = request.form.get('background_color', '').strip()
            text_color          = request.form.get('text_color', '').strip()
            link_url            = request.form.get('link_url', '').strip()
            link_text           = request.form.get('link_text', '').strip()

            current_user_id = get_current_user_id()
            current_time    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Values are passed as parameters (never pasted into the SQL) to prevent SQL injection
            values = (title, message, start_date, end_date, is_active, priority,
                      background_color, text_color, link_url, link_text)
            if ann_id:
                query = """
                    UPDATE announcements
                    SET title = %s, message = %s, start_date = %s, end_date = %s, is_active = %s, priority = %s,
                        background_color = %s, text_color = %s, link_url = %s, link_text = %s
                    WHERE id = %s
                """
                execute_command(query, params=values + (ann_id,))
            else:
                query = """
                    INSERT INTO announcements
                    (title, message, start_date, end_date, is_active, priority,
                     background_color, text_color, link_url, link_text, created_by, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                    RETURNING id
                """
                execute_command(query, params=values + (current_user_id,))

            return redirect(url_for('manage_announcements'))

        # GET → show form
        return render_template('add_edit_announcement.html', result={'announcement': announcement})

    except Exception as e:
        print('add/edit announcement exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-announcement/<int:ann_id>', methods=['POST'])
def delete_announcement(ann_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver() or PermissionHelper.has_permission(get_current_user_id(), "/delete-announcement"))):
            return redirect(url_for('login'))

        # Soft delete: set is_active = false (matches your schema philosophy)
        query = f"""
            UPDATE announcements 
            SET status = 2
            WHERE id = {ann_id}
        """
        print(f'DELETE announcement query: {query}')  # Debug print
        execute_command(query)
        return redirect(url_for('manage_announcements'))

    except Exception as e:
        print('delete announcement exception:- ', str(e))
        return redirect(url_for('login'))



def get_active_marquee_content(limit=1):
    """
    Returns list of active marquee messages ready for display.
    Ordered by priority DESC.
    """
    try:
        query = f"""
            SELECT 
                title,
                message,
                link_url,
                link_text,
                background_color,
                text_color,
                priority
            FROM announcements
            WHERE is_active = TRUE
              AND (start_date IS NULL OR start_date <= NOW())
              AND (end_date   IS NULL OR end_date   >= NOW())
            ORDER BY priority DESC, created_at DESC
            LIMIT {str(limit)}
        """
        records = fetch_records(query)  # assuming fetch_records supports params now

        marquee_items = []
        for row in records:
            # Build rich content (with optional link)
            content = row['message'].strip()

            if row['link_url'] and row['link_text']:
                content = f'{content} <a href="{row["link_url"]}" target="_blank" style="color: inherit; text-decoration: underline;">{row["link_text"]}</a>'

            style = ""
            if row['background_color']:
                style += f"background: {row['background_color']}; "
            if row['text_color']:
                style += f"color: {row['text_color']}; "

            marquee_items.append({
                'content': content,
                'style': style.strip(),
                'priority': row['priority']
            })

        return marquee_items

    except Exception as e:
        current_app.logger.error(f"Error fetching marquee: {str(e)}")
        return []