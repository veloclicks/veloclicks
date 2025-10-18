from datetime import datetime, timedelta, date
import time
import json
import math
import os
from dotenv import load_dotenv

from flask import Flask, jsonify, Blueprint, request
import requests
import logging
from app.models.user import db, User
from app.models.strava import Activity
from . import date_utils

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
VC_USER_ID              = 1
EARLIEST_EPOCH          = 1577836800 # Wednesday, 1 January 2020 00:00:00
DEFAULT_HISTORY_DAYS    = 60
CLIENT_ID               = os.getenv('STRAVA_CLIENT_ID')
CLIENT_SECRET           = os.getenv('STRAVA_CLIENT_SECRET')



# -------------------------------------------------------------------------------------------
#                             Check access token and refresh if necessary
# -------------------------------------------------------------------------------------------
"""
Gets latest access token for a user
"""
def get_access_token(user_id):    
    # get the user
    user = User.query.get(user_id)
    
    # check their token
    token_expiry_epoch  = user.token_expiry_epoch
    now                 = date_utils.get_now_epoch()
	
    if now < token_expiry_epoch:
        print(f"get_access_token() user: {user_id} current token is valid.")
        return user.strava_access_token
    
    else:
        print(f"get_access_token() user: {user_id} getting new token.")
        refresh_token = user.strava_refresh_token
        
        # use the code to get a token via POST to strava
        url = "https://www.strava.com/api/v3/oauth/token"
        params = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'refresh_token': refresh_token, 'grant_type': 'refresh_token'}
                
        response = requests.post(url, params)
        jresponse = response.json()
        
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
def get_key_activity_attributes(user_id, activity):
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
def retrieve_db_activities(user_id, start_date=None, end_date=None):
    logging.info(f"retrieve_db_activities() for user {user_id} from {start_date} to {end_date}.")

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

    logging.info(f"retrieve_db_activities() Found {len(activities)} activities in the database.")

    return activities
    
    
    '''
    activity_dicts = [
        {attr: getattr(activity, attr) for attr in selected_attributes}
        for activity in activities
    ]
    return activity_dicts
    '''
        
#
# gets activities between two epochs and stores in database
#    
def store_activity_history_from_to(user_id, before_epoch, after_epoch):
    logging.info(f"store_activity_history_from_to for user {user_id} from {before_epoch} to {after_epoch}")
    
    access_token = get_access_token(user_id)
    page            = 1
    items_per_page  = 30
    theres_more     = True
    
    # Query parameters (optional: set per your needs)
    url     = 'https://www.strava.com/api/v3/athlete/activities/'
    bearer  = 'Bearer ' + access_token
    headers = {'Authorization': bearer}
    
    minimal_activities = []
    new_activities_count = 0

    while(theres_more):
        params  = { 'after':after_epoch, 'before': before_epoch, 'page':page, 'per_page': items_per_page}
        try:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                activities  = response.json()
                num_items   = len(activities)
                
                logging.info(f"store_activity_history_from_to(). Found {num_items} activities on page {page}")
                
                # in case we have reached the end
                if (num_items < items_per_page):
                    theres_more = False
                if (num_items > 0):
                    for activity in activities:
                        # strip put the unnecessary detail
                        minimal_attributes = get_key_activity_attributes(VC_USER_ID, activity)
                        activity_id = activity['id']
                        
                        # store in placeholder
                        minimal_activities.append(minimal_attributes)
                            
                        # check if activity already in DB and add if not add them
                        if not db.session.query(Activity).filter_by(id=activity_id).first():
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
        logging.info("store_activity_history_from_to() sleeping for 5s")
        time.sleep(5)

    logging.info(f"store_activity_history_from_to() completed. Total activities processed: {len(minimal_activities)}, New activities added: {new_activities_count}")
    return {
        'activities': minimal_activities,
        'new_count': new_activities_count,
        'total_processed': len(minimal_activities)
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

            logging.info(f"get_activity_streams() successfully retrieved {len(filtered_streams)} of {len(stream_types)} requested stream types")
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
