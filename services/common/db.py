import os
import logging

import psycopg
from psycopg import Connection

logger = logging.getLogger(__name__)


def get_connection() -> Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("db.missing_database_url")
        raise RuntimeError("DATABASE_URL is not set")
    logger.debug("db.connect_start")
    conn = psycopg.connect(database_url)
    logger.debug("db.connect_success")
    return conn
