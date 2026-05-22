import logging
import time
import requests


def exchange_authorization_code(code, client_id, client_secret, redirect_uri):
    """Exchange OAuth authorization code for access/refresh tokens."""
    response = requests.post('https://www.strava.com/oauth/token', data={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
    })
    if not response.ok:
        logging.error(f"exchange_authorization_code() failed: {response.text}")
        return None
    return response.json()


def refresh_access_token(refresh_token, client_id, client_secret):
    """Refresh an expired access token. Returns token data dict or None."""
    url = "https://www.strava.com/api/v3/oauth/token"
    response = requests.post(url, {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    })
    jresponse = response.json()
    logging.debug(f"refresh_access_token() status: {response.status_code}")
    if 'access_token' not in jresponse:
        logging.error(f"refresh_access_token() failed. Response: {jresponse}")
        return None
    return jresponse


def fetch_activities(access_token, before_epoch, after_epoch):
    """Paginated fetch of activities from Strava. Returns list of raw activity dicts or None on error."""
    url = 'https://www.strava.com/api/v3/athlete/activities/'
    headers = {'Authorization': f'Bearer {access_token}'}
    page = 1
    items_per_page = 30
    all_activities = []

    while True:
        params = {'after': after_epoch, 'before': before_epoch, 'page': page, 'per_page': items_per_page}
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                logging.error(f"fetch_activities() failed: {response.json()}")
                return None
            activities = response.json()
            all_activities.extend(activities)
            if len(activities) < items_per_page:
                break
            page += 1
        except Exception as e:
            logging.error(f"fetch_activities() exception: {e}")
            return None
        time.sleep(2)

    logging.info(f"fetch_activities() retrieved {len(all_activities)} activities")
    return all_activities


def fetch_streams(access_token, activity_id, stream_types):
    """Fetch activity streams. Returns filtered dict keyed by stream type or None."""
    url = f'https://www.strava.com/api/v3/activities/{activity_id}/streams'
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'keys': ','.join(stream_types), 'key_by_type': 'true'}

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            all_streams = response.json()
            filtered = {st: all_streams[st] for st in stream_types if st in all_streams}
            for st in stream_types:
                if st not in all_streams:
                    logging.warning(f"fetch_streams() stream type '{st}' not available for activity {activity_id}")
            return filtered
        elif response.status_code == 404:
            logging.warning(f"fetch_streams() activity {activity_id} not found or no stream data")
            return None
        else:
            logging.error(f"fetch_streams() API error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logging.error(f"fetch_streams() exception: {e}")
        return None


def fetch_laps(access_token, activity_id):
    """Fetch lap data for an activity. Returns list of lap dicts or None."""
    url = f'https://www.strava.com/api/v3/activities/{activity_id}/laps'
    try:
        response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
        if response.status_code == 200:
            return response.json()
        logging.error(f"fetch_laps() API error {response.status_code} for activity {activity_id}")
        return None
    except Exception as e:
        logging.error(f"fetch_laps() exception: {e}")
        return None
