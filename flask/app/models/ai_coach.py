from sqlalchemy import Column, Integer, BigInteger, ForeignKey, Text, String, DateTime
from sqlalchemy.sql import func
from .db import db


class ActivityInsight(db.Model):
    __tablename__ = 'vc_activity_insight'

    id          = Column(Integer, primary_key=True)
    activity_id = Column(BigInteger, ForeignKey('vc_strava_activity.id', ondelete='CASCADE'), nullable=False)
    user_id     = Column(Integer, ForeignKey('vc_user.id', ondelete='CASCADE'), nullable=False)
    insight_type = Column(String(32), nullable=False, default='ACTIVITY_INSIGHT')
    coach_insight = Column(Text, nullable=True)
    created_at  = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<ActivityInsight activity_id={self.activity_id} type={self.insight_type}>"
