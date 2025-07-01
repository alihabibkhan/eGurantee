from datetime import datetime
from random import randint
import pymysql
from dotenv import load_dotenv
import os
load_dotenv()

c_host = "localhost" or os.getenv('MYSQL_HOST')
c_user = "root" or os.getenv('MYSQL_USER')
c_pwd = "" or os.getenv('MYSQL_PASSWORD')
c_cdb = "eguarantee_db" or os.getenv('MYSQL_DATABASE')


def db_connection():
    is_successful = False
    retried_attempts = 0
    max_attempts = 3

    while not is_successful and retried_attempts < max_attempts:
        if retried_attempts != 0:
            print("DB_Connection isSuccessful: " + str(is_successful) + ", RetriedAttempted: " + str(
                retried_attempts))
        try:

            db_connect = pymysql.connect(host=c_host, user=c_user, passwd=c_pwd, database=c_cdb)
            is_successful = True

            return db_connect

        except Exception as ex:
            print("Error while connecting with Database. Details: "+str(ex))
            retried_attempts = retried_attempts + 1

    if retried_attempts >= max_attempts:
        print("Server encountered an error while connecting with Internal Services.")

    return None


def fetch_records(query, is_print=False):
    query_key = str(randint(5, 100000))

    try:
        if is_print:
            print("FetchRecords:"+query_key+", connection_start:"+str(datetime.now()))
            print("query: "+str(query))

        connection = db_connection()
        if connection not in [None]:

            db_cursor = connection.cursor(pymysql.cursors.DictCursor)
            db_cursor.execute(query)
            my_result = db_cursor.fetchall()

            connection.commit()
            db_cursor.close()

            connection.close()

            if is_print:
                print("FetchRecords:"+query_key+", connection_close:"+str(datetime.now()))

            return my_result

    except Exception as ex:
        print("FetchRecords:"+query_key+", exception:"+str(datetime.now()))
        print("Error FetchRecords: Error Details:"+str(ex))
        raise ValueError("An error occurred. Kindly refresh the page.")


def execute_command(query, is_print=False):
    query_key = str(randint(5, 100000))
    try:
        if is_print:
            print("ExecuteCommand:" + query_key + ", connection_start:" + str(datetime.now()))
            print("query: "+str(query))

        inserted_record_id = ""

        connection = db_connection()
        if connection not in [None]:

            db_cursor = connection.cursor()
            db_cursor.execute(query)

            if str(query).strip().lower().startswith("insert into"):
                inserted_record_id = db_cursor.lastrowid

            connection.commit()
            db_cursor.close()
            connection.close()

            if is_print:
                print("ExecuteCommand:" + query_key + ", connection_close:" + str(datetime.now()))

            return str(inserted_record_id)

    except Exception as ex:
        print("ExecuteCommand:"+query_key+", exception:"+str(datetime.now()))
        print("Error ExecuteCommand: Error Details:"+str(ex))
        raise ValueError("An error occurred. Kindly refresh the page.")