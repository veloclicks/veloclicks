import logging
import requests


def exchange_authorization_code(code, client_id, client_secret, redirect_uri):
    """Exchange OAuth authorization code for access/refresh tokens."""
    response = _request('POST', 'https://www.strava.com/oauth/token', data={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
    })
    if not response.ok:
        logging.error("Strava OAuth exchange failed with HTTP %s", response.status_code)
        return None
    return response.json()


class StravaFailure(Exception):
    """Classify Strava failures without retaining sensitive response contents."""

    def __init__(self, reason: str, retry_after: int = 0):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


PAGE_SIZE = 100


def _request(method, url, **kwargs):
    """Bound network waits and classify recoverable upstream failures."""
    try:
        response = requests.request(method, url, timeout=(3, 8), **kwargs)
    except requests.RequestException as error:
        raise StravaFailure("upstream") from error
    if response.status_code == 429:
        raw = response.headers.get("Retry-After", "")
        raise StravaFailure("rate_limit", int(raw) if raw.isdecimal() else 900)
    return response


def _json(response):
    """Treat malformed upstream JSON as a retryable retrieval failure."""
    try:
        return response.json()
    except ValueError as error:
        raise StravaFailure("upstream") from error


def refresh_credentials(refresh_token: str, client_id: str, client_secret: str) -> dict:
    """Refresh credentials or distinguish rejected authorization from outages."""
    response = _request("POST", "https://www.strava.com/api/v3/oauth/token", data={
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    })
    if response.status_code in (401, 403):
        raise StravaFailure("reconnect")
    if response.status_code == 400:
        body = _json(response)
        if isinstance(body, dict) and (body.get("error") == "invalid_grant" or any(
            isinstance(field, dict) and field.get("field") == "refresh_token"
            for field in (body.get("errors") or [])
        )):
            raise StravaFailure("reconnect")
    if not response.ok:
        raise StravaFailure("upstream")
    body = _json(response)
    if not isinstance(body, dict) or not all(body.get(key) for key in ("access_token", "refresh_token", "expires_at")):
        raise StravaFailure("upstream")
    return body


def refresh_access_token(refresh_token, client_id, client_secret):
    """Return refreshed credentials for existing activity detail callers."""
    try:
        return refresh_credentials(refresh_token, client_id, client_secret)
    except StravaFailure:
        return None


def fetch_activity_page(access_token: str, start: int, end: int, page: int) -> list[dict]:
    """Fetch one Strava page with an inclusive lower and exclusive upper bound."""
    params = {"before": end, "page": page, "per_page": PAGE_SIZE}
    # Strava describes 'after' as exclusive. Include the exact first second.
    if start > 0:
        params["after"] = start - 1
    response = _request("GET", "https://www.strava.com/api/v3/athlete/activities",
                        headers={"Authorization": f"Bearer {access_token}"}, params=params)
    if response.status_code in (401, 403):
        raise StravaFailure("reconnect")
    if not response.ok:
        raise StravaFailure("upstream")
    data = _json(response)
    if not isinstance(data, list) or len(data) > PAGE_SIZE or any(not isinstance(row, dict) for row in data):
        raise StravaFailure("upstream")
    return data


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
