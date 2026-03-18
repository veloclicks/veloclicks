import logging
from typing import Dict, List, Optional

from app.models.strava import Activity

logger = logging.getLogger(__name__)


def find_similar_activities(user_id: int, reference_activity_id: int, days_back: int = 28, limit: int = 5) -> Optional[List[Dict]]:
    """
    Find activities similar to a reference activity for comparison.

    Similarity is based on:
    - Same activity type (e.g., Ride, Run)
    - Similar duration (within 25%)
    - Similar intensity (normalized power or average heart rate within 20%)
    - Occurred within specified time window
    """
    logger.info(f"find_similar_activities for activity {reference_activity_id}")

    try:
        from datetime import datetime, timedelta

        days_back = min(days_back, 180)
        limit = min(limit, 10)

        reference = Activity.query.filter_by(id=reference_activity_id, user_id=user_id).first()
        if not reference:
            logger.error(f"Reference activity {reference_activity_id} not found")
            return None

        cutoff_date = reference.start_date - timedelta(days=days_back) if reference.start_date else None
        if not cutoff_date:
            logger.error(f"Reference activity {reference_activity_id} has no start_date")
            return None

        duration_min = reference.moving_time * 0.75 if reference.moving_time else 0
        duration_max = reference.moving_time * 1.25 if reference.moving_time else float('inf')

        query = Activity.query.filter(
            Activity.user_id == user_id,
            Activity.id != reference_activity_id,
            Activity.type == reference.type,
            Activity.start_date >= cutoff_date,
            Activity.start_date < reference.start_date,
            Activity.moving_time >= duration_min,
            Activity.moving_time <= duration_max
        )

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

        similar_activities = query.order_by(Activity.start_date.desc()).limit(limit).all()

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
