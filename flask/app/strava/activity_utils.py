import json
import logging
import numpy as np
from typing import Dict, List, Optional

from app.models import db
from app.models.strava import Activity
from app.training.zone_utils import get_user_zones
from app.models.training_zone import ZoneType
from app.strava.utils import get_activity_streams

logger = logging.getLogger(__name__)


def _generate_power_curve_durations(activity_duration_seconds: int) -> List[int]:
    """
    Generate list of durations (in seconds) for power curve calculation.
    Uses logarithmic spacing for 0-2hr, 30min intervals for 2-6hr, 1hr intervals beyond 6hr.

    Args:
        activity_duration_seconds: Total duration of the activity in seconds

    Returns:
        List of duration values in seconds
    """
    durations = []

    # High granularity 0-2 hours (25 logarithmically-spaced points)
    two_hours = 2 * 3600
    if activity_duration_seconds >= 60:  # Only if activity is at least 1 minute
        max_duration_phase1 = min(activity_duration_seconds, two_hours)
        phase1_durations = np.logspace(
            np.log10(1),  # Start at 1 second
            np.log10(max_duration_phase1),
            num=25,
            dtype=int
        )
        durations.extend(phase1_durations.tolist())

    # Medium granularity 2-6 hours (every 30 minutes)
    six_hours = 6 * 3600
    if activity_duration_seconds > two_hours:
        max_duration_phase2 = min(activity_duration_seconds, six_hours)
        phase2_start = two_hours + 1800  # 2hr + 30min
        phase2_durations = range(phase2_start, int(max_duration_phase2) + 1, 1800)
        durations.extend(phase2_durations)

    # Low granularity beyond 6 hours (every 1 hour)
    if activity_duration_seconds > six_hours:
        phase3_start = six_hours + 3600  # 6hr + 1hr
        phase3_durations = range(phase3_start, int(activity_duration_seconds) + 1, 3600)
        durations.extend(phase3_durations)

    # Remove duplicates and sort
    durations = sorted(list(set(durations)))

    return durations


def calculate_power_curve(user_id: int, activity_id: int) -> Optional[Dict[int, float]]:
    """
    Calculate power curve for an activity and save to database.

    Power curve represents the maximum average power the athlete sustained
    for various durations throughout the activity.

    Args:
        user_id: ID of the user (for authorization checks)
        activity_id: ID of the activity to analyze

    Returns:
        Dictionary mapping duration (seconds) to max average power (watts),
        or None if calculation failed
    """
    try:
        # Fetch activity from database
        activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
        if not activity:
            logger.error(f"Activity {activity_id} not found for user {user_id}")
            return None

        # Get power stream data
        streams = get_activity_streams(user_id, activity_id, ['watts', 'time'])
        if not streams or 'watts' not in streams or 'time' not in streams:
            logger.warning(f"No power data available for activity {activity_id}")
            return None

        watts_data = streams['watts']['data']
        time_data = streams['time']['data']

        if not watts_data or len(watts_data) == 0:
            logger.warning(f"Empty power data for activity {activity_id}")
            return None

        # Convert to numpy arrays for efficient computation
        watts_array = np.array(watts_data, dtype=float)

        # Calculate activity duration
        activity_duration = time_data[-1] if time_data else len(watts_data)

        # Generate durations to calculate
        durations = _generate_power_curve_durations(activity_duration)

        # Calculate max average power for each duration
        power_curve = {}
        for duration in durations:
            if duration > len(watts_array):
                continue

            # Use convolution for efficient rolling average
            # This calculates the sum of each window of size 'duration'
            window = np.ones(duration)
            rolling_sum = np.convolve(watts_array, window, mode='valid')

            # Convert sum to average
            rolling_avg = rolling_sum / duration

            # Find maximum average power for this duration
            max_power = float(np.max(rolling_avg))
            power_curve[duration] = round(max_power, 2)

        # Save to database
        activity.power_curve_data = json.dumps(power_curve)
        db.session.commit()

        logger.info(f"Calculated power curve for activity {activity_id}: {len(power_curve)} data points")
        return power_curve

    except Exception as e:
        logger.error(f"Error calculating power curve for activity {activity_id}: {str(e)}")
        db.session.rollback()
        return None


def calculate_time_in_zones(user_id: int, activity_id: int) -> Optional[Dict[str, int]]:
    """
    Calculate time spent in each power zone for an activity and save to database.

    Args:
        user_id: ID of the user
        activity_id: ID of the activity to analyze

    Returns:
        Dictionary mapping zone name to time in seconds,
        or None if calculation failed
    """
    try:
        # Fetch activity from database
        activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
        if not activity:
            logger.error(f"Activity {activity_id} not found for user {user_id}")
            return None

        # Get power stream data
        streams = get_activity_streams(user_id, activity_id, ['watts', 'time'])
        if not streams or 'watts' not in streams:
            logger.warning(f"No power data available for activity {activity_id}")
            return None

        watts_data = streams['watts']['data']
        if not watts_data or len(watts_data) == 0:
            logger.warning(f"Empty power data for activity {activity_id}")
            return None

        # Get user's power zones
        zones = get_user_zones(user_id, ZoneType.POWER)
        if not zones:
            logger.warning(f"No power zones configured for user {user_id}")
            return None

        # Initialize time counters for each zone
        time_in_zones = {zone['name']: 0 for zone in zones}

        # Calculate time in each zone
        # Assuming 1 second per data point (typical for Strava streams)
        for watts in watts_data:
            if watts is None or watts == 0:
                continue

            # Find which zone this power value belongs to
            for zone in zones:
                min_value = zone.get('min_value', 0)
                max_value = zone.get('max_value', float('inf'))

                if min_value <= watts < max_value:
                    time_in_zones[zone['name']] += 1
                    break

        # Save to database
        activity.time_in_zones = json.dumps(time_in_zones)
        db.session.commit()

        logger.info(f"Calculated time in zones for activity {activity_id}: {time_in_zones}")
        return time_in_zones

    except Exception as e:
        logger.error(f"Error calculating time in zones for activity {activity_id}: {str(e)}")
        db.session.rollback()
        return None


def calculate_activity_power_metrics(user_id: int, activity_id: int) -> Dict[str, Optional[Dict]]:
    """
    Calculate all power metrics for an activity (power curve and time in zones).
    This is a convenience orchestrator function that calls both calculation functions.

    Args:
        user_id: ID of the user
        activity_id: ID of the activity to analyze

    Returns:
        Dictionary with 'power_curve' and 'time_in_zones' keys containing the results
    """
    logger.info(f"Calculating power metrics for activity {activity_id}")

    power_curve = calculate_power_curve(user_id, activity_id)
    time_in_zones = calculate_time_in_zones(user_id, activity_id)

    return {
        'power_curve': power_curve,
        'time_in_zones': time_in_zones
    }
