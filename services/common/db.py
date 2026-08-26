import os
import logging

import psycopg
from psycopg import Connection
from psycopg_pool import ConnectionPool

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


def create_connection_pool(
    *,
    read_only: bool = False,
    min_size: int | None = None,
    max_size: int | None = None,
) -> ConnectionPool:
    """Create a closed pool so the owning application controls its lifespan."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("db.missing_database_url")
        raise RuntimeError("DATABASE_URL is not set")

    pool_min_size = min_size if min_size is not None else int(os.getenv("DB_POOL_MIN_SIZE", "1"))
    pool_max_size = max_size if max_size is not None else int(os.getenv("DB_POOL_MAX_SIZE", "8"))
    if pool_min_size < 0 or pool_max_size < 1 or pool_min_size > pool_max_size:
        raise ValueError("database pool sizes must satisfy 0 <= min_size <= max_size")

    def configure(conn: Connection) -> None:
        if read_only:
            conn.execute("SET default_transaction_read_only = on")
            conn.commit()

    return ConnectionPool(
        conninfo=database_url,
        min_size=pool_min_size,
        max_size=pool_max_size,
        open=False,
        configure=configure,
        name="docmap-presentation" if read_only else "docmap",
    )
