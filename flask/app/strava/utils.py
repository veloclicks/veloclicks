from datetime import datetime, timedelta, date
import time
import json
import math
import os
from dotenv import load_dotenv

from flask import Flask, jsonify, Blueprint, request, current_app
import requests
import logging
from app.models import db, User, Activity
from app.common import date_utils

# Load environment variables
load_dotenv()
bp = Blueprint("strava", __name__)

# Configuration constants
SAMPLE_RATE = 5          # Take every Nth point (1-20 recommended)
MIN_POINTS = 50          # Minimum points to return (don't sample if already small)
MAX_POINTS = 300         # Maximum points to return (further reduce if needed)
COORDINATE_PRECISION = 6  # Decimal places for lat/lng (6 = ~1m accuracy)
DISTANCE_PRECISION = 2    # Decimal places for distance in km
ELEVATION_PRECISION = 1   # Decimal places for elevation in meters


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
DEFAULT_HISTORY_DAYS    = 60
# Strava credentials will be accessed from Flask config (resolved from Parameter Store)
# CLIENT_ID and CLIENT_SECRET accessed via current_app.config in functions



# -------------------------------------------------------------------------------------------
#                             Check access token and refresh if necessary
# -------------------------------------------------------------------------------------------
"""
Gets latest access token for a user
"""
def get_access_token(user_id):    
    # get the user
    user = User.query.get(user_id)
    print(f"get_access_token() for user {user_id}")
    # check their token
    token_expiry_epoch  = user.token_expiry_epoch
    now                 = date_utils.get_now_epoch()

    # If token_expiry_epoch is None, treat token as expired and refresh it
    if token_expiry_epoch is not None and now < token_expiry_epoch:
        print(f"get_access_token() user: {user_id} current token is valid.")
        return user.strava_access_token
    
    else:
        print(f"get_access_token() user: {user_id} getting new token.")
        refresh_token = user.strava_refresh_token
        
        # use the code to get a token via POST to strava
        url = "https://www.strava.com/api/v3/oauth/token"
        client_id = current_app.config['STRAVA_CLIENT_ID']
        client_secret = current_app.config['STRAVA_CLIENT_SECRET']

        # Debug: Print what we're sending to Strava
        print(f"get_access_token() CLIENT_ID: '{client_id}' (type: {type(client_id)})")
        print(f"get_access_token() CLIENT_SECRET: '{client_secret}' (type: {type(client_secret)})")
        print(f"get_access_token() refresh_token: '{refresh_token[:10]}...' (type: {type(refresh_token)})")

        params = {'client_id': client_id, 'client_secret': client_secret, 'refresh_token': refresh_token, 'grant_type': 'refresh_token'}
                
        response = requests.post(url, params)
        jresponse = response.json()

        # Debug logging for token refresh response
        import logging
        logging.debug(f"Token refresh response status: {response.status_code}")
        logging.debug(f"Token refresh response: {jresponse}")

        # Check if refresh was successful
        if 'access_token' not in jresponse:
            logging.error(f"Token refresh failed for user {user_id}. Response: {jresponse}")
            return None

        # uupdate the user
        user.strava_access_token = jresponse['access_token']
        user.strava_refresh_token = jresponse['refresh_token']
        user.token_expiry_epoch = jresponse['expires_at']
        db.session.commit()
        
        print(f"get_access_token() user: {user_id} tokens updated, expiry: {jresponse['expires_at']}")
        return user.strava_access_token
		    


# -------------------------------------------------------------------------------------------
#                                         Get Activities
# -------------------------------------------------------------------------------------------

