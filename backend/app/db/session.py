import logging
import os

import psycopg2
from psycopg2 import OperationalError

logger = logging.getLogger(__name__)

_connection = None


def get_connection() -> psycopg2.extensions.connection:
    """Return a lazy psycopg2 connection.

    Does not connect at import time. Re-establishes the connection if it has
    been closed.  Raises ``RuntimeError`` when ``DATABASE_URL`` is not set.
    """
    global _connection
    if _connection is None or _connection.closed:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is not set.")
        try:
            _connection = psycopg2.connect(database_url)
            logger.info("Database connection established.")
        except OperationalError as exc:
            logger.error("Database connection failed", exc_info=True)
            raise
    return _connection

