from datetime import datetime
from flask import current_app
from app.models import db, User
from app.common import date_utils
from app.shared_activities.entitlement import utc_naive
from app.strava import strava_client
from app.strava.constants import ACTIVITY_SUMMARY_FIELDS


def get_access_token(user_id):
    """Refresh detail credentials under the same lock as queued imports."""
    user = db.session.get(User, user_id)
    if not user:
        return None
    now = date_utils.get_now_epoch()
    if user.strava_access_token and user.token_expiry_epoch and now < user.token_expiry_epoch:
        return user.strava_access_token

    user = User.query.filter_by(id=user_id).populate_existing().with_for_update().first()
    if not user:
        db.session.rollback()
        return None
    if user.strava_access_token and user.token_expiry_epoch and now < user.token_expiry_epoch:
        db.session.commit()
        return user.strava_access_token
    if not user.strava_refresh_token:
        db.session.rollback()
        return None
    data = strava_client.refresh_access_token(
        user.strava_refresh_token, current_app.config["STRAVA_CLIENT_ID"],
        current_app.config["STRAVA_CLIENT_SECRET"],
    )
    if not data:
        db.session.rollback()
        return None
    user.strava_access_token = data["access_token"]
    user.strava_refresh_token = data["refresh_token"]
    user.token_expiry_epoch = data["expires_at"]
    db.session.commit()
    return user.strava_access_token


def _get_key_activity_attributes(user_id, activity):
    minimal_dict = {key: activity[key] for key in ACTIVITY_SUMMARY_FIELDS if key in activity}

    if 'start_date' in minimal_dict and minimal_dict['start_date']:
        minimal_dict['start_date'] = utc_naive(datetime.fromisoformat(minimal_dict['start_date'].replace('Z', '+00:00')))
    if 'start_date_local' in minimal_dict and minimal_dict['start_date_local']:
        minimal_dict['start_date_local'] = datetime.fromisoformat(minimal_dict['start_date_local']).replace(tzinfo=None)

    minimal_dict['user_id'] = user_id
    return minimal_dict
