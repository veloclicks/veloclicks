from datetime import datetime, timedelta, date
import time
import json
import os
from dotenv import load_dotenv

from flask import Flask, jsonify, Blueprint, request, current_app, redirect
import requests
import logging
import jwt

# Load environment variables
load_dotenv()
from app.models import db, User, Activity
from app.models.user import MembershipType
from app.common import date_utils
from . import utils as strava_utils

#bp = Blueprint("strava", __name__)
strava_bp = Blueprint('strava', __name__, url_prefix='/strava')

EARLIEST_EPOCH          = 1577836800 # Wednesday, 1 January 2020 00:00:00

'''
    This file only has api endpoint methods, for the grunt work, see check strava_utils.py
'''
logging.basicConfig(
    level=logging.INFO,                           # Minimum log level
    format="%(asctime)s - %(levelname)s - %(message)s",  # Output format
    datefmt="%Y-%m-%d %H:%M:%S"                   # Timestamp format
)


# -------------------------------------------------------------------------------------------
#                                               Constants
# -------------------------------------------------------------------------------------------
# VC_USER_ID              = 1  # DEPRECATED: Should use actual user_id from authentication
EARLIEST_EPOCH          = 1577836800 # Wednesday, 1 January 2020 00:00:00
TWENTY_TWENTY_FOUR_START   = 1704067200
TWENTY_TWENTY_THREE_START  = 1672531200
TWENTY_TWENTY_TWO_START    = 1640995200
TWENTY_TWENTY_ONE_START    = 1609459200
TWENTY_TWENTY_START        = 1577836800
TWENTY_NINETEEN_START      = 1546300800
TWENTY_EIGHTEEN_START      = 1514764800

DEFAULT_HISTORY_DAYS    = 2800
SYNCH_WINDOW_DAYS       = 30
FRONTEND_URL            = os.getenv('FRONTEND_URL')

def get_user_id_from_token():
    """Extract user ID from JWT token in Authorization header"""
    auth_header = request.headers.get('Authorization')

    if not auth_header:
        return None

    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, IndexError):
        return None

@strava_bp.route('/test/', methods=['POST', 'GET'])
def test():
    print('/test api')
    return jsonify({'test': 'hello from /strava/test/ in strava.py!'})

# Debug catch-all route to see what paths we're receiving
@strava_bp.route('/', defaults={'path': ''})
@strava_bp.route('/<path:path>')
def catch_all(path):
    print(f"=== CATCH-ALL DEBUG ===")
    print(f"Received path: '{path}'")
    print(f"Full request path: {request.path}")
    print(f"Request URL: {request.url}")
    print(f"Request args: {request.args}")
    print(f"Request method: {request.method}")
    print(f"Blueprint name: {request.blueprint}")
    print("=====================")
    return jsonify({
        'message': f"Caught path: {path}",
        'full_path': request.path,
        'args': dict(request.args),
        'method': request.method
    })

