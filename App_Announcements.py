from imports import *
from application import application

@application.route('/manage-announcements')
def manage_announcements():
    try:
        if is_login() and (is_admin() or is_executive_approver()):
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
        if not (is_login() and (is_admin() or is_executive_approver())):
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

            # Escape strings to prevent SQL injection (your existing method)
            title_esc            = escape_sql_string(title)
            message_esc          = escape_sql_string(message)
            bg_color_esc         = escape_sql_string(background_color)
            text_color_esc       = escape_sql_string(text_color)
            link_url_esc         = escape_sql_string(link_url)
            link_text_esc        = escape_sql_string(link_text)
            start_date_esc       = f"'{start_date}'" if start_date else 'NULL'
            end_date_esc         = f"'{end_date}'" if end_date else 'NULL'

            if ann_id:
                # Update existing (no modified_by/date in your schema, but adding for audit)
                query = f"""
                    UPDATE announcements 
                    SET 
                        title = {title_esc},
                        message = {message_esc},
                        start_date = {start_date_esc},
                        end_date = {end_date_esc},
                        is_active = {is_active},
                        priority = {priority},
                        background_color = {bg_color_esc},
                        text_color = {text_color_esc},
                        link_url = {link_url_esc},
                        link_text = {link_text_esc}
                    WHERE id = {ann_id}
                """
                print(f'UPDATE announcement query: {query}')  # Debug print
                execute_command(query)
            else:
                # Insert new - exactly matching your PG schema
                query = f"""
                    INSERT INTO announcements 
                    (title, message, start_date, end_date, is_active, priority,
                     background_color, text_color, link_url, link_text, created_by, status)
                    VALUES (
                        {title_esc}, {message_esc}, {start_date_esc}, {end_date_esc},
                        {is_active}, {priority},
                        {bg_color_esc}, {text_color_esc}, {link_url_esc}, {link_text_esc},
                        {current_user_id}, 1
                    )
                    RETURNING id
                """
                print(f'INSERT announcement query: {query}')  # Debug print
                execute_command(query)

            return redirect(url_for('manage_announcements'))

        # GET → show form
        return render_template('add_edit_announcement.html', result={'announcement': announcement})

    except Exception as e:
        print('add/edit announcement exception:- ', str(e))
        return redirect(url_for('login'))


@application.route('/delete-announcement/<int:ann_id>', methods=['POST'])
def delete_announcement(ann_id):
    try:
        if not (is_login() and (is_admin() or is_executive_approver())):
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