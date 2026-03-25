from sqlalchemy import Column, Integer, BigInteger, ForeignKey, Text
from sqlalchemy.orm import relationship
from .db import db
from .user import User


class ActivityAnalytics(db.Model):
    __tablename__ = 'vc_activity_analytics'

    id          = Column(Integer, primary_key=True)
    activity_id = Column(BigInteger, ForeignKey('vc_strava_activity.id', ondelete='CASCADE'), nullable=False, unique=True)
    user_id     = Column(Integer, ForeignKey('vc_user.id', ondelete='CASCADE'), nullable=False)

    classification_data = Column(Text, nullable=True)   # JSON: workout classification + evidence
    execution_data      = Column(Text, nullable=True)   # JSON: interval analysis + execution metrics
    power_curve_data    = Column(Text, nullable=True)   # JSON: {duration_seconds: max_watts}
    time_in_zones       = Column(Text, nullable=True)   # JSON: {zone_name: seconds}

    def __repr__(self):
        return f"<ActivityAnalytics activity_id={self.activity_id}>"
