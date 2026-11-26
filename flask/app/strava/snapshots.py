"""Build and publish entitlement-aware activity snapshots from durable work."""

from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import select, update

from app.models import User, db
from app.models.activity_work import ActivitySnapshotWork
from app.shared_activities import snapshot
from .service import get_stored_activity_page

logger = logging.getLogger(__name__)


def _lock_publisher(user_id: int) -> bool:
    """Serialize publishers while letting activity edits commit during object I/O."""
    if db.session.get_bind().dialect.name != "postgresql":
        return True
    return bool(db.session.execute(select(db.func.pg_try_advisory_xact_lock(781625, user_id))).scalar())


def _publish(work: ActivitySnapshotWork, *, force: bool = False) -> bool:
    """Publish a single generation and acknowledge it only if it is still current."""
    if not _lock_publisher(work.user_id):
        db.session.rollback()
        return False

    db.session.refresh(work)
    now = datetime.now(timezone.utc)
    if not force and work.next_attempt.replace(tzinfo=timezone.utc) > now:
        db.session.rollback()
        return False
    user = db.session.get(User, work.user_id)
    if not user:
        db.session.rollback()
        return False
    generation = work.generation
    rows, _ = get_stored_activity_page(user.id, None, None, 50, None)
    body, digest = snapshot.encode(user.id, [row.to_dict() for row in rows])
    changed = digest != work.digest
    try:
        if changed or (snapshot.stored_digest(user.id) != digest):
            snapshot.write(user.id, body)
    except Exception as error:
        logger.warning("activity_snapshot_publish_failed error=%s", type(error).__name__)
        db.session.execute(update(ActivitySnapshotWork).where(
            ActivitySnapshotWork.user_id == user.id,
            ActivitySnapshotWork.generation == generation,
        ).values(next_attempt=now + timedelta(minutes=1)))
        db.session.commit()
        return False

    # Changes after the query leave the newer generation pending. Only one
    # publisher can write at a time, so an older worker cannot overwrite it.
    db.session.execute(update(ActivitySnapshotWork).where(
        ActivitySnapshotWork.user_id == user.id,
        ActivitySnapshotWork.generation == generation,
    ).values(published=generation, digest=digest, next_attempt=now + timedelta(days=1)))
    db.session.commit()
    logger.info("activity_snapshot_checked changed=%s", changed)
    return True


def process_one() -> bool:
    """Publish one due snapshot, including reevaluation of rolling expiry."""
    if not snapshot.storage_configured():
        return False
    now = datetime.now(timezone.utc)
    work = ActivitySnapshotWork.query.filter(
        ActivitySnapshotWork.next_attempt <= now,
    ).order_by(ActivitySnapshotWork.next_attempt).first()
    return _publish(work) if work else False


def seed(user_id: int) -> bool:
    """Seed or repair a single user's snapshot without touching sync coverage."""
    if not snapshot.storage_configured():
        raise RuntimeError("Configure a private snapshot destination before seeding.")
    user = User.query.filter_by(id=user_id).with_for_update().first()
    if not user:
        raise ValueError("User not found.")
    work = db.session.get(ActivitySnapshotWork, user_id)
    if not work:
        db.session.add(ActivitySnapshotWork(user_id=user_id))
    db.session.commit()
    return _publish(db.session.get(ActivitySnapshotWork, user_id), force=True)
