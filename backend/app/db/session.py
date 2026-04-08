import logging
import os

import psycopg2
import psycopg2.extensions
from psycopg2 import OperationalError

logger = logging.getLogger(__name__)

_connection = None


def get_connection() -> psycopg2.extensions.connection:
    """Return a lazy psycopg2 connection.

    Does not connect at import time. Re-establishes the connection if it has
    been closed or is in an unrecoverable state.  Raises ``RuntimeError``
    when ``DATABASE_URL`` is not set.
    """
    global _connection

    # Re-create if missing or closed
    if _connection is None or _connection.closed:
        _connection = _new_connection()
        return _connection

    # If the connection is stuck in a failed transaction, roll back to reset
    # it to IDLE so the next query can proceed cleanly.
    tx_status = _connection.info.transaction_status
    if tx_status == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
        try:
            _connection.rollback()
            logger.warning("Rolled back aborted transaction on reused connection.")
        except Exception:
            _connection = _new_connection()
    elif tx_status == psycopg2.extensions.TRANSACTION_STATUS_UNKNOWN:
        _connection = _new_connection()

    return _connection


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

