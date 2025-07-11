import psycopg2
from psycopg2 import Error
import time
from typing import List, Dict, Optional
import traceback
import os

POSTGRES_CONNECTION = os.getenv('POSTGRES_CONNECTION')


def db_connection():
    connection = None
    max_attempts = 3
    attempt = 1

    while attempt <= max_attempts:
        try:
            if attempt == 1:
                print(f"Connection attempt {attempt} started at {time.strftime('%Y-%m-%d %H:%M:%S')}")

            # connection = psycopg2.connect(
            #     user="your_username",
            #     password="your_password",
            #     host="127.0.0.1",
            #     port="5432",
            #     database="your_database"
            # )

            connection = psycopg2.connect(
                dsn=str(POSTGRES_CONNECTION)
            )

            if attempt == 1:
                print(f"Connection successful at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            return connection

        except (Exception, Error) as error:
            print(f"Error while connecting to PostgreSQL (Attempt {attempt}/{max_attempts}): {error}")
            attempt += 1
            if attempt <= max_attempts:
                time.sleep(2)  # Wait 2 seconds before retrying
            if attempt > max_attempts:
                print(f"Failed to connect after {max_attempts} attempts")
                raise Exception("Database connection failed")
        finally:
            if attempt == max_attempts and connection is not None:
                connection.close()

    return None


def fetch_records(query: str, is_print: bool = False) -> List[Dict]:
    connection = None
    cursor = None
    results = []

    try:
        if is_print:
            print(f"Connection start at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(query)

        connection = db_connection()
        cursor = connection.cursor()

        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        records = cursor.fetchall()

        for record in records:
            result_dict = dict(zip(columns, record))
            results.append(result_dict)

        if is_print:
            print(f"Query execution completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        return results

    except (Exception, Error) as error:
        print(f"Error while fetching records: {error}")
        return []

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            if is_print:
                print(f"Connection closed at {time.strftime('%Y-%m-%d %H:%M:%S')}")


# def execute_command(query: str, is_print: bool = False) -> Optional[int]:
#     connection = None
#     cursor = None
#     last_insert_id = None
#
#     try:
#         if is_print:
#             print(f"Connection start at {time.strftime('%Y-%m-%d %H:%M:%S')}")
#             print(query)
#
#         connection = db_connection()
#         cursor = connection.cursor()
#
#         cursor.execute(query)
#         connection.commit()
#
#         # Try to get the last inserted ID if the query was an INSERT
#         if query.strip().lower().startswith('insert'):
#             cursor.execute("SELECT LASTVAL()")
#             last_insert_id = cursor.fetchone()[0]
#
#         if is_print:
#             print(f"Query execution completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
#
#         return last_insert_id
#
#     except (Exception, Error) as error:
#         print(f"Error while executing command: {error}")
#         if connection:
#             connection.rollback()
#         return None
#
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()
#             if is_print:
#                 print(f"Connection closed at {time.strftime('%Y-%m-%d %H:%M:%S')}")


def execute_command(query: str, is_print: bool = False) -> Optional[int]:
    connection = None
    cursor = None
    last_insert_id = None

    try:
        if is_print:
            print(f"Connection start at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("Executing query:")
            print(query)

        connection = db_connection()
        cursor = connection.cursor()

        cursor.execute(query)
        connection.commit()

        if query.strip().lower().startswith('insert'):
            cursor.execute("SELECT LASTVAL()")
            last_insert_id = cursor.fetchone()[0]

        if is_print:
            print(f"Query execution completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        return last_insert_id

    except (Exception, Error) as error:
        print("❌ Error while executing SQL command.")
        print(f"  ➤ Error Message: {error}")
        print("  ➤ Traceback:")
        traceback.print_exc()

        # Try to parse query for potential issue hint
        print("  ➤ Query snippet for inspection:")
        query_lines = query.strip().split(',')
        for i, line in enumerate(query_lines):
            print(f"    [{i+1}] {line.strip()}")

        if connection:
            connection.rollback()
        return None

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            if is_print:
                print(f"Connection closed at {time.strftime('%Y-%m-%d %H:%M:%S')}")