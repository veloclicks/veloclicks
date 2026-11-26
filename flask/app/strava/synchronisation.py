"""Durable, newest-first Strava synchronisation for all entry points."""

from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import case
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import Activity, SyncHistory, User, db
from app.models.activity_work import ActivitySyncJob
from app.shared_activities.entitlement import FULL_HISTORY_START, activity_cutoff, previous_year
from .coverage import missing_intervals
from . import strava_client, utils

logger = logging.getLogger(__name__)
ACTIVE = ("queued", "retry")
RECENT_DAYS = 30
HISTORY_DAYS = 365
MAX_FAILURES = 4


def _now() -> datetime:
    """Use whole UTC seconds for Strava and persisted boundaries."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def _epoch(value: datetime) -> int:
    """Interpret naive activity timestamps as UTC."""
    return int((value if value.tzinfo else value.replace(tzinfo=timezone.utc)).timestamp())


def _utc(epoch: int) -> datetime:
    """Convert an API epoch to an aware database interval boundary."""
    return datetime.fromtimestamp(epoch, timezone.utc)


def _lock_user(user_id: int, *, skip_locked: bool = False) -> User | None:
    """Serialize OAuth, enqueue and worker pages through one database lock."""
    return User.query.filter_by(id=user_id).with_for_update(skip_locked=skip_locked).first()


def status(user_id: int) -> dict:
    """Return sync and entitlement state without changing the queue."""
    user = db.session.get(User, user_id)
    job = db.session.get(ActivitySyncJob, user_id)
    connected = bool(user and (user.strava_access_token or user.strava_refresh_token))
    cutoff = activity_cutoff(user.membership_type.value).isoformat() + "Z" if user else None
    state = job.status if job else "idle"
    return {
        "status": state,
        "syncing": state in ACTIVE,
        "reconnect": state == "reconnect" or not connected,
        "revision": job.revision if job else 0,
        "error": job.error if job else None,
        "tier": user.membership_type.value if user else None,
        "activity_since": cutoff,
    }


def _set_window(job: ActivitySyncJob, kind: str, start: int, end: int, now: datetime) -> None:
    """Replace the current window while preserving the recent watermark and revision."""
    job.kind = kind
    job.from_epoch, job.to_epoch = start, end
    job.page = 1
    job.attempts = 0
    job.next_attempt = now
    job.status = "queued"
    job.error = None


def enqueue(user_id: int, kind: str = "automatic", window: tuple[int, int] | None = None,
            *, locked_user: User | None = None) -> dict:
    """Claim one sync slot or return the currently active or blocked job."""
    user = locked_user or _lock_user(user_id)
    if not user:
        return status(user_id)
    job = db.session.get(ActivitySyncJob, user_id)
    if job and (job.status in ACTIVE or job.status == "reconnect") and locked_user is None:
        db.session.commit()
        return status(user_id)
    if not (user.strava_access_token or user.strava_refresh_token):
        db.session.commit()
        return status(user_id)
    now = _now()
    if job and job.error == "rate_limit" and job.next_attempt.replace(tzinfo=timezone.utc) > now:
        db.session.commit()
        return status(user_id)
    end = _epoch(now)
    cutoff = max(_epoch(FULL_HISTORY_START), _epoch(activity_cutoff(user.membership_type.value, now)))
    if kind == "historical":
        start, requested_end = window
        end = min(end, requested_end)
        start = max(cutoff, start)
        window_kind = "requested"
    else:
        start = _epoch(now - timedelta(days=RECENT_DAYS))
        if kind == "manual" and job and job.recent_watermark:
            start = max(_epoch(previous_year(now)), job.recent_watermark)
        start = max(start, cutoff)
        window_kind = "recent"
    if not job:
        job = ActivitySyncJob(user_id=user_id)
        db.session.add(job)
    _set_window(job, window_kind, start, end, now)
    if start >= end:
        _schedule_gap(user, job, now, end)
    db.session.commit()
    return status(user_id)


def connect(user_id: int, exchange) -> dict:
    """Exchange an OAuth code under the same lock as import, then queue recent work."""
    user = _lock_user(user_id)
    if not user:
        return {"success": False, "error": "user_not_found"}
    token = exchange()
    if not token or not all(token.get(k) for k in ("access_token", "refresh_token", "expires_at")):
        db.session.rollback()
        return {"success": False, "error": "token_exchange"}
    _save_credentials(user, token)
    enqueue(user_id, locked_user=user)
    return {"success": True, "activity_count": 0}


def _save_credentials(user: User, data: dict) -> None:
    """Stage refreshed credentials in the transaction holding the sync lock."""
    user.strava_access_token = data["access_token"]
    user.strava_refresh_token = data["refresh_token"]
    user.token_expiry_epoch = data["expires_at"]


def _refresh(user: User, client_id: str, client_secret: str) -> str:
    """Refresh a provider token or mark the job as requiring a reconnect."""
    if not user.strava_refresh_token:
        raise strava_client.StravaFailure("reconnect")
    data = strava_client.refresh_credentials(user.strava_refresh_token, client_id, client_secret)
    _save_credentials(user, data)
    return user.strava_access_token


def _get_page(user: User, job: ActivitySyncJob, now: datetime, client_id: str, client_secret: str) -> list:
    """Refresh an expired token and retry one rejected access token once."""
    token = user.strava_access_token
    refreshed = not token or not user.token_expiry_epoch or user.token_expiry_epoch <= _epoch(now)
    if refreshed:
        token = _refresh(user, client_id, client_secret)
    try:
        return strava_client.fetch_activity_page(token, job.from_epoch, job.to_epoch, job.page)
    except strava_client.StravaFailure as error:
        if error.reason != "reconnect" or refreshed:
            raise
    token = _refresh(user, client_id, client_secret)
    return strava_client.fetch_activity_page(token, job.from_epoch, job.to_epoch, job.page)


def _persist_rows(user: User, job: ActivitySyncJob, rows: list) -> int:
    """Insert new owned rides once, filtering the provider's boundary overlap."""
    values = {}
    for row in rows:
        data = utils._get_key_activity_attributes(user.id, row)
        date = data.get("start_date")
        activity_id = data.get("id")
        if not date or type(activity_id) is not int:
            raise strava_client.StravaFailure("upstream")
        if job.from_epoch <= _epoch(date) < job.to_epoch:
            values[activity_id] = dict(data, ftp=user.ftp)
    if not values:
        return 0
    if db.session.get_bind().dialect.name == "postgresql":
        statement = pg_insert(Activity)
        # Rows can omit different optional Strava metrics. A common projection
        # keeps the insert shape deterministic across the whole page.
        columns = {key for row in values.values() for key in row}
        records = [{key: row.get(key) for key in columns} for row in values.values()]
        return db.session.execute(
            statement.values(records).on_conflict_do_nothing(index_elements=["id"])
        ).rowcount
    new = [Activity(**row) for key, row in values.items() if db.session.get(Activity, key) is None]
    db.session.add_all(new)
    return len(new)


