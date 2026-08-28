import os

import psycopg2
from psycopg2.extras import RealDictCursor

_connection = None


def _dsn():
    # DATABASE_URL is set in AWS (resolved from SSM); locally it falls back to
    # the split POSTGRES_* vars, matching the Flask app's config pattern.
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url
    return (
        f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ.get('POSTGRES_PORT', '5432')}"
        f"/{os.environ['POSTGRES_DB']}"
    )


def get_connection():
    # Reuse connection across warm invocations; reconnect if Neon has closed it due to idle timeout
    global _connection
    if _connection is None or _connection.closed:
        _connection = psycopg2.connect(
            _dsn(),
            cursor_factory=RealDictCursor,
            connect_timeout=5,
        )
        _connection.autocommit = True
    return _connection