#
# Extracts key activity attributes from an Activity
#
def _get_key_activity_attributes(user_id, activity):
    keys=['id', 'name', 'start_date_local', 'start_date', 'type', 'distance', 'elapsed_time', 'moving_time', 'average_speed', 'max_speed', 'average_watts', 'max_watts', 'weighted_average_watts', 'average_heartrate', 'max_heartrate', 'suffer_score', 'average_cadence', 'total_elevation_gain', 'elev_low', 'elev_high']
    
    minimal_dict = {key: activity[key] for key in keys if key in activity}

    # Convert date strings to DateTime objects
    if 'start_date' in minimal_dict and minimal_dict['start_date']:
        minimal_dict['start_date'] = datetime.fromisoformat(minimal_dict['start_date'].replace('Z', '+00:00'))

    if 'start_date_local' in minimal_dict and minimal_dict['start_date_local']:
        minimal_dict['start_date_local'] = datetime.fromisoformat(minimal_dict['start_date_local'])

    # also put the user id into the dictionary
    minimal_dict['user_id'] = user_id

    return minimal_dict


#
# this gets activities that are in the db
#
def _retrieve_stored_activities(user_id, start_date=None, end_date=None):
    print(f"_retrieve_stored_activities() for user {user_id} from {start_date} to {end_date}.")

    selected_attributes=['id', 'name', 'start_date_local', 'start_date', 'type', 'distance', 'elapsed_time', 'moving_time', 'average_speed', 'max_speed', 'average_watts', 'max_watts', 'weighted_average_watts', 'average_heartrate', 'max_heartrate', 'suffer_score', 'average_cadence', 'total_elevation_gain', 'elev_low', 'elev_high']

    # Start with base query
    query = db.session.query(Activity).filter(Activity.user_id == user_id)

    # Add date filters if provided
    if start_date:
        query = query.filter(Activity.start_date >= start_date)
    if end_date:
        query = query.filter(Activity.start_date <= end_date)

    # Execute query with ordering
    activities = query.order_by(Activity.start_date.desc()).all()

    print(f"_retrieve_stored_activities() Found {len(activities)} activities in the database for user {user_id}.")

    return activities  
    
        
#
# gets activities between two epochs and stores in database
#    
def retrieve_strava_activities(user_id, before_epoch, after_epoch):
    """
    Gets activities from strave between two periods and stores them in the database.

    Args:
        user_id (_type_): The local id of the user who's strava account is to be accessed to retrieve the activities 
        before_epoch (_type_): The unix epoch indicating the start of the time period within which to retrieve activities
        after_epoch (_type_): The unix epoch indicating the end of the time period within which to retrieve activities

    Returns:
        Dictionary: A Dictionary with 3 keys: 'activities' contains a list of activities found ; 'new-count': the number of activities added to the database; total_processed: the total number of activities found within the before_epoch and end_epoch
    """
    print(f"retrieve_strava_activities for user {user_id} from {before_epoch} to {after_epoch}")
    
    access_token = get_access_token(user_id)
    if not access_token:
        print(f"Failed to get access token for user {user_id}")
        return None

    # Get user's current FTP to capture as snapshot
    user = User.query.get(user_id)
    user_ftp = user.ftp if user else None

    page            = 1
    items_per_page  = 30
    theres_more     = True
    
    # Query parameters (optional: set per your needs)
    url     = 'https://www.strava.com/api/v3/athlete/activities/'
    bearer  = 'Bearer ' + access_token
    headers = {'Authorization': bearer}
    
    minimal_activities = []
    new_activities_count = 0

    # loop through to get all the activities
    while(theres_more):
        params  = { 'after':after_epoch, 'before': before_epoch, 'page':page, 'per_page': items_per_page}
        try:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                activities  = response.json()
                num_items   = len(activities)
                
                print(f"retrieve_strava_activities(). Found {num_items} activities on page {page} for user {user_id}")
                
                # in case we have reached the end
                if (num_items < items_per_page):
                    theres_more = False
                if (num_items > 0):
                    for activity in activities:
                        # strip put the unnecessary detail
                        minimal_attributes = _get_key_activity_attributes(user_id, activity)
                        activity_id = activity['id']
                        
                        # store in placeholder
                        minimal_activities.append(minimal_attributes)
                            
                        # check if activity already in DB and add if not add them
                        if not db.session.query(Activity).filter_by(id=activity_id).first():
                            # Capture FTP snapshot at time of activity sync
                            minimal_attributes['ftp'] = user_ftp
                            activity = Activity(**minimal_attributes)
                            db.session.add(activity)
                            db.session.commit()
                            new_activities_count += 1
                            logging.info(f" - {minimal_attributes['name']} on {minimal_attributes['start_date_local']} ...... written to db.")
                        else:
                            logging.debug(f" - {minimal_attributes['name']} on {minimal_attributes['start_date_local']} ...... already stored.")
                    page = page+1
            else:
                logging.error(f"Error Failed to fetch activities details {response.json() }")
                return None
        except Exception as e:
                logging.error(f"Error Failed to fetch activities details {e}")
                return None
        logging.info("store_activity_history_from_to() sleeping for 2s")
        time.sleep(2)

    print(f"retrieve_strava_activities() completed. Total activities processed: {len(minimal_activities)}, New activities added: {new_activities_count}")
    return {
        'activities': minimal_activities,
        'new_count': new_activities_count,
        'total_processed': len(minimal_activities)
    }