# -------------------------------------------------------------------------------------------
#                         Strava Authentication and Permission
# -------------------------------------------------------------------------------------------
# 1. react (activities.js) redirects the user to strava to provide authentication
# 2. after slecting the permissions, strava redirects to this url with a short-lived token
# 3. we then send this token back to strava, alongside our secrret key
# 4. strava then returns a longer-life authentication token for that user and a refresh token
# 5. these are saved to the database
#
@strava_bp.route('/strava_auth/', methods=['POST', 'GET'])
@strava_bp.route('/strava_auth', methods=['POST', 'GET'])  # without trailing slash
@strava_bp.route('/auth/', methods=['POST', 'GET'])  # shorter path
@strava_bp.route('/auth', methods=['POST', 'GET'])   # shorter path without slash
def strava_auth():
    print('>>>>>>>> [print] /strava_auth OAuth callback received')
    logging.debug('>>>>>>>> [debug] /strava_auth OAuth callback received')

    # Handle OAuth errors from Strava
    error = request.args.get('error')
    if error:
        logging.error(f'>>>>>>>> Strava OAuth error: {error}')
        frontend_url = FRONTEND_URL
        return redirect(f"{frontend_url}/profile/strava-connect?error=access_denied")

    # Get authorization code and user state
    logging.debug('>>>>>>>> [debug] /strava_auth extracting code and state')
    code = request.args.get('code')
    state = request.args.get('state')  # user_id

    if not code or not state:
        logging.error('>>>>>>>> Missing code or state parameter')
        frontend_url = FRONTEND_URL
        return redirect(f"{frontend_url}/profile/strava-connect?error=missing_params")

    try:
        # Get Strava credentials from config
        client_id = current_app.config.get('STRAVA_CLIENT_ID')
        client_secret = current_app.config.get('STRAVA_CLIENT_SECRET')
        
        logging.debug('>>>>>>>> [debug] /strava_auth client id', client_id)

        # Exchange code for tokens with correct redirect URI
        redirect_uri = f"{request.url_root.rstrip('/')}/strava/strava_auth/"
        response = requests.post('https://www.strava.com/oauth/token', data={
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        })

        if not response.ok:
            logging.error(f'>>>>>>>> Strava token exchange failed: {response.text}')
            frontend_url = FRONTEND_URL
            return redirect(f"{frontend_url}/profile/strava-connect?error=token_exchange")

        token_data = response.json()

        # Debug logging for Strava token response
        logging.debug(f">>>>>>>> Strava token response status: {response.status_code}")
        logging.debug(f">>>>>>>> Strava token response headers: {dict(response.headers)}")
        logging.debug(f">>>>>>>> Strava token response body: {response.text}")
        logging.debug(f">>>>>>>> Parsed token data: {token_data}")

        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_at = token_data.get('expires_at')

        logging.debug(f">>>>>>>> Token details - access_token exists: {bool(access_token)}")
        logging.debug(f">>>>>>>> Token details - refresh_token exists: {bool(refresh_token)}")
        logging.debug(f">>>>>>>> Token details - expires_at: {expires_at} (type: {type(expires_at)})")

        # Store tokens for the user
        user = User.query.get(int(state))
        if not user:
            logging.error(f'>>>>>>>> User with id {state} not found')
            frontend_url = FRONTEND_URL
            return redirect(f"{frontend_url}/profile/strava-connect?error=user_not_found")

        user.strava_access_token = access_token
        user.strava_refresh_token = refresh_token
        user.token_expiry_epoch = expires_at
        db.session.commit()

    except Exception as e:
        logging.error(f'>>>>>>>> Exception in strava_auth: {e}')
        frontend_url = FRONTEND_URL
        return redirect(f"{frontend_url}/profile/strava-connect?error=connection_failed")

    print(f'>>>>>> Strava tokens saved for user {state}, starting activity sync...')

    # Sync the last 30 days activities
    now = datetime.now()
    before_epoch = int(now.timestamp())
    after_epoch = int((now - timedelta(days=30)).timestamp())

    activity_count = 0
    try:
        sync_result = strava_utils.retrieve_strava_activities(int(state), before_epoch, after_epoch)
        activity_count = sync_result.get('new_count', 0) if sync_result else 0
        logging.info(f'Successfully synced {activity_count} new activities for user {state}')
    except Exception as e:
        logging.error(f'Failed to sync activities for user {state}: {e}')
        # Continue anyway - user is connected even if sync failed

    # Redirect to activities page with success message
    frontend_url = FRONTEND_URL
    return redirect(f"{frontend_url}/activities?strava_connected=true&activities={activity_count}")



