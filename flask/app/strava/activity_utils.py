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




# --------------------------------------------------------------------------------------
# 
#                                     TSS
#
# --------------------------------------------------------------------------------------

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
        # Fetch activity from database
        activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
        if not activity:
            logger.error(f"Activity {activity_id} not found for user {user_id}")
            return None

        # Get user data
        from app.models.user import User
        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return None

        # Determine which method to use
        use_power = False
        use_hr = False

        if calculation_method == 'power':
            use_power = True
        elif calculation_method == 'hr':
            use_hr = True
        else:
            logger.error(f"Invalid calculation_method: {calculation_method}. Use 'power' or 'hr'")
            return None

        # Try power-based TSS
        if use_power:
            if not activity.weighted_average_watts or not user.ftp:
                logger.warning(f"Power-based TSS requested but data missing (NP={activity.weighted_average_watts}, FTP={user.ftp})")
                return None
            else:
                normalized_power = float(activity.weighted_average_watts)
                ftp = float(user.ftp)
                duration_seconds = float(activity.moving_time) if activity.moving_time else 0

                if duration_seconds > 0 and ftp > 0:
                    # Calculate Intensity Factor (IF)
                    intensity_factor = normalized_power / ftp

                    # Calculate power-based TSS
                    # TSS = (sec x NP x IF) / (FTP x 3600) x 100
                    tss = (duration_seconds * normalized_power * intensity_factor) / (ftp * 3600) * 100

                    # Save to database
                    activity.tss = round(tss, 1)
                    db.session.commit()

                    logger.info(f"Calculated power-based TSS for activity {activity_id}: {tss:.1f} (NP={normalized_power}W, FTP={ftp}W, IF={intensity_factor:.3f})")
                    return round(tss, 1)

        # Use heart rate-based TSS
        if use_hr:
            logger.info(f"Using HR-based TSS for activity {activity_id}")

        streams = get_activity_streams(user_id, activity_id, ['heartrate', 'time'])
        if not streams or 'heartrate' not in streams or 'time' not in streams:
            # No heart rate data available - mark as checked with TSS = 0
            activity.tss = 0.0
            db.session.commit()
            logger.warning(f"No heart rate data available for activity {activity_id}")
            return 0.0

        hr_data = streams['heartrate']['data']
        time_data = streams['time']['data']

        # Validate data types
        if not isinstance(hr_data, list):
            logger.error(f"Heart rate data is not a list for activity {activity_id}: type={type(hr_data)}, value={hr_data}")
            activity.tss = 0.0
            db.session.commit()
            return 0.0

        if not hr_data or len(hr_data) == 0:
            # Empty heart rate data - mark as checked with TSS = 0
            activity.tss = 0.0
            db.session.commit()
            logger.warning(f"Empty heart rate data for activity {activity_id}")
            return 0.0

        # Get user profile data for HR calculations
        from app.models.user import User
        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return None

        # Check if user has required HR data
        if not user.max_heart_rate or not user.resting_heart_rate:
            logger.warning(f"User {user_id} missing max_heart_rate or resting_heart_rate")
            activity.tss = 0.0
            db.session.commit()
            return 0.0

        max_hr = float(user.max_heart_rate)
        resting_hr = float(user.resting_heart_rate)

        # Determine exponential factor based on sex (default to male if not set)
        exp_multiplier = 1.92 if user.sex in ['Male', 'M', None] else 1.67

        # Calculate TRIMP for each second
        trimp_total = 0.0
        for hr in hr_data:
            if hr is None or hr <= 0:
                continue

            # Calculate heart rate fraction (reserve)
            hr_fraction = (hr - resting_hr) / (max_hr - resting_hr)

            # Clamp to reasonable bounds (0 to 1.2 to allow for slight overages)
            hr_fraction = max(0.0, min(1.2, hr_fraction))

            # Calculate exponential weighting factor
            exp_factor = np.exp(exp_multiplier * hr_fraction)

            # TRIMP for this second (duration = 1 second)
            trimp_total += 1.0 * hr_fraction * exp_factor

        # Normalize TRIMP to TSS scale
        # A typical hour-long threshold workout (HR at ~85% of max) should yield TSS ~100
        # This normalization factor may need tuning based on real-world data
        # For now, we'll use a conservative scaling
        tss = trimp_total / 60.0  # Rough normalization

        # Save to database
        activity.tss = round(tss, 1)
        db.session.commit()

        logger.info(f"Calculated TSS for activity {activity_id}: {tss:.1f}")
        return round(tss, 1)

    except Exception as e:
        logger.error(f"Error calculating TSS for activity {activity_id}: {str(e)}")
        db.session.rollback()
        return None