#
# Retrieve Strava activities by month and year - used to iterate through historic data
#
def retrieve_strava_activities_by_month(user_id, year, month=None):
    """
    Retrieves Strava activities for a user by month and year.
    If no month is provided, loops through all months in the year.

    Args:
        user_id (int): The local id of the user whose Strava account is to be accessed
        year (int): The year for which to retrieve activities (e.g., 2024)
        month (int, optional): The month (1-12) for which to retrieve activities.
                               If None, retrieves activities for all months in the year.

    Returns:
        Dictionary: A dictionary containing:
            - 'total_activities': total number of activities retrieved
            - 'total_new': total number of new activities added to database
            - 'months_processed': list of months that were processed
            - 'month_results': dictionary with per-month breakdown
    """
    from calendar import monthrange

    logging.info(f"retrieve_strava_activities_by_month() for user {user_id}, year {year}, month {month}")

    # Determine which months to process
    if month is not None:
        # Single month provided
        months_to_process = [month]
    else:
        # Process all 12 months
        months_to_process = list(range(1, 13))

    # Track overall results
    total_activities = 0
    total_new = 0
    month_results = {}

    # Process each month
    for current_month in months_to_process:
        logging.info(f"Processing month {current_month}/{year}")

        # Calculate epoch for start of month (first day at 00:00:00)
        start_date = datetime(year, current_month, 1)
        after_epoch = int(start_date.timestamp())

        # Calculate epoch for end of month (last day at 23:59:59)
        last_day = monthrange(year, current_month)[1]
        end_date = datetime(year, current_month, last_day, 23, 59, 59)
        before_epoch = int(end_date.timestamp())

        logging.info(f"Month {current_month}: after_epoch={after_epoch}, before_epoch={before_epoch}")

        # Call retrieve_strava_activities for this month
        result = retrieve_strava_activities(user_id, before_epoch, after_epoch)

        if result:
            # Track this month's results
            month_results[current_month] = {
                'activities_count': result['total_processed'],
                'new_count': result['new_count'],
                'start_epoch': after_epoch,
                'end_epoch': before_epoch
            }

            total_activities += result['total_processed']
            total_new += result['new_count']

            logging.info(f"Month {current_month}/{year}: Found {result['total_processed']} activities, {result['new_count']} new")
        else:
            logging.error(f"Failed to retrieve activities for month {current_month}/{year}")
            month_results[current_month] = {
                'error': 'Failed to retrieve activities'
            }

        # Sleep for 10 seconds before processing next month (only if processing multiple months)
        if month is None and current_month != months_to_process[-1]:
            logging.info("Sleeping for 5 seconds before next month...")
            time.sleep(5)

    logging.info(f"retrieve_strava_activities_by_month() completed. Total activities: {total_activities}, New activities: {total_new}")

    return {
        'total_activities': total_activities,
        'total_new': total_new,
        'months_processed': months_to_process,
        'month_results': month_results
    }