# -------------------------------------------------------------------------------------------
#         synch - This will return the latest 60 days activities
# -------------------------------------------------------------------------------------------
@strava_bp.route('/synch/')
def strava_synch():
    print(f"/synch strava_synch() - looking for new activities in last {SYNCH_WINDOW_DAYS} days.")

    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required", "success": False}), 401
    
    now               = datetime.now()
    synch_from_epoch  = int((now - timedelta(days=SYNCH_WINDOW_DAYS)).timestamp())
    
    # get user info
    user = User.query.get(user_id)
    if not user:
        return f"No user with id {user_id} found."
    
    after_epoch     = synch_from_epoch
    before_epoch    = int(now.timestamp())
    
    # get the latest activities and save to db
    #minimal_activities = strava_utils.get_activities_from_to(user_id, before_epoch, after_epoch)
    sync_result = strava_utils.retrieve_strava_activities(user_id, before_epoch, after_epoch)

    if sync_result is not None:
        return jsonify({
            "success": True,
            "new_activities": sync_result['new_count'],
            "total_processed": sync_result['total_processed'],
            "message": f"Sync completed. {sync_result['new_count']} new activities added out of {sync_result['total_processed']} processed."
        })
    else:
        return jsonify({ "error": "Failed to fetch activities", "success": False})
    

# -------------------------------------------------------------------------------------------
#         synch - This will return the activities in the database
# -------------------------------------------------------------------------------------------
@strava_bp.route('/activities/')
def strava_activities():
    logging.info('strava_activities()')

    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    # Get years from query parameters (e.g., ?years=2023,2024)
    years_param = request.args.get('years')

    if years_param:
        # Parse years from query parameter
        try:
            selected_years = [int(year.strip()) for year in years_param.split(',')]
            logging.info(f"strava_activities() - filtering for years: {selected_years}")

            # Calculate date range from selected years
            min_year = min(selected_years)
            max_year = max(selected_years)
            start_date = datetime(min_year, 1, 1)
            end_date = datetime(max_year, 12, 31, 23, 59, 59)
        except (ValueError, TypeError) as e:
            logging.error(f"Invalid years parameter: {years_param}, error: {e}")
            return jsonify({"error": "Invalid years parameter"}), 400
    else:
        # Default to last 6 months
        now = datetime.now()
        start_date = now - timedelta(days=180)  # 6 months
        end_date = now
        logging.info(f"strava_activities() - using default 6 month range")

    # get user info
    user = User.query.get(user_id)
    if not user:
        return f"No user with id {user_id} found."

    # get activities from db with date filtering
    logging.info(f"strava_activities() - looking for activities for user {user_id} from {start_date} to {end_date}")
    activities = strava_utils.retrieve_db_activities(user_id, start_date, end_date)

    if activities is not None:
        #return jsonify(activities)
        logging.info('jsonifying activities...')
        return jsonify([a.to_dict() for a in activities])
    else:
        logging.info('strava_activities() no activities found.')
        now                 = datetime.now()
        sixtydaysago_epoch  = int((now - timedelta(days=DEFAULT_HISTORY_DAYS)).timestamp())
        after_epoch         = sixtydaysago_epoch
        before_epoch        = int(now.timestamp())
        activities          = strava_utils.retrieve_strava_activities(user_id, before_epoch, after_epoch)
        return jsonify({ "error": "Failed to fetch activities from db"})


# -------------------------------------------------------------------------------------------
#   Get Activities - This will retreive all activities since 2024 and store them in db
#
#   This is not called from the REACT front end but can be called from a url
#
#   127.0.0.1:5000/strava/all_activities
#
# -------------------------------------------------------------------------------------------
@strava_bp.route('/strava/all_activities/') 
def get_all_activities():
    
    print('/strava/all_activities/')
    
    after_epoch     = TWENTY_TWENTY_TWO_START
    before_epoch    = TWENTY_TWENTY_FOUR_START
    #before_epoch    = int(datetime.now().timestamp())
    
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    
    # get user info
    user = User.query.get(user_id)
    if not user:
        return f"No user with id {user_id} found."
    
    # get the latest activities and save to db
    minimal_activities = strava_utils.retrieve_strava_activities(user_id, before_epoch, after_epoch)

    if minimal_activities is not None:
        return jsonify(minimal_activities)
    else:
        return jsonify({ "error": "Failed to fetch activities"})

# -------------------------------------------------------------------------------------------
#                                   Get activity by id
# -------------------------------------------------------------------------------------------
# http://127.0.0.1:5000/strava/activity/0001
@strava_bp.route("/activity/<int:id>", methods=["GET"])
def activity(id):

    logging.info(f"/strava/activity/ received id: {id}")

    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    # Get activity by ID and user_id for security
    activity = Activity.query.filter_by(id=id, user_id=user_id).first()

    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    return jsonify(activity.to_dict())


