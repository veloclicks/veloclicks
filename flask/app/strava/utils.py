from datetime import datetime
import logging
from flask import current_app
from app.models import db, User
from app.common import date_utils
from app.strava import strava_client
from app.strava.constants import ACTIVITY_SUMMARY_FIELDS


def get_access_token(user_id):
    user = User.query.get(user_id)
    token_expiry_epoch = user.token_expiry_epoch
    now = date_utils.get_now_epoch()

    if token_expiry_epoch is not None and now < token_expiry_epoch:
        return user.strava_access_token

    client_id = current_app.config['STRAVA_CLIENT_ID']
    client_secret = current_app.config['STRAVA_CLIENT_SECRET']

    token_data = strava_client.refresh_access_token(user.strava_refresh_token, client_id, client_secret)
    if not token_data:
        logging.error(f"get_access_token() token refresh failed for user {user_id}")
        return None

    user.strava_access_token = token_data['access_token']
    user.strava_refresh_token = token_data['refresh_token']
    user.token_expiry_epoch = token_data['expires_at']
    db.session.commit()

    return user.strava_access_token


def _get_key_activity_attributes(user_id, activity):
    minimal_dict = {key: activity[key] for key in ACTIVITY_SUMMARY_FIELDS if key in activity}

    if 'start_date' in minimal_dict and minimal_dict['start_date']:
        minimal_dict['start_date'] = datetime.fromisoformat(minimal_dict['start_date'].replace('Z', '+00:00'))
    if 'start_date_local' in minimal_dict and minimal_dict['start_date_local']:
        minimal_dict['start_date_local'] = datetime.fromisoformat(minimal_dict['start_date_local'])

    minimal_dict['user_id'] = user_id
    return minimal_dict
