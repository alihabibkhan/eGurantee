import psycopg2
from psycopg2 import Error
from psycopg2 import pool as pg_pool
import threading
import time
from typing import List, Dict, Optional
import traceback
import os

POSTGRES_CONNECTION = os.getenv('POSTGRES_CONNECTION')


# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------
# Connections are opened once and reused across requests instead of paying the
# TCP + SSL handshake on every query. The pool is created lazily per process
# (so each gunicorn worker gets its own pool after fork).
DB_POOL_MIN_CONN = int(os.getenv('DB_POOL_MIN_CONN', 1))
DB_POOL_MAX_CONN = int(os.getenv('DB_POOL_MAX_CONN', 10))
# Connections idle longer than this are pinged before reuse, because the
# server / load balancer may have silently dropped them.
DB_POOL_IDLE_CHECK_SECONDS = int(os.getenv('DB_POOL_IDLE_CHECK_SECONDS', 60))

_CONNECT_KWARGS = {
    'dsn': str(POSTGRES_CONNECTION),
    'connect_timeout': 10,
    'keepalives': 1,
    'keepalives_idle': 30,
    'keepalives_interval': 10,
    'keepalives_count': 5,
}

_pool = None
_pool_pid = None
_pool_lock = threading.Lock()
_last_used = {}         # id(conn) -> time it was returned to the pool
_overflow_conns = set() # id(conn) of connections opened outside the pool


class _AutocommitConnectionPool(pg_pool.ThreadedConnectionPool):
    """
    Pooled connections run in autocommit mode: plain SELECTs don't leave a
    transaction open, so no extra ROLLBACK round trip is needed when a
    connection is returned. execute_command() sends each command as a single
    statement, so it is still atomic.
    """
    def _connect(self, key=None):
        connection = super()._connect(key)
        connection.autocommit = True
        return connection


def _new_connection():
    connection = psycopg2.connect(**_CONNECT_KWARGS)
    connection.autocommit = True
    return connection


def _get_pool():
    global _pool, _pool_pid
    pid = os.getpid()
    if _pool is not None and _pool_pid == pid:
        return _pool

    with _pool_lock:
        if _pool is None or _pool_pid != pid:
            # A pool inherited from a parent process (fork) must not be reused.
            _pool = _AutocommitConnectionPool(DB_POOL_MIN_CONN, DB_POOL_MAX_CONN, **_CONNECT_KWARGS)
            _pool_pid = pid
            _last_used.clear()
            _overflow_conns.clear()
            print(f"DB pool created (pid={pid}, min={DB_POOL_MIN_CONN}, max={DB_POOL_MAX_CONN})")
    return _pool


def _is_connection_alive(connection) -> bool:
    if connection.closed:
        return False

    last_used = _last_used.get(id(connection))
    if last_used is not None and time.time() - last_used < DB_POOL_IDLE_CHECK_SECONDS:
        return True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


def get_connection():
    """
    Borrow a connection from the pool. Always hand it back with
    release_connection() (never call connection.close() directly).
    """
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            db_pool = _get_pool()
            try:
                connection = db_pool.getconn()
            except pg_pool.PoolError:
                # Pool exhausted: open a temporary connection rather than failing the request.
                print(f"DB pool exhausted (max={DB_POOL_MAX_CONN}), opening a temporary connection")
                connection = _new_connection()
                _overflow_conns.add(id(connection))
                return connection

            if _is_connection_alive(connection):
                return connection

            # Stale connection: discard it and try again.
            release_connection(connection, discard=True)

        except (Exception, Error) as error:
            print(f"Error while getting PostgreSQL connection (Attempt {attempt}/{max_attempts}): {error}")
            if attempt < max_attempts:
                time.sleep(2)

    print(f"Failed to get a database connection after {max_attempts} attempts")
    raise Exception("Database connection failed")


def release_connection(connection, discard: bool = False):
    """Return a connection to the pool (or close it if it is broken / temporary)."""
    if connection is None:
        return

    conn_id = id(connection)
    if conn_id in _overflow_conns:
        _overflow_conns.discard(conn_id)
        try:
            connection.close()
        except Exception:
            pass
        return

    discard = discard or bool(connection.closed)
    try:
        _get_pool().putconn(connection, close=discard)
    except Exception as error:
        print(f"Error while releasing PostgreSQL connection: {error}")
        try:
            connection.close()
        except Exception:
            pass
        discard = True

    if discard:
        _last_used.pop(conn_id, None)
    else:
        _last_used[conn_id] = time.time()


def close_pool():
    """Close every pooled connection (e.g. on shutdown)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None
            _last_used.clear()


def _is_connection_error(error) -> bool:
    return isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError))


# NOTE: db_connection() opens a standalone (non-pooled) connection and is kept
# for scripts that manage the connection themselves. Application queries go
# through fetch_records() / execute_command(), which use the pool.
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


def fetch_records(query: str, is_print: bool = True, params: Optional[tuple] = None) -> List[Dict]:
    # A pooled connection can be dropped by the server while idle; if a read
    # fails because of that, retry once on a fresh connection.
    results, connection_failed = _fetch_records_once(query, is_print, params)
    if connection_failed:
        print("Retrying fetch_records on a fresh connection")
        results, _ = _fetch_records_once(query, is_print, params)
    return results


def _fetch_records_once(query: str, is_print: bool, params: Optional[tuple]):
    connection = None
    cursor = None
    results = []
    discard_connection = False

    try:
        if is_print:
            print(f"Connection start at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(query)

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        records = cursor.fetchall()

        for record in records:
            result_dict = dict(zip(columns, record))
            results.append(result_dict)

        if is_print:
            print(f"Query execution completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        return results, False

    except (Exception, Error) as error:
        print(f"Error while fetching records: {error}")
        discard_connection = _is_connection_error(error)
        return [], discard_connection

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if connection:
            release_connection(connection, discard=discard_connection)
            if is_print:
                print(f"Connection released at {time.strftime('%Y-%m-%d %H:%M:%S')}")


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


def execute_command(query: str, is_print: bool = False, return_id: bool = True) -> Optional[int]:
    connection = None
    cursor = None
    last_insert_id = None
    discard_connection = False

    try:
        if is_print:
            print(f"Connection start at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("Executing query:")
            print(query)

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(query)
        connection.commit()

        if query.strip().lower().startswith('insert') and return_id is True:
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

        discard_connection = _is_connection_error(error)
        if connection and not connection.closed:
            try:
                connection.rollback()
            except Exception:
                discard_connection = True
        return None

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if connection:
            release_connection(connection, discard=discard_connection)
            if is_print:
                print(f"Connection released at {time.strftime('%Y-%m-%d %H:%M:%S')}")