# -------------------------------------------------------------------------------------------
#                                   Get activity streams by id
# -------------------------------------------------------------------------------------------
# http://127.0.0.1:5002/strava/activity/123456/streams
@strava_bp.route("/activity/<int:id>/streams", methods=["GET"])
def activity_streams(id):

    logging.info(f"/strava/activity/{id}/streams")

    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    # Get stream types from query parameters, default to latlng
    stream_types = request.args.get('types', 'latlng').split(',')

    # Get streams from Strava API
    streams_data = strava_utils.get_activity_streams(user_id, id, stream_types)

    if streams_data is None:
        return jsonify({'error': 'Failed to retrieve activity streams or no stream data available'}), 404

    return jsonify(streams_data)


# -------------------------------------------------------------------------------------------
#                           Get optimized elevation profile data
# -------------------------------------------------------------------------------------------
# http://127.0.0.1:5002/strava/activity/123456/elevation-profile
@strava_bp.route("/activity/<int:id>/elevation-profile", methods=["GET"])
def activity_elevation_profile(id):

    logging.info(f"/strava/activity/{id}/elevation-profile")

    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    # Get optimized elevation profile data with sampling
    profile_data = strava_utils.get_elevation_profile_data(user_id, id)

    if profile_data is None:
        return jsonify({'error': 'Failed to retrieve elevation profile data or no stream data available'}), 404

    return jsonify(profile_data)


# -------------------------------------------------------------------------------------------
#                   Monthly sync - Retrieve activities by month and year (Premium only)
# -------------------------------------------------------------------------------------------
# http://127.0.0.1:5002/strava/monthly_synch?year=2024&month=5
# http://127.0.0.1:5002/strava/monthly_synch?year=2024
@strava_bp.route("/monthly_synch", methods=["GET"])
def monthly_synch():
    """
    Retrieve Strava activities by month and year.
    Requires PREMIUM_TIER membership.

    Query Parameters:
        year (required): Year to sync activities for
        month (optional): Specific month (1-12). If not provided, syncs all months in the year.
    """
    logging.info("/strava/monthly_synch")

    # Get authenticated user
    user_id = get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    # Get user and check membership type
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Check if user has premium membership
    if user.membership_type != MembershipType.PREMIUM_TIER:
        return jsonify({
            "error": "Premium membership required",
            "message": "This feature is only available to premium members. Please upgrade your membership to access historical activity sync."
        }), 403

    # Get query parameters
    year = request.args.get('year')
    month = request.args.get('month')

    # Validate year parameter (required)
    if not year:
        return jsonify({"error": "Year parameter is required"}), 400

    try:
        year = int(year)
        if year < 2000 or year > datetime.now().year:
            return jsonify({"error": f"Invalid year. Must be between 2000 and {datetime.now().year}"}), 400
    except ValueError:
        return jsonify({"error": "Year must be a valid integer"}), 400

    # Validate month parameter (optional)
    month_int = None
    if month:
        try:
            month_int = int(month)
            if month_int < 1 or month_int > 12:
                return jsonify({"error": "Month must be between 1 and 12"}), 400
        except ValueError:
            return jsonify({"error": "Month must be a valid integer"}), 400

    # Call the strava_utils function to retrieve activities
    logging.info(f"Syncing activities for user {user_id}, year {year}, month {month_int}")
    result = strava_utils.retrieve_strava_activities_by_month(user_id, year, month_int)

    if result:
        return jsonify({
            "success": True,
            "total_activities": result['total_activities'],
            "total_new": result['total_new'],
            "months_processed": result['months_processed'],
            "month_results": result['month_results'],
            "message": f"Successfully synced {result['total_new']} new activities out of {result['total_activities']} total."
        })
    else:
        return jsonify({
            "error": "Failed to retrieve activities",
            "success": False
        }), 500