#
# Get activity streams from Strava API (lat/lng, altitude, etc.)
#
def get_activity_streams(user_id, activity_id, stream_types=['latlng']):
    """
    Get activity streams from Strava API

    Args:
        user_id: User ID for authentication
        activity_id: Strava activity ID
        stream_types: List of stream types ['latlng', 'altitude', 'time', 'velocity_smooth', 'heartrate', 'cadence', 'watts']

    Returns:
        Dict with stream data or None if failed
    """
    logging.info(f"get_activity_streams() for user {user_id}, activity {activity_id}, types: {stream_types}")

    access_token = get_access_token(user_id)
    if not access_token:
        logging.error("get_activity_streams() Failed to get access token")
        return None

    # Strava API endpoint for activity streams
    url = f'https://www.strava.com/api/v3/activities/{activity_id}/streams'
    bearer = 'Bearer ' + access_token
    headers = {'Authorization': bearer}
    params = {
        'keys': ','.join(stream_types),
        'key_by_type': 'true'
    }

    try:
        logging.info(f"get_activity_streams() calling Strava API: {url}")
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            all_streams_data = response.json()

            # Filter to only return the requested stream types
            filtered_streams = {}
            for stream_type in stream_types:
                if stream_type in all_streams_data:
                    filtered_streams[stream_type] = all_streams_data[stream_type]
                else:
                    logging.warning(f"get_activity_streams() stream type '{stream_type}' not available for activity {activity_id}")

            logging.info(f"get_activity_streams() successfully retrieved {stream_types}")
            return filtered_streams
        elif response.status_code == 404:
            logging.warning(f"get_activity_streams() activity {activity_id} not found or no stream data available")
            return None
        else:
            logging.error(f"get_activity_streams() API error {response.status_code}: {response.text}")
            return None

    except Exception as e:
        logging.error(f"get_activity_streams() Exception: {e}")
        return None


#
# Generate optimized elevation profile data with sampling
#
def get_elevation_profile_data(user_id, activity_id):
    """
    Get optimized elevation profile data with configurable sampling

    Returns preprocessed data with:
    - Distance calculations done on backend
    - Configurable sampling to reduce data points
    - Proper coordinate precision
    """
    logging.info(f"get_elevation_profile_data() for user {user_id}, activity {activity_id}")

    # Get streams from Strava API
    streams_data = get_activity_streams(user_id, activity_id, ['latlng', 'altitude', 'heartrate'])

    if not streams_data or 'latlng' not in streams_data or 'altitude' not in streams_data:
        logging.warning(f"get_elevation_profile_data() insufficient stream data for activity {activity_id}")
        return None

    latlng_data = streams_data['latlng']['data']
    altitude_data = streams_data['altitude']['data']
    heartrate_data = streams_data.get('heartrate', {}).get('data', None)

    # Calculate distances using Haversine formula
    cumulative_distance = 0
    profile_data = []

    for i in range(len(latlng_data)):
        if i > 0:
            # Calculate distance between consecutive points
            lat1, lng1 = latlng_data[i - 1]
            lat2, lng2 = latlng_data[i]

            R = 6371  # Earth's radius in km
            dLat = math.radians(lat2 - lat1)
            dLng = math.radians(lng2 - lng1)
            a = (math.sin(dLat/2) * math.sin(dLat/2) +
                 math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
                 math.sin(dLng/2) * math.sin(dLng/2))
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = R * c

            cumulative_distance += distance

        # Build data point
        data_point = {
            'distance': round(cumulative_distance, DISTANCE_PRECISION),
            'elevation': round(altitude_data[i], ELEVATION_PRECISION),
            'lat': round(latlng_data[i][0], COORDINATE_PRECISION),
            'lng': round(latlng_data[i][1], COORDINATE_PRECISION)
        }

        # Add heart rate if available
        if heartrate_data and i < len(heartrate_data) and heartrate_data[i] is not None:
            data_point['heartrate'] = int(heartrate_data[i])

        profile_data.append(data_point)

    # Apply sampling to reduce data points
    sample_rate = SAMPLE_RATE
    min_points = MIN_POINTS
    max_points = MAX_POINTS

    # Don't sample if already small dataset
    if len(profile_data) <= min_points:
        sampled_data = profile_data
    else:
        # Sample every Nth point
        sampled_data = profile_data[::sample_rate]

        # Further reduce if still too large
        if len(sampled_data) > max_points:
            step = len(sampled_data) // max_points
            sampled_data = sampled_data[::step]

    logging.info(f"get_elevation_profile_data() reduced {len(profile_data)} points to {len(sampled_data)} points")

    return {
        'profile_data': sampled_data,
        'total_points': len(profile_data),
        'sampled_points': len(sampled_data),
        'sample_rate_used': sample_rate if len(profile_data) > min_points else 1
    }