def _record_coverage(user_id: int, lower: int, upper: int, now: datetime) -> None:
    """Merge adjacent successful windows in the page-completion transaction."""
    start, end = _utc(lower), _utc(upper)
    adjacent = SyncHistory.query.filter(
        SyncHistory.user_id == user_id, SyncHistory.from_date <= end, SyncHistory.to_date >= start,
    ).all()
    for row in adjacent:
        start = min(start, row.from_date.replace(tzinfo=timezone.utc))
        end = max(end, row.to_date.replace(tzinfo=timezone.utc))
        db.session.delete(row)
    db.session.add(SyncHistory(user_id=user_id, from_date=start, to_date=end, completed_at=now))


def _schedule_gap(user: User, job: ActivitySyncJob, now: datetime, through: int) -> None:
    """Resume at the newest missing interval within the current entitlement."""
    cutoff = max(_epoch(FULL_HISTORY_START), _epoch(activity_cutoff(user.membership_type.value, now)))
    completed = [(_epoch(row.from_date), _epoch(row.to_date))
                 for row in SyncHistory.query.filter_by(user_id=user.id)]
    gaps = missing_intervals(cutoff, through, completed)
    if gaps:
        start, end = gaps[0]
        _set_window(job, "history", max(start, end - HISTORY_DAYS * 86400), end, now)
    else:
        job.status, job.error = "complete", None


def _fail(job: ActivitySyncJob, error: strava_client.StravaFailure, now: datetime) -> None:
    """Leave the failed page unacknowledged and back off within API limits."""
    job.error = error.reason
    if error.reason == "reconnect":
        job.status = "reconnect"
        return
    job.attempts += 1
    job.next_attempt = now + timedelta(seconds=max(error.retry_after, 30 * 2 ** (job.attempts - 1)))
    job.status = "failed" if job.attempts >= MAX_FAILURES else "retry"


def process_one(client_id: str, client_secret: str) -> bool:
    """Process one durable page and acknowledge it only after the DB commit."""
    now = _now()
    candidates = db.session.query(ActivitySyncJob.user_id).filter(
        ActivitySyncJob.status.in_(ACTIVE), ActivitySyncJob.next_attempt <= now,
    ).order_by(case((ActivitySyncJob.kind == "recent", 0), else_=1),
               ActivitySyncJob.next_attempt, ActivitySyncJob.user_id).limit(16).all()
    for (user_id,) in candidates:
        user = _lock_user(user_id, skip_locked=True)
        if not user:
            continue
        job = db.session.get(ActivitySyncJob, user_id)
        if not job or job.status not in ACTIVE or job.next_attempt.replace(tzinfo=timezone.utc) > now:
            db.session.rollback()
            continue
        cutoff = max(_epoch(FULL_HISTORY_START), _epoch(activity_cutoff(user.membership_type.value, now)))
        if job.from_epoch < cutoff:
            job.from_epoch, job.page = cutoff, 1
        if job.from_epoch >= job.to_epoch:
            _schedule_gap(user, job, now, job.recent_watermark or _epoch(now))
            db.session.commit()
            return True
        try:
            rows = _get_page(user, job, now, client_id, client_secret)
            # A malformed or partially persisted page must leave no new coverage.
            with db.session.begin_nested():
                if _persist_rows(user, job, rows):
                    job.revision += 1
                if len(rows) == strava_client.PAGE_SIZE:
                    job.page += 1
                    job.next_attempt = now
                else:
                    _record_coverage(user.id, job.from_epoch, job.to_epoch, now)
                    if job.kind == "recent":
                        job.recent_watermark = job.to_epoch
                        user.last_synch_epoch = job.to_epoch
                    if job.kind == "requested":
                        job.status = "complete"
                    else:
                        _schedule_gap(user, job, now, job.recent_watermark or job.to_epoch)
                job.attempts, job.error = 0, None
                if job.status == "retry":
                    job.status = "queued"
        except (strava_client.StravaFailure, SQLAlchemyError, ValueError, TypeError, KeyError) as error:
            failure = error if isinstance(error, strava_client.StravaFailure) else strava_client.StravaFailure("upstream")
            _fail(job, failure, now)
        db.session.commit()
        logger.info("activity_sync_step status=%s kind=%s", job.status, job.kind)
        return True
    db.session.rollback()
    return False
