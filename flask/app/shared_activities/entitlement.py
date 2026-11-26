"""Apply the activity-history entitlement to UTC timestamps in both APIs."""

from datetime import datetime, timezone

PREMIUM = "PREMIUM_TIER"
# Strava's list endpoint accepts Unix seconds and an omitted lower bound.
FULL_HISTORY_START = datetime(1970, 1, 1)


def utc_naive(value: datetime) -> datetime:
    """Convert a timestamp to the database's naive UTC representation."""
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def previous_year(now: datetime) -> datetime:
    """Return the same UTC date twelve months ago, clamping leap day."""
    try:
        return now.replace(year=now.year - 1)
    except ValueError:
        return now.replace(year=now.year - 1, day=28)


def activity_cutoff(tier: str, now: datetime | None = None) -> datetime:
    """Return the oldest store timestamp the membership may access."""
    if tier == PREMIUM:
        return datetime.min
    return previous_year(utc_naive(now or datetime.now(timezone.utc)))


def history_predicate(start_date, account_id, membership_type, user_id: int):
    """Build a single-statement eligibility check against live membership."""
    from sqlalchemy import or_, select

    premium = select(account_id).where(account_id == user_id, membership_type == PREMIUM).exists()
    return or_(start_date >= activity_cutoff("FREE_TIER"), premium)
