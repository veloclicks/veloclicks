"""Durable Strava imports and snapshot publication state."""

from .db import db


class ActivitySyncJob(db.Model):
    """One durable sync slot per user, claimed under their database row lock."""

    __tablename__ = "activity_sync_job"
    user_id = db.Column(db.Integer, db.ForeignKey("vc_user.id", ondelete="CASCADE"), primary_key=True)
    status = db.Column(db.String(16), nullable=False, default="queued")
    kind = db.Column(db.String(16), nullable=False, default="recent")
    from_epoch = db.Column(db.BigInteger, nullable=False)
    to_epoch = db.Column(db.BigInteger, nullable=False)
    page = db.Column(db.Integer, nullable=False, default=1)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    next_attempt = db.Column(db.DateTime(timezone=True), nullable=False)
    revision = db.Column(db.BigInteger, nullable=False, default=0)
    recent_watermark = db.Column(db.BigInteger)
    error = db.Column(db.String(24))
    __table_args__ = (db.Index("ix_activity_sync_due", "status", "next_attempt"),)


class ActivitySnapshotWork(db.Model):
    """Transactional dirty generation and retry state for one snapshot."""

    __tablename__ = "activity_snapshot_work"
    user_id = db.Column(db.Integer, db.ForeignKey("vc_user.id", ondelete="CASCADE"), primary_key=True)
    generation = db.Column(db.BigInteger, nullable=False, default=1)
    published = db.Column(db.BigInteger, nullable=False, default=0)
    digest = db.Column(db.String(64))
    next_attempt = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
