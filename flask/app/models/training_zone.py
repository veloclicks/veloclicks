from sqlalchemy import Column, String, Integer, ForeignKey, Index, Enum
from .db import db
from .user import User
import enum


class ZoneType(enum.Enum):
    POWER = 'power'
    HEART_RATE = 'heart_rate'


class TrainingZone(db.Model):
    __tablename__ = 'vc_training_zone'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('vc_user.id'), nullable=False)

    type = Column(Enum(ZoneType), nullable=False)
    name = Column(String(20), nullable=False)  # 'z1', 'z2', 'sweet_spot', etc.
    display_name = Column(String(50), nullable=False)  # 'Z1 - Active Recovery'

    min = Column(Integer, nullable=False)  # watts or bpm
    max = Column(Integer, nullable=False)  # watts or bpm

    sort_order = Column(Integer, nullable=False)  # For ordering zones in display

    __table_args__ = (
        Index('idx_user_zone_type', user_id, type),
    )

    def __repr__(self):
        return f"<TrainingZone {self.user_id} {self.type} {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type.value,
            'name': self.name,
            'display_name': self.display_name,
            'min_value': self.min,
            'max_value': self.max,
            'sort_order': self.sort_order
        }
