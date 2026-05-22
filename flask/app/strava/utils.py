from datetime import datetime
import logging
import requests
from flask import current_app
from app.models import db, User
from app.common import date_utils


def get_access_token(user_id):
    user = User.query.get(user_id)
    token_expiry_epoch = user.token_expiry_epoch
    now = date_utils.get_now_epoch()

    if token_expiry_epoch is not None and now < token_expiry_epoch:
        return user.strava_access_token

    refresh_token = user.strava_refresh_token
    url = "https://www.strava.com/api/v3/oauth/token"
    client_id = current_app.config['STRAVA_CLIENT_ID']
    client_secret = current_app.config['STRAVA_CLIENT_SECRET']

    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }
    response = requests.post(url, params)
    jresponse = response.json()

    logging.debug(f"Token refresh response status: {response.status_code}")

    if 'access_token' not in jresponse:
        logging.error(f"Token refresh failed for user {user_id}. Response: {jresponse}")
        return None

    user.strava_access_token = jresponse['access_token']
    user.strava_refresh_token = jresponse['refresh_token']
    user.token_expiry_epoch = jresponse['expires_at']
    db.session.commit()

    return user.strava_access_token


def _get_key_activity_attributes(user_id, activity):
    keys = [
        'id', 'name', 'start_date_local', 'start_date', 'type', 'distance',
        'elapsed_time', 'moving_time', 'average_speed', 'max_speed',
        'average_watts', 'max_watts', 'weighted_average_watts',
        'average_heartrate', 'max_heartrate', 'suffer_score',
        'average_cadence', 'total_elevation_gain', 'elev_low', 'elev_high',
    ]
    minimal_dict = {key: activity[key] for key in keys if key in activity}

    if 'start_date' in minimal_dict and minimal_dict['start_date']:
        minimal_dict['start_date'] = datetime.fromisoformat(minimal_dict['start_date'].replace('Z', '+00:00'))
    if 'start_date_local' in minimal_dict and minimal_dict['start_date_local']:
        minimal_dict['start_date_local'] = datetime.fromisoformat(minimal_dict['start_date_local'])

    minimal_dict['user_id'] = user_id
    return minimal_dict
