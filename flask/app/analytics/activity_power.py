import json
import logging
import numpy as np
from typing import Dict, List, Optional

from app.models import db
from app.models.strava import Activity
from app.models.analytics import ActivityAnalytics
from app.profile.training_zones import get_user_zones
from app.models.training_zone import ZoneType
from app.strava.streams import get_activity_streams

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------
#
#                                     POWER CURVE
#
# --------------------------------------------------------------------------------------

#
# Workout which power checkpoints to show when displaying the power curve - rather than continuous
#
def _generate_power_curve_durations(activity_duration_seconds: int) -> List[int]:
    """
    Generate list of durations (in seconds) for power curve calculation.
    Optimized for real-world ride distribution and Lambda performance:
    - 0-20min: every 1s (1,200 points) - FTP estimation critical zone
    - 20min-2hr: every 5s (1,200 points) - most common ride lengths
    - 2hr-6hr: every 2min (120 points) - weekend long rides

    Maximum supported duration: 6 hours
    """
    durations = []
    six_hours = 6 * 3600

    twenty_min = 20 * 60
    if activity_duration_seconds >= 1:
        phase1_end = min(activity_duration_seconds, twenty_min)
        durations.extend(range(1, phase1_end + 1))

    two_hours = 2 * 3600
    if activity_duration_seconds > twenty_min:
        phase2_end = min(activity_duration_seconds, two_hours)
        durations.extend(range(twenty_min + 5, phase2_end + 1, 5))

    if activity_duration_seconds > two_hours:
        phase3_end = min(activity_duration_seconds, six_hours)
        durations.extend(range(two_hours + 120, phase3_end + 1, 120))

    return durations


#
# for an agent
#
def get_key_power_curve_durations(power_curve: Dict[int, float]) -> Dict[int, float]:
    """
    Filter power curve data to return only key durations for analysis.
    Reduces token usage when sending data to LLM agents while preserving
    the most important data points for training analysis.
    """
    key_durations = [
        5, 10, 15, 30,
        60, 120, 180, 300,
        480, 600, 720, 900, 1200,
        1800, 2400, 3600, 5400, 7200,
        10800, 14400, 18000, 21600
    ]

    filtered_curve = {}
    for duration in key_durations:
        if duration in power_curve:
            filtered_curve[duration] = power_curve[duration]

    logger.info(f"Filtered power curve from {len(power_curve)} to {len(filtered_curve)} key data points")
    return filtered_curve

#
# Calculates power curve for an activity
#
def calculate_power_curve(user_id: int, activity_id: int) -> Optional[Dict[int, float]]:
    """
    Calculate power curve for an activity and save to database.

    Power curve represents the maximum average power the athlete sustained
    for various durations throughout the activity.
    """
    logger.info(f"calculate_power_curve for activity {activity_id}")
    try:
        activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
        if not activity:
            logger.error(f"Activity {activity_id} not found for user {user_id}")
            return None

        analytics = ActivityAnalytics.query.filter_by(activity_id=activity_id).first()
        if not analytics:
            analytics = ActivityAnalytics(activity_id=activity_id, user_id=user_id)
            db.session.add(analytics)

        six_hours = 6 * 3600
        if activity.moving_time and activity.moving_time > six_hours:
            logger.warning(f"Activity {activity_id} duration ({activity.moving_time}s) exceeds 6hr limit - power curve not supported")
            analytics.power_curve_data = '{}'
            db.session.commit()
            return {}

        streams = get_activity_streams(user_id, activity_id, ['watts', 'time'])
        if not streams or 'watts' not in streams or 'time' not in streams:
            analytics.power_curve_data = '{}'
            db.session.commit()
            logger.warning(f"No power data available for activity {activity_id}")
            return {}

        watts_data = streams['watts']['data']
        time_data = streams['time']['data']
        logger.info(f"Retrieved {len(watts_data)} power data points for activity {activity_id}")

        if not watts_data or len(watts_data) == 0:
            analytics.power_curve_data = '{}'
            db.session.commit()
            logger.warning(f"Empty power data for activity {activity_id}")
            return {}

        logger.info(f"Converting {len(watts_data)} power points to numpy array")
        watts_array = np.array(watts_data, dtype=float)
        logger.info(f"Numpy conversion successful, calculating power curve")

        activity_duration = time_data[-1] if time_data else len(watts_data)
        durations = _generate_power_curve_durations(activity_duration)

        logger.info(f"Calculating power curve for activity {activity_id} with {len(durations)} durations.....")

        power_curve = {}
        cumsum = np.cumsum(np.insert(watts_array, 0, 0))

        for duration in durations:
            if duration > len(watts_array):
                continue
            rolling_avg = (cumsum[duration:] - cumsum[:-duration]) / duration
            max_power = float(np.max(rolling_avg))
            power_curve[duration] = round(max_power, 2)

        analytics.power_curve_data = json.dumps(power_curve)
        db.session.commit()

        logger.info(f"Calculated power curve for activity {activity_id}: {len(power_curve)} data points")
        return power_curve

    except Exception as e:
        logger.error(f"Error calculating power curve for activity {activity_id}: {str(e)}")
        db.session.rollback()
        return None

