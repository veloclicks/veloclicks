from .db import db


class SyncHistory(db.Model):
    """Successfully retrieved and persisted half-open UTC intervals."""
    __tablename__ = "sync_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("vc_user.id"), nullable=False)
    from_date = db.Column(db.DateTime(timezone=True), nullable=False)
    to_date = db.Column(db.DateTime(timezone=True), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=False,
                             server_default=db.func.now())
    __table_args__ = (
        db.CheckConstraint("from_date < to_date", name="ck_sync_history_interval"),
        db.Index("ix_sync_history_user_dates", "user_id", "from_date", "to_date"),
    )