#
# Set RPE (Rate of Perceived Exertion) for one or more activities
#
def set_rpe(user_id, updates):
    """
    Set RPE for one or more activities.
    All-or-nothing transaction: validates all updates before applying any.

    Args:
        user_id: Authenticated user ID
        updates: List of {"activity_id": int, "rpe": int|None} dicts

    Returns:
        {"success": True, "count": int, "message": str} on success
        {"success": False, "error": str, "message": str} on failure
    """
    logging.info(f"set_rpe() for user {user_id} with {len(updates)} updates")

    try:
        # Ensure updates is a list
        if not isinstance(updates, list):
            return {
                "success": False,
                "error": "Invalid format",
                "message": "Updates must be a list"
            }

        if len(updates) == 0:
            return {
                "success": False,
                "error": "No updates provided",
                "message": "Updates list cannot be empty"
            }

        # Step 1: Validate all updates first
        activity_ids = []
        validated_updates = []

        for i, update in enumerate(updates):
            # Check structure
            if not isinstance(update, dict):
                return {
                    "success": False,
                    "error": "Invalid format",
                    "message": f"Update {i} is not a dictionary"
                }

            if 'activity_id' not in update or 'rpe' not in update:
                return {
                    "success": False,
                    "error": "Missing fields",
                    "message": f"Update {i} missing 'activity_id' or 'rpe'"
                }

            activity_id = update['activity_id']
            rpe_value = update['rpe']

            # Validate activity_id
            try:
                activity_id = int(activity_id)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "error": "Invalid activity_id",
                    "message": f"Update {i}: activity_id must be an integer"
                }

            # Validate RPE value
            if rpe_value is not None:
                try:
                    rpe_value = int(rpe_value)
                    if rpe_value < 1 or rpe_value > 10:
                        return {
                            "success": False,
                            "error": "Invalid RPE value",
                            "message": f"Update {i}: RPE must be between 1 and 10 (got {rpe_value})"
                        }
                except (ValueError, TypeError):
                    return {
                        "success": False,
                        "error": "Invalid RPE value",
                        "message": f"Update {i}: RPE must be a valid integer or null"
                    }

            activity_ids.append(activity_id)
            validated_updates.append({"activity_id": activity_id, "rpe": rpe_value})

        # Step 2: Fetch all activities and verify they belong to user
        activities = Activity.query.filter(
            Activity.id.in_(activity_ids),
            Activity.user_id == user_id
        ).all()

        # Check all activities were found
        if len(activities) != len(activity_ids):
            found_ids = {a.id for a in activities}
            missing_ids = set(activity_ids) - found_ids
            return {
                "success": False,
                "error": "Activities not found",
                "message": f"Activities not found or not owned by user: {sorted(missing_ids)}"
            }

        # Create a map of activity_id -> activity object for quick lookup
        activity_map = {a.id: a for a in activities}

        # Step 3: Apply all updates
        for update in validated_updates:
            activity = activity_map[update['activity_id']]
            activity.rpe = update['rpe']

        # Step 4: Commit transaction
        db.session.commit()

        # Step 5: Return success
        logging.info(f"set_rpe() successfully updated {len(validated_updates)} activities")
        return {
            "success": True,
            "count": len(validated_updates),
            "message": f"Updated {len(validated_updates)} {'activity' if len(validated_updates) == 1 else 'activities'}"
        }

    except Exception as e:
        logging.error(f"set_rpe() Exception: {e}")
        db.session.rollback()
        return {
            "success": False,
            "error": "Database error",
            "message": str(e)
        }
