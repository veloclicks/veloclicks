"""Bounded, read-only pages from the existing PostgreSQL activity table."""

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from time import perf_counter

from sqlalchemy import (
    BigInteger, Column, DateTime, Float, Integer, MetaData, String, Table,
    create_engine, select, tuple_,
)
from sqlalchemy.engine import Engine, make_url
from shared_activities.entitlement import history_predicate
from shared_activities.pagination import ActivityCursor, InvalidPage, date_window, limit_value


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


users = Table("vc_user", MetaData(), Column("id", Integer), Column("membership_type", String))


def user_tier(engine: Engine, user_id: int) -> str | None:
    """Read current entitlement for snapshots containing potentially restricted rows."""
    with engine.connect() as connection:
        return connection.scalar(select(users.c.membership_type).where(users.c.id == user_id))


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


def activity_page(engine: Engine, user_id: int, query: Mapping[str, str], secret: str, timings: dict | None = None) -> dict:
    """Return one page with a signed cursor compatible with the Flask API."""
    timings = {} if timings is None else timings
    started = perf_counter()
    cursor = query.get("cursor")
    if "limit" not in query:
        raise InvalidPage("Cursor requires a limit" if cursor is not None else "Limit is required")
    limit = limit_value(query["limit"])
    years = query.get("years") or ""
    start, end = date_window(years, datetime.now(timezone.utc).replace(tzinfo=None))
    signer = ActivityCursor(secret, user_id, years)
    before = None
    if cursor is not None:
        window_end, before = signer.decode(cursor)
        if window_end is not None:
            end = window_end
            start = end - timedelta(days=180)

    columns = activities.c
    statement = select(activities).where(
        columns.user_id == user_id,
        history_predicate(columns.start_date, users.c.id, users.c.membership_type, user_id),
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
                try:
                    result = connection.execute(statement)
                finally:
                    timings["query_execute_ms"] = round((perf_counter() - started) * 1000, 2)
                    started = perf_counter()
                try:
                    rows = result.mappings().all()
                finally:
                    timings["result_fetch_ms"] = round((perf_counter() - started) * 1000, 2)
            finally:
                started = perf_counter()
    finally:
        phase = "connection_release_ms" if "connection_checkout_ms" in timings else "connection_checkout_ms"
        timings[phase] = round((perf_counter() - started) * 1000, 2)

    started = perf_counter()

    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = signer.encode(end, last.start_date, last.id)
    result = {"activities": [_serialize(row) for row in rows[:limit]], "next_cursor": next_cursor}
    timings["row_serialization_ms"] = round((perf_counter() - started) * 1000, 2)
    timings["activity_count"] = len(result["activities"])
    timings["has_more"] = next_cursor is not None
    return result