# --------------------------------------------------------------------------------------
# 
#                                     POWER
#
# --------------------------------------------------------------------------------------

def _generate_power_curve_durations(activity_duration_seconds: int) -> List[int]:
    """
    Generate list of durations (in seconds) for power curve calculation.
    Optimized for real-world ride distribution and Lambda performance:
    - 0-20min: every 1s (1,200 points) - FTP estimation critical zone
    - 20min-2hr: every 5s (1,200 points) - most common ride lengths
    - 2hr-6hr: every 2min (120 points) - weekend long rides

    Maximum supported duration: 6 hours
    Total for common rides:
      - 1hr: 1,920 points (~4-5s execution)
      - 2hr: 2,400 points (~5-7s execution)
      - 6hr: 2,520 points (~6-8s execution)

    Args:
        activity_duration_seconds: Total duration of the activity in seconds

    Returns:
        List of duration values in seconds
    """
    durations = []
    six_hours = 6 * 3600  # 21,600 seconds

    # 0-20 minutes: every 1 second (1,200 points) - FTP critical zone
    twenty_min = 20 * 60  # 1,200 seconds
    if activity_duration_seconds >= 1:
        phase1_end = min(activity_duration_seconds, twenty_min)
        durations.extend(range(1, phase1_end + 1))

    # 20min-2hr: every 5 seconds (1,200 points) - common ride length
    two_hours = 2 * 3600  # 7,200 seconds
    if activity_duration_seconds > twenty_min:
        phase2_end = min(activity_duration_seconds, two_hours)
        durations.extend(range(twenty_min + 5, phase2_end + 1, 5))

    # 2hr-6hr: every 2 minutes (120 points) - long weekend rides
    if activity_duration_seconds > two_hours:
        phase3_end = min(activity_duration_seconds, six_hours)
        durations.extend(range(two_hours + 120, phase3_end + 1, 120))

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
        empty dict {} if no power data exists,
        or None if calculation failed
    """
    logger.info(f"calculate_power_curve for activity {activity_id}")
    try:
        # Fetch activity from database
        activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
        if not activity:
            logger.error(f"Activity {activity_id} not found for user {user_id}")
            return None

        # Check activity duration - only support up to 6 hours
        six_hours = 6 * 3600
        if activity.moving_time and activity.moving_time > six_hours:
            logger.warning(f"Activity {activity_id} duration ({activity.moving_time}s) exceeds 6hr limit - power curve not supported")
            activity.power_curve_data = '{}'
            db.session.commit()
            return {}

        # Get power stream data
        streams = get_activity_streams(user_id, activity_id, ['watts', 'time'])
        if not streams or 'watts' not in streams or 'time' not in streams:
            # No power data available - mark as checked with empty JSON
            activity.power_curve_data = '{}'
            db.session.commit()
            logger.warning(f"No power data available for activity {activity_id}")
            return {}  # Empty dict means "checked, no data exists"

        watts_data = streams['watts']['data']
        time_data = streams['time']['data']
        logger.info(f"Retrieved {len(watts_data)} power data points for activity {activity_id}")

        if not watts_data or len(watts_data) == 0:
            # Empty power data - mark as checked with empty JSON
            activity.power_curve_data = '{}'
            db.session.commit()
            logger.warning(f"Empty power data for activity {activity_id}")
            return {}

        logger.info(f"Converting {len(watts_data)} power points to numpy array")
        # Convert to numpy arrays for efficient computation
        watts_array = np.array(watts_data, dtype=float)
        logger.info(f"Numpy conversion successful, calculating power curve")

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

#
# Time in Power Zones
#
def calculate_power_distribution(user_id: int, activity_id: int) -> Optional[Dict[str, int]]:
    """
    Calculate time spent in each power zone for an activity and save to database.

    Args:
        user_id: ID of the user
        activity_id: ID of the activity to analyze

    Returns:
        Dictionary mapping zone name to time in seconds,
        empty dict {} if no power data exists,
        or None if calculation failed
    """
    logger.info(f"calculate_power_distribution for activity {activity_id}")
    try:
        # Fetch activity from database
        activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
        if not activity:
            logger.error(f"Activity {activity_id} not found for user {user_id}")
            return None

        # Get power stream data
        streams = get_activity_streams(user_id, activity_id, ['watts', 'time'])
        if not streams or 'watts' not in streams:
            # No power data available - mark as checked with empty JSON
            activity.time_in_zones = '{}'
            db.session.commit()
            logger.warning(f"No power data available for activity {activity_id}")
            return {}

        watts_data = streams['watts']['data']
        if not watts_data or len(watts_data) == 0:
            # Empty power data - mark as checked with empty JSON
            activity.time_in_zones = '{}'
            db.session.commit()
            logger.warning(f"Empty power data for activity {activity_id}")
            return {}

        # Get user's power zones
        zones = get_user_zones(user_id, ZoneType.POWER)
        if not zones:
            logger.warning(f"No power zones configured for user {user_id} - FTP not set")
            # Mark as checked with empty JSON since zones aren't configured
            activity.time_in_zones = '{}'
            db.session.commit()
            return {}

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


#
# Entry point
#
def calculate_power_metrics(user_id: int, activity_id: int) -> Dict[str, Optional[Dict]]:
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
    logger.info(f"Power curve calculated for {activity_id}")
    
    time_in_zones = calculate_power_distribution(user_id, activity_id)
    logger.info(f"Time in zones calculated for {activity_id}")

    return {
        'power_curve': power_curve,
        'time_in_zones': time_in_zones
    }


# --------------------------------------------------------------------------------------
#
#                           FIND SIMILAR ACTIVITIES
#
# --------------------------------------------------------------------------------------
def find_similar_activities(user_id: int, reference_activity_id: int, days_back: int = 28, limit: int = 5) -> Optional[List[Dict]]:
    """
    Find activities similar to a reference activity for comparison.

    Similarity is based on:
    - Same activity type (e.g., Ride, Run)
    - Similar duration (within 25%)
    - Similar intensity (normalized power or average heart rate within 20%)
    - Occurred within specified time window

    Args:
        user_id: ID of the user
        reference_activity_id: Activity to compare against
        days_back: How many days back to search (default 90, max 180)
        limit: Maximum number of similar activities to return (default 5, max 10)

    Returns:
        List of activity summaries with key metrics, or None if error
    """
    print(f"strava.activity_utils.find_similar_activities for activity {reference_activity_id}")
    
    try:
        from datetime import datetime, timedelta

        # Enforce limits to control costs
        days_back = min(days_back, 180)  # Max 6 months
        limit = min(limit, 10)  # Max 10 activities

        # Get reference activity
        reference = Activity.query.filter_by(id=reference_activity_id, user_id=user_id).first()
        if not reference:
            logger.error(f"Reference activity {reference_activity_id} not found")
            return None

        # Calculate time window
        cutoff_date = reference.start_date - timedelta(days=days_back) if reference.start_date else None
        if not cutoff_date:
            logger.error(f"Reference activity {reference_activity_id} has no start_date")
            return None

        # Define similarity criteria
        duration_min = reference.moving_time * 0.75 if reference.moving_time else 0
        duration_max = reference.moving_time * 1.25 if reference.moving_time else float('inf')

        # Query for similar activities
        query = Activity.query.filter(
            Activity.user_id == user_id,
            Activity.id != reference_activity_id,  # Exclude the reference activity itself
            Activity.type == reference.type,
            Activity.start_date >= cutoff_date,
            Activity.start_date < reference.start_date,  # Only past activities
            Activity.moving_time >= duration_min,
            Activity.moving_time <= duration_max
        )

        # Add intensity filter if available
        if reference.weighted_average_watts and reference.weighted_average_watts > 0:
            power_min = reference.weighted_average_watts * 0.8
            power_max = reference.weighted_average_watts * 1.2
            query = query.filter(
                Activity.weighted_average_watts >= power_min,
                Activity.weighted_average_watts <= power_max
            )
        elif reference.average_heartrate and reference.average_heartrate > 0:
            hr_min = reference.average_heartrate * 0.8
            hr_max = reference.average_heartrate * 1.2
            query = query.filter(
                Activity.average_heartrate >= hr_min,
                Activity.average_heartrate <= hr_max
            )

        # Order by date (most recent first) and limit
        similar_activities = query.order_by(Activity.start_date.desc()).limit(limit).all()

        # Format results
        results = []
        for activity in similar_activities:
            results.append({
                'activity_id': activity.id,
                'name': activity.name,
                'type': activity.type,
                'start_date': activity.start_date.isoformat() if activity.start_date else None,
                'distance': activity.distance,
                'moving_time': activity.moving_time,
                'elapsed_time': activity.elapsed_time,
                'average_watts': activity.average_watts,
                'weighted_average_watts': activity.weighted_average_watts,
                'average_heartrate': activity.average_heartrate,
                'max_heartrate': activity.max_heartrate,
                'elevation_gain': activity.total_elevation_gain,
                'tss': activity.tss
            })

        logger.info(f"Found {len(results)} similar activities to {reference_activity_id}")
        return results

    except Exception as e:
        logger.error(f"Error finding similar activities for {reference_activity_id}: {str(e)}")
        return None
