import logging
import os
import threading

import psycopg2
import psycopg2.extensions
from psycopg2 import OperationalError

logger = logging.getLogger(__name__)

# Each thread (event-loop, thread-pool workers, background tasks) gets its
# own psycopg2 connection via threading.local().  This avoids the race
# condition where two threads issue SQL on the same libpq handle
# simultaneously (psycopg2 releases the GIL during wire I/O).
_thread_local = threading.local()


def get_connection() -> psycopg2.extensions.connection:
    """Return a per-thread psycopg2 connection (lazy, auto-recovering).

    Each thread gets its own connection stored in ``threading.local()``.
    Re-establishes the connection if it has been closed or is stuck in an
    unrecoverable transaction state.  Raises ``RuntimeError`` when
    ``DATABASE_URL`` is not set.
    """
    conn = getattr(_thread_local, "connection", None)

    # Re-create if missing or closed
    if conn is None or conn.closed:
        conn = _new_connection()
        _thread_local.connection = conn
        return conn

    # If the connection is stuck in a failed transaction, roll back to reset
    # it to IDLE so the next query can proceed cleanly.
    tx_status = conn.info.transaction_status
    if tx_status == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
        try:
            conn.rollback()
            logger.warning("Rolled back aborted transaction on reused connection.")
        except Exception:
            conn = _new_connection()
            _thread_local.connection = conn
    elif tx_status == psycopg2.extensions.TRANSACTION_STATUS_UNKNOWN:
        conn = _new_connection()
        _thread_local.connection = conn

    return conn


def _new_connection() -> psycopg2.extensions.connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    try:
        conn = psycopg2.connect(database_url)
        logger.info("Database connection established.")
        return conn
    except OperationalError:
        logger.error("Database connection failed", exc_info=True)
        raise

