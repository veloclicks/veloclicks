from datetime import datetime
import math
import logging
from flask import current_app
from sqlalchemy import tuple_
from app.models import db, User, Activity
from app.shared_activities.entitlement import history_predicate
from app.strava.constants import (
    COORDINATE_SAMPLE_RATE,
    MIN_COORDINATE_POINTS,
    MAX_COORDINATE_POINTS,
)
from app.strava import strava_client, synchronisation
from . import utils as strava_utils

COORDINATE_PRECISION = 6
DISTANCE_PRECISION = 2
ELEVATION_PRECISION = 1


def handle_oauth_callback(user_id, code, redirect_uri):
    """Connect Strava and durably schedule the first 30 days."""
    return synchronisation.connect(user_id, lambda: strava_client.exchange_authorization_code(
        code, current_app.config.get("STRAVA_CLIENT_ID"),
        current_app.config.get("STRAVA_CLIENT_SECRET"), redirect_uri,
    ))


def _stored_activity_query(user_id, start_date, end_date):
    """Scope stored activities to the owner and their current entitlement."""
    query = Activity.query.filter(
        Activity.user_id == user_id,
        Activity.start_date.is_not(None),
        history_predicate(Activity.start_date, User.id, User.membership_type, user_id),
    )
    if start_date:
        query = query.filter(Activity.start_date >= start_date)
    if end_date:
        query = query.filter(Activity.start_date <= end_date)
    return query


def entitled_activity(user_id: int, activity_id: int) -> Activity | None:
    """Return detail access only for an owned, currently entitled ride."""
    return _stored_activity_query(user_id, None, None).filter(Activity.id == activity_id).first()


def get_stored_activities(user_id, start_date=None, end_date=None):
    """Return all stored activities in the date range for existing callers."""
    return _stored_activity_query(user_id, start_date, end_date).order_by(
        Activity.start_date.desc()
    ).all()


def get_stored_activity_page(user_id: int, start_date: datetime, end_date: datetime,
                             limit: int, before: tuple[datetime, int] | None
                             ) -> tuple[list[Activity], bool]:
    """Return a bounded page and whether a continuation exists."""
    query = _stored_activity_query(user_id, start_date, end_date)
    if before is not None:
        # The ID breaks ties when several rides share the same start time.
        query = query.filter(tuple_(Activity.start_date, Activity.id) < before)
    rows = query.order_by(Activity.start_date.desc(), Activity.id.desc()).limit(limit + 1).all()
    return rows[:limit], len(rows) > limit


def get_activity_streams(user_id, activity_id, stream_types=None):
    """Get activity streams from Strava, handling token refresh."""
    if stream_types is None:
        stream_types = ['latlng']
    access_token = strava_utils.get_access_token(user_id)
    if not access_token:
        return None
    return strava_client.fetch_streams(access_token, activity_id, stream_types)


def get_activity_laps(user_id, activity_id):
    """Get lap data from Strava, handling token refresh."""
    access_token = strava_utils.get_access_token(user_id)
    if not access_token:
        return None
    return strava_client.fetch_laps(access_token, activity_id)


