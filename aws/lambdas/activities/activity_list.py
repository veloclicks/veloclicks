"""Bounded, read-only pages from the existing PostgreSQL activity table."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from functools import lru_cache
from time import perf_counter

from itsdangerous import BadData, URLSafeSerializer
from sqlalchemy import (
    BigInteger, Column, DateTime, Float, Integer, MetaData, String, Table,
    create_engine, select, tuple_,
)
from sqlalchemy.engine import Engine, make_url


# The prototype mirrors the public projection of Flask's Activity.to_dict()
# without importing its ORM metadata. The parity tests cover schema drift.
_dates = ("start_date", "start_date_local")
_measures = (
    "distance", "elapsed_time", "moving_time", "average_speed", "max_speed",
    "average_watts", "max_watts", "weighted_average_watts", "average_heartrate",
    "max_heartrate", "suffer_score", "average_cadence", "total_elevation_gain",
    "elev_low", "elev_high", "tss",
)
activities = Table(
    "vc_strava_activity",
    MetaData(),
    Column("id", BigInteger),
    Column("user_id", Integer),
    Column("name", String),
    Column("type", String),
    Column("ftp", Integer),
    Column("rpe", Integer),
    *(Column(field, DateTime) for field in _dates),
    *(Column(field, Float(12, asdecimal=True)) for field in _measures),
)


class InvalidPage(ValueError):
    """The request cannot be converted to a valid page of activities."""


@lru_cache(maxsize=1)
def database_engine(database_url: str) -> Engine:
    """Keep one lazy PostgreSQL pool per Lambda environment."""
    url = make_url(database_url)
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+psycopg2")
    options = url.query.get("options", "")
    return create_engine(
        url, pool_size=1, max_overflow=0, pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "options": f"{options} -c default_transaction_read_only=on"},
    )


def _serialize(row: Mapping) -> dict:
    """Use Flask's activity timestamp, numeric precision and null conventions."""
    data = dict(row)
    for field in _dates:
        if data[field] is not None:
            data[field] = data[field].isoformat()
    for field in _measures:
        if data[field] is not None:
            data[field] = round(float(data[field]), 1 if field == "tss" else 2)
    return data


def _date_window(years: str) -> tuple[datetime, datetime]:
    """Interpret years and the rolling window exactly as the Flask list does."""
    if not years:
        end = datetime.now()
        return end - timedelta(days=180), end
    try:
        selected = [int(year.strip()) for year in years.split(",")]
        return datetime(min(selected), 1, 1), datetime(max(selected), 12, 31, 23, 59, 59)
    except (ValueError, TypeError) as error:
        raise InvalidPage("Invalid years parameter") from error


def activity_page(engine: Engine, user_id: int, query: Mapping[str, str], secret: str, timings: dict | None = None) -> dict:
    """Return one page with a signed cursor compatible with the Flask API."""
    timings = {} if timings is None else timings
    started = perf_counter()
    cursor = query.get("cursor")
    if "limit" not in query:
        raise InvalidPage("Cursor requires a limit" if cursor is not None else "Limit is required")
    try:
        limit = int(query["limit"])
        if not 1 <= limit <= 50:
            raise ValueError
    except (TypeError, ValueError) as error:
        raise InvalidPage("Limit must be between 1 and 50") from error

    years = query.get("years") or ""
    start, end = _date_window(years)
    signer = URLSafeSerializer(secret, salt="activity-list-cursor")
    scope = [user_id, years]
    before = None
    if cursor is not None:
        try:
            cursor_scope, window_end, date, activity_id = signer.loads(cursor)
            if cursor_scope != scope:
                raise ValueError
            if not years:
                end = datetime.fromisoformat(window_end)
                start = end - timedelta(days=180)
            before = datetime.fromisoformat(date), activity_id
        except (BadData, TypeError, ValueError) as error:
            raise InvalidPage("Invalid activity cursor") from error

    columns = activities.c
    statement = select(activities).where(
        columns.user_id == user_id,
        columns.start_date >= start,
        columns.start_date <= end,
    )
    if before is not None:
        statement = statement.where(tuple_(columns.start_date, columns.id) < before)

    # Read one extra row to detect a continuation without a count query.
    statement = statement.order_by(columns.start_date.desc(), columns.id.desc()).limit(limit + 1)
    timings["prepare_query_ms"] = round((perf_counter() - started) * 1000, 2)
    started = perf_counter()
    try:
        with engine.connect() as connection:
            timings["connection_checkout_ms"] = round((perf_counter() - started) * 1000, 2)
            started = perf_counter()
            try:
                rows = connection.execute(statement).mappings().all()
            finally:
                timings["query_fetch_ms"] = round((perf_counter() - started) * 1000, 2)
                started = perf_counter()
    finally:
        phase = "connection_release_ms" if "query_fetch_ms" in timings else "connection_checkout_ms"
        timings[phase] = round((perf_counter() - started) * 1000, 2)

    started = perf_counter()

    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = signer.dumps([scope, end.isoformat(), last.start_date.isoformat(), last.id])
    result = {"activities": [_serialize(row) for row in rows[:limit]], "next_cursor": next_cursor}
    timings["row_serialization_ms"] = round((perf_counter() - started) * 1000, 2)
    return result
