import logging
import numpy as np
from typing import Optional

from app.models import db
from app.models.strava import Activity
from app.strava.streams import get_activity_streams

logger = logging.getLogger(__name__)


def calculate_tss(user_id: int, activity_id: int, calculation_method: str = 'power') -> Optional[float]:
    """
    Calculate Training Stress Score (TSS) for an activity.

    Power-based TSS formula (matches TrainerRoad calculation):
    TSS = (duration_seconds × NP × IF) / (FTP × 3600) × 100
    where IF = NP / FTP

    This is the preferred method when power data is available and closely matches
    TrainerRoad's TSS calculations (typically within 2-4%).

    Heart rate-based TSS (TRIMP method):
    - For each second: TRIMP += duration * HR_fraction * exp_factor
    - HR_fraction = (HR - resting_HR) / (max_HR - resting_HR)
    - exp_factor = exp(1.92 * HR_fraction) for males, exp(1.67 * HR_fraction) for females

    Note: HR-based TSS may produce values significantly different from power-based calculations.

    Args:
        user_id: ID of the user (for authorization checks)
        activity_id: ID of the activity to analyze
        calculation_method: Method to use - 'power' or 'hr'

    Returns:
        TSS value as float, 0.0 if no data exists, or None if calculation failed
    """
    try:
        activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
        if not activity:
            logger.error(f"Activity {activity_id} not found for user {user_id}")
            return None

        from app.models.user import User
        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return None

        use_power = False
        use_hr = False

        if calculation_method == 'power':
            use_power = True
        elif calculation_method == 'hr':
            use_hr = True
        else:
            logger.error(f"Invalid calculation_method: {calculation_method}. Use 'power' or 'hr'")
            return None

        if use_power:
            if not activity.weighted_average_watts or not user.ftp:
                logger.warning(f"Power-based TSS requested but data missing (NP={activity.weighted_average_watts}, FTP={user.ftp})")
                return None
            else:
                normalized_power = float(activity.weighted_average_watts)
                ftp = float(user.ftp)
                duration_seconds = float(activity.moving_time) if activity.moving_time else 0

                if duration_seconds > 0 and ftp > 0:
                    intensity_factor = normalized_power / ftp
                    tss = (duration_seconds * normalized_power * intensity_factor) / (ftp * 3600) * 100
                    activity.tss = round(tss, 1)
                    db.session.commit()
                    logger.info(f"Calculated power-based TSS for activity {activity_id}: {tss:.1f} (NP={normalized_power}W, FTP={ftp}W, IF={intensity_factor:.3f})")
                    return round(tss, 1)

        if use_hr:
            logger.info(f"Using HR-based TSS for activity {activity_id}")

        streams = get_activity_streams(user_id, activity_id, ['heartrate', 'time'])
        if not streams or 'heartrate' not in streams or 'time' not in streams:
            activity.tss = 0.0
            db.session.commit()
            logger.warning(f"No heart rate data available for activity {activity_id}")
            return 0.0

        hr_data = streams['heartrate']['data']
        time_data = streams['time']['data']

        if not isinstance(hr_data, list):
            logger.error(f"Heart rate data is not a list for activity {activity_id}: type={type(hr_data)}, value={hr_data}")
            activity.tss = 0.0
            db.session.commit()
            return 0.0

        if not hr_data or len(hr_data) == 0:
            activity.tss = 0.0
            db.session.commit()
            logger.warning(f"Empty heart rate data for activity {activity_id}")
            return 0.0

        from app.models.user import User
        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return None

        if not user.max_heart_rate or not user.resting_heart_rate:
            logger.warning(f"User {user_id} missing max_heart_rate or resting_heart_rate")
            activity.tss = 0.0
            db.session.commit()
            return 0.0

        max_hr = float(user.max_heart_rate)
        resting_hr = float(user.resting_heart_rate)
        exp_multiplier = 1.92 if user.sex in ['Male', 'M', None] else 1.67

        trimp_total = 0.0
        for hr in hr_data:
            if hr is None or hr <= 0:
                continue
            hr_fraction = (hr - resting_hr) / (max_hr - resting_hr)
            hr_fraction = max(0.0, min(1.2, hr_fraction))
            exp_factor = np.exp(exp_multiplier * hr_fraction)
            trimp_total += 1.0 * hr_fraction * exp_factor

        tss = trimp_total / 60.0
        activity.tss = round(tss, 1)
        db.session.commit()

        logger.info(f"Calculated TSS for activity {activity_id}: {tss:.1f}")
        return round(tss, 1)

    except Exception as e:
        logger.error(f"Error calculating TSS for activity {activity_id}: {str(e)}")
        db.session.rollback()
        return None