def get_elevation_profile(user_id, activity_id):
    """Get optimized elevation profile data with coordinate sampling."""
    access_token = strava_utils.get_access_token(user_id)
    if not access_token:
        return None

    streams_data = strava_client.fetch_streams(
        access_token, activity_id, ['latlng', 'altitude', 'heartrate', 'watts', 'grade_smooth']
    )

    if not streams_data or 'latlng' not in streams_data or 'altitude' not in streams_data:
        return None

    latlng_data = streams_data['latlng']['data']
    altitude_data = streams_data['altitude']['data']
    heartrate_data = streams_data.get('heartrate', {}).get('data')
    power_data = streams_data.get('watts', {}).get('data')
    gradient_data = streams_data.get('grade_smooth', {}).get('data')

    cumulative_distance = 0
    profile_data = []

    for i in range(len(latlng_data)):
        if i > 0:
            lat1, lng1 = latlng_data[i - 1]
            lat2, lng2 = latlng_data[i]
            R = 6371
            dLat = math.radians(lat2 - lat1)
            dLng = math.radians(lng2 - lng1)
            a = (math.sin(dLat / 2) ** 2 +
                 math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
                 math.sin(dLng / 2) ** 2)
            cumulative_distance += R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        data_point = {
            'distance': round(cumulative_distance, DISTANCE_PRECISION),
            'elevation': round(altitude_data[i], ELEVATION_PRECISION),
            'lat': round(latlng_data[i][0], COORDINATE_PRECISION),
            'lng': round(latlng_data[i][1], COORDINATE_PRECISION),
        }
        if heartrate_data and i < len(heartrate_data) and heartrate_data[i] is not None:
            data_point['heartrate'] = int(heartrate_data[i])
        if power_data and i < len(power_data) and power_data[i] is not None:
            data_point['power'] = int(power_data[i])
        if gradient_data and i < len(gradient_data) and gradient_data[i] is not None:
            data_point['gradient'] = round(gradient_data[i], 1)

        profile_data.append(data_point)

    sample_rate = COORDINATE_SAMPLE_RATE
    min_points = MIN_COORDINATE_POINTS
    max_points = MAX_COORDINATE_POINTS

    if len(profile_data) <= min_points:
        sampled_data = profile_data
    else:
        sampled_data = profile_data[::sample_rate]
        if len(sampled_data) > max_points:
            step = len(sampled_data) // max_points
            sampled_data = sampled_data[::step]

    logging.info(f"get_elevation_profile() reduced {len(profile_data)} to {len(sampled_data)} points")
    return {
        'profile_data': sampled_data,
        'total_points': len(profile_data),
        'sampled_points': len(sampled_data),
        'sample_rate_used': sample_rate if len(profile_data) > min_points else 1,
    }


def update_rpe(user_id, updates):
    """Set RPE for one or more activities. All-or-nothing transaction."""
    logging.info(f"update_rpe() for user {user_id} with {len(updates)} updates")

    if not isinstance(updates, list):
        return {"success": False, "error": "Invalid format", "message": "Updates must be a list"}
    if len(updates) == 0:
        return {"success": False, "error": "No updates provided", "message": "Updates list cannot be empty"}

    activity_ids = []
    validated_updates = []

    for i, update in enumerate(updates):
        if not isinstance(update, dict):
            return {"success": False, "error": "Invalid format", "message": f"Update {i} is not a dictionary"}
        if 'activity_id' not in update or 'rpe' not in update:
            return {"success": False, "error": "Missing fields", "message": f"Update {i} missing 'activity_id' or 'rpe'"}

        activity_id = update['activity_id']
        rpe_value = update['rpe']

        try:
            activity_id = int(activity_id)
        except (ValueError, TypeError):
            return {"success": False, "error": "Invalid activity_id", "message": f"Update {i}: activity_id must be an integer"}

        if rpe_value is not None:
            try:
                rpe_value = int(rpe_value)
                if rpe_value < 1 or rpe_value > 10:
                    return {"success": False, "error": "Invalid RPE value", "message": f"Update {i}: RPE must be between 1 and 10"}
            except (ValueError, TypeError):
                return {"success": False, "error": "Invalid RPE value", "message": f"Update {i}: RPE must be a valid integer or null"}

        activity_ids.append(activity_id)
        validated_updates.append({"activity_id": activity_id, "rpe": rpe_value})

    activities = _stored_activity_query(user_id, None, None).filter(Activity.id.in_(activity_ids)).all()

    if len(activities) != len(activity_ids):
        found_ids = {a.id for a in activities}
        missing_ids = set(activity_ids) - found_ids
        return {"success": False, "error": "Activities not found", "message": f"Activities not found or not owned by user: {sorted(missing_ids)}"}

    activity_map = {a.id: a for a in activities}

    try:
        for update in validated_updates:
            activity_map[update['activity_id']].rpe = update['rpe']
        db.session.commit()
        count = len(validated_updates)
        return {"success": True, "count": count, "message": f"Updated {count} {'activity' if count == 1 else 'activities'}"}
    except Exception as e:
        logging.error(f"update_rpe() Exception: {e}")
        db.session.rollback()
        return {"success": False, "error": "Database error", "message": str(e)}
