import logging
import requests
from typing import Optional

from app.strava.utils import get_access_token


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

def get_activity_laps(user_id: str, activity_id: str) -> Optional[list]:
    """Fetch lap data from Strava activity detail endpoint."""
    access_token = get_access_token(user_id)
    if not access_token:
        return None
    
    url = f'https://www.strava.com/api/v3/activities/{activity_id}/laps'
    response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
    
    if response.status_code == 200:
        return response.json()
    return None