#
# calculates power in zones for an activity
#
def calculate_power_distribution(user_id: int, activity_id: int) -> Optional[Dict[str, int]]:
    """
    Calculate time spent in each power zone for an activity and save to database.
    """
    logger.info(f"calculate_power_distribution for activity {activity_id}")
    try:
        activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
        if not activity:
            logger.error(f"Activity {activity_id} not found for user {user_id}")
            return None

        analytics = ActivityAnalytics.query.filter_by(activity_id=activity_id).first()
        if not analytics:
            analytics = ActivityAnalytics(activity_id=activity_id, user_id=user_id)
            db.session.add(analytics)

        streams = get_activity_streams(user_id, activity_id, ['watts', 'time'])
        if not streams or 'watts' not in streams:
            analytics.time_in_zones = '{}'
            db.session.commit()
            logger.warning(f"No power data available for activity {activity_id}")
            return {}

        watts_data = streams['watts']['data']
        if not watts_data or len(watts_data) == 0:
            analytics.time_in_zones = '{}'
            db.session.commit()
            logger.warning(f"Empty power data for activity {activity_id}")
            return {}

        zones = get_user_zones(user_id, ZoneType.POWER)
        if not zones:
            logger.warning(f"No power zones configured for user {user_id} - FTP not set")
            analytics.time_in_zones = '{}'
            db.session.commit()
            return {}

        time_in_zones = {zone['name']: 0 for zone in zones}

        for watts in watts_data:
            if watts is None or watts == 0:
                continue
            for zone in zones:
                min_value = zone.get('min_value', 0)
                max_value = zone.get('max_value', float('inf'))
                if min_value <= watts < max_value:
                    time_in_zones[zone['name']] += 1
                    break

        analytics.time_in_zones = json.dumps(time_in_zones)
        db.session.commit()

        logger.info(f"Calculated time in zones for activity {activity_id}: {time_in_zones}")
        return time_in_zones

    except Exception as e:
        logger.error(f"Error calculating time in zones for activity {activity_id}: {str(e)}")
        db.session.rollback()
        return None

def calculate_hr_distribution(user_id: int, activity_id: int) -> Optional[Dict[str, int]]:
    """
    Calculate time spent in each HR zone for an activity.

    Returns {zone_name: seconds_count}.
    Not persisted — computed on demand for the LLM payload.
    """
    logger.info(f"calculate_hr_distribution for activity {activity_id}")
    try:
        streams = get_activity_streams(user_id, activity_id, ['heartrate'])
        if not streams or 'heartrate' not in streams:
            logger.warning(f"No HR data available for activity {activity_id}")
            return {}

        hr_data = streams['heartrate']['data']
        if not hr_data:
            return {}

        zones = get_user_zones(user_id, ZoneType.HEART_RATE)
        if not zones:
            logger.warning(f"No HR zones configured for user {user_id} - max_hr not set")
            return {}

        time_in_zones = {zone['name']: 0 for zone in zones}

        for hr in hr_data:
            if hr is None or hr == 0:
                continue
            for zone in zones:
                min_value = zone.get('min_value', 0)
                max_value = zone.get('max_value', float('inf'))
                if min_value <= hr < max_value:
                    time_in_zones[zone['name']] += 1
                    break

        logger.info(f"Calculated HR time in zones for activity {activity_id}: {time_in_zones}")
        return time_in_zones

    except Exception as e:
        logger.error(f"Error calculating HR time in zones for activity {activity_id}: {str(e)}")
        return {}


#
# main method for calculating activity power metrics
#
def calculate_power_metrics(user_id: int, activity_id: int) -> Dict[str, Optional[Dict]]:
    """
    Orchestrator: calculate power curve and time in zones for an activity.
    """
    logger.info(f"Calculating power metrics for activity {activity_id}")

    power_curve = calculate_power_curve(user_id, activity_id)
    logger.info(f"Power curve calculated for {activity_id}")

    time_in_zones = calculate_power_distribution(user_id, activity_id)
    logger.info(f"Time in zones calculated for {activity_id}")

    return {
        'power_curve': power_curve,
        'time_in_zones': time_in_zones
    }

