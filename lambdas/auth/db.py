import os

import psycopg2
from psycopg2.extras import RealDictCursor

_connection = None


def get_connection():
    # Reuse connection across warm invocations; reconnect if Neon has closed it due to idle timeout
    global _connection
    if _connection is None or _connection.closed:
        _connection = psycopg2.connect(
            host=os.environ["POSTGRES_HOST"],
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            sslmode=os.environ.get("DB_SSLMODE", "disable"),
            cursor_factory=RealDictCursor,
            connect_timeout=5,
        )
        _connection.autocommit = True
    return _connection
