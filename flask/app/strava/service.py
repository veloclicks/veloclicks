from datetime import datetime, timedelta
from calendar import monthrange
import math
import time
import logging
import requests
from flask import current_app
from app.models import db, User, Activity
from app.common import date_utils
from app.strava.constants import (
    SYNCH_WINDOW_DAYS,
    COORDINATE_SAMPLE_RATE,
    MIN_COORDINATE_POINTS,
    MAX_COORDINATE_POINTS,
)
from . import utils as strava_utils

COORDINATE_PRECISION = 6
DISTANCE_PRECISION = 2
ELEVATION_PRECISION = 1


def handle_oauth_callback(user_id, code, redirect_uri):
    """Exchange OAuth code for tokens, persist to user, trigger initial sync."""
    client_id = current_app.config.get('STRAVA_CLIENT_ID')
    client_secret = current_app.config.get('STRAVA_CLIENT_SECRET')

    response = requests.post('https://www.strava.com/oauth/token', data={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
    })

    if not response.ok:
        logging.error(f'Strava token exchange failed: {response.text}')
        return {'success': False, 'error': 'token_exchange'}

    token_data = response.json()

    user = User.query.get(user_id)
    if not user:
        return {'success': False, 'error': 'user_not_found'}

    user.strava_access_token = token_data.get('access_token')
    user.strava_refresh_token = token_data.get('refresh_token')
    user.token_expiry_epoch = token_data.get('expires_at')
    db.session.commit()

    now = datetime.now()
    before_epoch = int(now.timestamp())
    after_epoch = int((now - timedelta(days=30)).timestamp())

    activity_count = 0
    try:
        sync_result = sync_activities(user_id, before_epoch, after_epoch)
        if sync_result:
            activity_count = sync_result.get('new_count', 0)
            user.last_synch_epoch = before_epoch
            db.session.commit()
    except Exception as e:
        logging.error(f'Failed to sync activities for user {user_id}: {e}')

    return {'success': True, 'activity_count': activity_count}


def perform_incremental_sync(user_id):
    """Incremental sync using last_synch_epoch as start. Updates last_synch_epoch on success."""
    now = datetime.now()
    before_epoch = int(now.timestamp())

    user = User.query.get(user_id)
    if not user:
        return None

    default_synch_from = int((now - timedelta(days=SYNCH_WINDOW_DAYS)).timestamp())
    if user.last_synch_epoch:
        after_epoch = max(user.last_synch_epoch, default_synch_from)
    else:
        after_epoch = default_synch_from

    result = sync_activities(user_id, before_epoch, after_epoch)

    if result is not None:
        user.last_synch_epoch = before_epoch
        db.session.commit()

    return result


def sync_activities(user_id, before_epoch, after_epoch):
    """Fetch activities from Strava API for the given window and persist to DB."""
    access_token = strava_utils.get_access_token(user_id)
    if not access_token:
        return None

    user = User.query.get(user_id)
    user_ftp = user.ftp if user else None

    page = 1
    items_per_page = 30
    theres_more = True
    url = 'https://www.strava.com/api/v3/athlete/activities/'
    headers = {'Authorization': f'Bearer {access_token}'}
    minimal_activities = []
    new_activities_count = 0

    while theres_more:
        params = {'after': after_epoch, 'before': before_epoch, 'page': page, 'per_page': items_per_page}
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                activities = response.json()
                num_items = len(activities)
                if num_items < items_per_page:
                    theres_more = False
                for activity in activities:
                    minimal_attrs = strava_utils._get_key_activity_attributes(user_id, activity)
                    activity_id = activity['id']
                    minimal_activities.append(minimal_attrs)
                    if not db.session.query(Activity).filter_by(id=activity_id).first():
                        minimal_attrs['ftp'] = user_ftp
                        db.session.add(Activity(**minimal_attrs))
                        db.session.commit()
                        new_activities_count += 1
                        logging.info(f" - {minimal_attrs['name']} on {minimal_attrs['start_date_local']} written to db.")
                    else:
                        logging.debug(f" - {minimal_attrs['name']} already stored.")
                page += 1
            else:
                logging.error(f"Failed to fetch activities: {response.json()}")
                return None
        except Exception as e:
            logging.error(f"Failed to fetch activities: {e}")
            return None
        time.sleep(2)

    logging.info(f"sync_activities() complete. Processed: {len(minimal_activities)}, New: {new_activities_count}")
    return {
        'activities': minimal_activities,
        'new_count': new_activities_count,
        'total_processed': len(minimal_activities),
    }


def sync_activities_by_month(user_id, year, month=None):
    """Sync activities for a year/month. If month is None, processes all 12 months."""
    months_to_process = [month] if month is not None else list(range(1, 13))
    total_activities = 0
    total_new = 0
    month_results = {}

    for current_month in months_to_process:
        start_date = datetime(year, current_month, 1)
        after_epoch = int(start_date.timestamp())
        last_day = monthrange(year, current_month)[1]
        end_date = datetime(year, current_month, last_day, 23, 59, 59)
        before_epoch = int(end_date.timestamp())

        result = sync_activities(user_id, before_epoch, after_epoch)

        if result:
            month_results[current_month] = {
                'activities_count': result['total_processed'],
                'new_count': result['new_count'],
            }
            total_activities += result['total_processed']
            total_new += result['new_count']
        else:
            month_results[current_month] = {'error': 'Failed to retrieve activities'}

        if month is None and current_month != months_to_process[-1]:
            time.sleep(5)

    return {
        'total_activities': total_activities,
        'total_new': total_new,
        'months_processed': months_to_process,
        'month_results': month_results,
    }


def get_stored_activities(user_id, start_date=None, end_date=None):
    """Query stored activities from DB with optional date filters."""
    query = db.session.query(Activity).filter(Activity.user_id == user_id)
    if start_date:
        query = query.filter(Activity.start_date >= start_date)
    if end_date:
        query = query.filter(Activity.start_date <= end_date)
    return query.order_by(Activity.start_date.desc()).all()


def get_elevation_profile(user_id, activity_id):
    """Get optimized elevation profile data with coordinate sampling."""
    from app.strava.streams import get_activity_streams

    streams_data = get_activity_streams(
        user_id, activity_id, ['latlng', 'altitude', 'heartrate', 'watts', 'grade_smooth']
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

    activities = Activity.query.filter(
        Activity.id.in_(activity_ids),
        Activity.user_id == user_id,
    ).all()

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
