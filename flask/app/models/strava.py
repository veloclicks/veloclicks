from sqlalchemy import Column, String, Integer, BigInteger, ForeignKey, Float, Text, Boolean, DateTime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKeyConstraint

from .db import db
from .user import User

class Activity(db.Model): 
    __tablename__ = 'vc_strava_activity'
   
    user_id = Column(Integer, ForeignKey('vc_user.id'), nullable=False)
    
    id = Column(BigInteger, primary_key=True)
    __table_args__ = (        
        ForeignKeyConstraint([user_id], [User.id], ondelete='NO ACTION'),        
    )
   
    # Basics
    name        = Column(String(128), nullable=True)

    start_date_local = Column(DateTime, nullable=True)
    start_date       = Column(DateTime, nullable=True)
    
    type                = Column(String(32), nullable=True)
    distance            = Column(Float(12, 2), nullable=True)
    
    # Time
    elapsed_time        = Column(Float(12, 2), nullable=True)
    moving_time         = Column(Float(12, 2), nullable=True)
    
    # Speed
    average_speed = Column(Float(12, 2), nullable=True)
    max_speed = Column(Float(12, 2), nullable=True)

    # Power
    average_watts = Column(Float(12, 2), nullable=True)
    max_watts = Column(Float(12, 2), nullable=True)
    weighted_average_watts = Column(Float(12, 2), nullable=True)
    
    # HR
    average_heartrate = Column(Float(12, 2), nullable=True)
    max_heartrate   = Column(Float(12, 2), nullable=True)
    suffer_score    = Column(Float(12, 2), nullable=True)
    
    # cadence
    average_cadence = Column(Float(12, 2), nullable=True)
    
    # elevation
    total_elevation_gain    = Column(Float(12, 2), nullable=True)
    elev_low                = Column(Float(12, 2), nullable=True)
    elev_high               = Column(Float(12, 2), nullable=True)

    # Power Analysis
    ftp = Column(Integer, nullable=True)                    # User's FTP at time of activity
    rpe = Column(Integer, nullable=True)                    # Rate of Perceived Exertion (1-10)
    power_curve_data = Column(Text, nullable=True)          # JSON: {duration_seconds: max_watts}
    time_in_zones = Column(Text, nullable=True)             # JSON: {zone_name: seconds}

    def __repr__(self):
        return f"{self.email}"
    
        
    # FOR JSON SERIALIZATION    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "start_date_local": self.start_date_local.isoformat() if self.start_date_local else None,
            "type": self.type,
            "distance": round(float(self.distance), 2) if self.distance is not None else None,
            "elapsed_time": round(float(self.elapsed_time), 2) if self.elapsed_time is not None else None,
            "moving_time": round(float(self.moving_time), 2) if self.moving_time is not None else None,
            "average_speed": round(float(self.average_speed), 2) if self.average_speed is not None else None,
            "max_speed": round(float(self.max_speed), 2) if self.max_speed is not None else None,
            "average_watts": round(float(self.average_watts), 2) if self.average_watts is not None else None,
            "max_watts": round(float(self.max_watts), 2) if self.max_watts is not None else None,
            "weighted_average_watts": round(float(self.weighted_average_watts), 2) if self.weighted_average_watts is not None else None,
            "average_heartrate": round(float(self.average_heartrate), 2) if self.average_heartrate is not None else None,
            "max_heartrate": round(float(self.max_heartrate), 2) if self.max_heartrate is not None else None,
            "suffer_score": round(float(self.suffer_score), 2) if self.suffer_score is not None else None,
            "average_cadence": round(float(self.average_cadence), 2) if self.average_cadence is not None else None,
            "total_elevation_gain": round(float(self.total_elevation_gain), 2) if self.total_elevation_gain is not None else None,
            "elev_low": round(float(self.elev_low), 2) if self.elev_low is not None else None,
            "elev_high": round(float(self.elev_high), 2) if self.elev_high is not None else None,
            "ftp": self.ftp,
            "rpe": self.rpe,
            "power_curve_data": self.power_curve_data,
            "time_in_zones": self.time_in_zones,
        }

        