from datetime import datetime, timedelta, timezone
import os
import logging
from dotenv import load_dotenv

from flask import jsonify, Blueprint, request, g, redirect, current_app
from app.common.auth import require_auth
from itsdangerous import BadData, URLSafeTimedSerializer
from urllib.parse import urlencode

load_dotenv()
from app.models import db, User, Activity, ActivityAnalytics
from app.models.user import MembershipType
from app.strava import service, synchronisation
from app.shared_activities import snapshot
from app.shared_activities.pagination import ActivityCursor, InvalidPage, date_window, limit_value

strava_bp = Blueprint('strava', __name__, url_prefix='/strava')

FRONTEND_URL = os.getenv('FRONTEND_URL')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


# -------------------------------------------------------------------------------------------
#                         Strava Authentication and Permission
# -------------------------------------------------------------------------------------------
@strava_bp.route('/strava_auth/', methods=['POST', 'GET'])
def strava_auth():
    error = request.args.get('error')
    if error:
        return redirect(f"{FRONTEND_URL}/profile/strava-connect?error=access_denied")

    code = request.args.get('code')
    state = request.args.get('state')

    if not code or not state:
        return redirect(f"{FRONTEND_URL}/profile/strava-connect?error=missing_params")
    if "activity:read_all" not in (request.args.get("scope") or "").split(","):
        return redirect(f"{FRONTEND_URL}/profile/strava-connect?error=access_denied")

    redirect_uri = f"{request.url_root.rstrip('/')}/strava/strava_auth/"

    try:
        signer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="strava-oauth-state")
        user_id = signer.loads(state, max_age=600)
        if type(user_id) is not int:
            raise ValueError
        result = service.handle_oauth_callback(user_id, code, redirect_uri)
    except (BadData, ValueError):
        return redirect(f"{FRONTEND_URL}/profile/strava-connect?error=connection_failed")
    except Exception as error:
        db.session.rollback()
        logging.error("Strava OAuth failed (%s)", type(error).__name__)
        return redirect(f"{FRONTEND_URL}/profile/strava-connect?error=connection_failed")

    if not result['success']:
        return redirect(f"{FRONTEND_URL}/profile/strava-connect?error={result['error']}")

    return redirect(f"{FRONTEND_URL}/activities?strava_connected=true&activities={result['activity_count']}")


# -------------------------------------------------------------------------------------------
#                         Sync — incremental sync from last_synch_epoch
# -------------------------------------------------------------------------------------------
@strava_bp.get("/oauth-url")
@require_auth
def oauth_url():
    """Bind the Strava callback to the authenticated application's user."""
    signer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="strava-oauth-state")
    query = urlencode({
        "client_id": current_app.config["STRAVA_CLIENT_ID"],
        "response_type": "code",
        "redirect_uri": f"{request.url_root.rstrip('/')}/strava/strava_auth/",
        "scope": "read,activity:read_all",
        "state": signer.dumps(g.user_id),
    })
    return jsonify(url=f"https://www.strava.com/oauth/authorize?{query}")


@strava_bp.route('/synch/')
@require_auth
def strava_synch():
    """Queue the same manual job for legacy callers."""
    return jsonify(success=True, new_activities=0, message="Sync requested.",
                   **synchronisation.enqueue(g.user_id, "manual")), 202


@strava_bp.post("/sync")
@require_auth
def start_sync():
    """Request a manual or login sync without holding the browser connection."""
    data = request.get_json(silent=True) or {}
    kind = data.get("kind", "manual") if isinstance(data, dict) else None
    if kind not in ("automatic", "manual"):
        return jsonify(error="Invalid sync kind"), 400
    return jsonify(synchronisation.enqueue(g.user_id, kind)), 202


@strava_bp.get("/sync/status")
@require_auth
def sync_status():
    """Describe current progress for all tabs sharing this user's job."""
    return jsonify(synchronisation.status(g.user_id))


@strava_bp.get("/activities/snapshot")
@require_auth
def activity_snapshot():
    """Return the owner's fast snapshot without querying on recent-only hits."""
    def tier():
        user = db.session.get(User, g.user_id)
        return user.membership_type.value if user else None

    try:
        result = snapshot.read(g.user_id, tier)
    except Exception as error:
        logging.warning("Snapshot unavailable (%s)", type(error).__name__)
        result = None
    body, code = (result, 200) if result is not None else ({"error": "Snapshot unavailable"}, 404)
    return jsonify(body), code, {"Cache-Control": "private, no-store"}


# -------------------------------------------------------------------------------------------
#                         Activities — return stored activities with optional year filter
# -------------------------------------------------------------------------------------------
@strava_bp.route('/activities/')
@require_auth
def strava_activities():
    """Return the legacy list or a cursor page when the client requests a limit."""
    limit_param = request.args.get('limit')
    cursor = request.args.get('cursor')
    if limit_param is None and cursor is not None:
        return jsonify(error="Cursor requires a limit"), 400
    years = request.args.get('years') or ""
    try:
        limit = limit_value(limit_param) if limit_param is not None else None
        start, end = date_window(years, datetime.now(timezone.utc).replace(tzinfo=None))
        signer = ActivityCursor(current_app.config["SECRET_KEY"], g.user_id, years)
        before = None
        if cursor is not None:
            window_end, before = signer.decode(cursor)
            if window_end is not None:
                end = window_end
                start = end - timedelta(days=180)
    except InvalidPage as error:
        return jsonify(error=str(error)), 400

    if limit is None:
        activities = service.get_stored_activities(g.user_id, start, end)
        return jsonify([activity.to_dict() for activity in activities])

    activities, has_more = service.get_stored_activity_page(g.user_id, start, end, limit, before)
    next_cursor = None
    if has_more:
        last = activities[-1]
        next_cursor = signer.encode(end, last.start_date, last.id)
    return jsonify(activities=[activity.to_dict() for activity in activities], next_cursor=next_cursor)

# -------------------------------------------------------------------------------------------
#                         Bulk historical sync (hardcoded 2022–2024 window)
# -------------------------------------------------------------------------------------------
@strava_bp.route('/strava/all_activities/')
@require_auth
def get_all_activities():
    bounds = (1640995200, 1735689600)
    return jsonify(success=True, **synchronisation.enqueue(g.user_id, "historical", bounds)), 202


# -------------------------------------------------------------------------------------------
#                         Get activity by id
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>", methods=["GET"])
@require_auth
def activity(id):
    activity = service.entitled_activity(g.user_id, id)
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    data = activity.to_dict()

    analytics = ActivityAnalytics.query.filter_by(activity_id=id, user_id=g.user_id).first()
    if analytics:
        data['power_curve_data'] = analytics.power_curve_data
        data['time_in_zones'] = analytics.time_in_zones

    return jsonify(data)


# -------------------------------------------------------------------------------------------
#                         Get activity streams by id
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>/streams", methods=["GET"])
@require_auth
def activity_streams(id):
    if not service.entitled_activity(g.user_id, id):
        return jsonify(error="Activity not found"), 404
    stream_types = request.args.get('types', 'latlng').split(',')
    streams_data = service.get_activity_streams(g.user_id, id, stream_types)

    if streams_data is None:
        return jsonify({'error': 'Failed to retrieve activity streams or no stream data available'}), 404

    return jsonify(streams_data)


# -------------------------------------------------------------------------------------------
#                         Get optimized elevation profile
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>/elevation-profile", methods=["GET"])
@require_auth
def activity_elevation_profile(id):
    if not service.entitled_activity(g.user_id, id):
        return jsonify(error="Activity not found"), 404
    profile_data = service.get_elevation_profile(g.user_id, id)

    if profile_data is None:
        return jsonify({'error': 'Failed to retrieve elevation profile data or no stream data available'}), 404

    return jsonify(profile_data)


# -------------------------------------------------------------------------------------------
#                         Update RPE for a single activity
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>/rpe", methods=["PUT"])
@require_auth
def update_activity_rpe(id):
    activity = service.entitled_activity(g.user_id, id)
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    data = request.get_json()
    rpe_value = data.get('rpe')

    if rpe_value is not None:
        try:
            rpe_value = int(rpe_value)
            if rpe_value < 1 or rpe_value > 10:
                return jsonify({'error': 'RPE must be between 1 and 10'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'RPE must be a valid integer'}), 400

    activity.rpe = rpe_value
    db.session.commit()

    return jsonify({'message': 'RPE updated successfully', 'activity_id': id, 'rpe': rpe_value})


# -------------------------------------------------------------------------------------------
#                         Bulk update RPE for multiple activities
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activities/rpe", methods=["PUT"])
@require_auth
def bulk_update_activities_rpe():
    data = request.get_json()
    if not data or 'updates' not in data:
        return jsonify({'error': 'Missing "updates" field in request body'}), 400

    result = service.update_rpe(g.user_id, data['updates'])

    if result['success']:
        return jsonify({'message': result['message'], 'count': result['count']}), 200
    return jsonify({'error': result['error'], 'message': result['message']}), 400


# -------------------------------------------------------------------------------------------
#                         Calculate power metrics for activity
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>/calculate-power-metrics", methods=["POST"])
@require_auth
def calculate_activity_power_metrics_endpoint(id):
    activity = service.entitled_activity(g.user_id, id)
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    from app.analytics.activity_power import calculate_power_metrics

    try:
        result = calculate_power_metrics(g.user_id, id)
        power_curve_available = result['power_curve'] is not None and len(result['power_curve']) > 0
        time_in_zones_available = result['time_in_zones'] is not None and len(result['time_in_zones']) > 0

        if not power_curve_available and not time_in_zones_available:
            return jsonify({
                'error': 'Failed to calculate power metrics',
                'message': 'No power data available for this activity or FTP not configured in profile',
            }), 404

        return jsonify({
            'message': 'Power metrics calculated successfully',
            'activity_id': id,
            'power_curve_calculated': power_curve_available,
            'time_in_zones_calculated': time_in_zones_available,
            'power_curve_points': len(result['power_curve']) if result['power_curve'] else 0,
            'time_in_zones': result['time_in_zones'] if time_in_zones_available else {},
        })
    except Exception as e:
        logging.error(f"Error calculating power metrics for activity {id}: {e}")
        return jsonify({'error': 'Failed to calculate power metrics', 'message': str(e)}), 500


# -------------------------------------------------------------------------------------------
#                         Calculate TSS for activity
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>/calculate-tss", methods=["POST"])
@require_auth
def calculate_activity_tss_endpoint(id):
    activity = service.entitled_activity(g.user_id, id)
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    from app.analytics.activity_tss import calculate_tss

    try:
        tss = calculate_tss(g.user_id, id)

        if tss is None:
            return jsonify({
                'error': 'Failed to calculate TSS',
                'message': 'Calculation failed or user missing required heart rate data',
            }), 404

        if tss == 0.0:
            return jsonify({
                'message': 'TSS calculated (no heart rate data available)',
                'activity_id': id,
                'tss': 0.0,
                'note': 'Activity has no heart rate data',
            }), 200

        return jsonify({'message': 'TSS calculated successfully', 'activity_id': id, 'tss': tss})

    except Exception as e:
        logging.error(f"Error calculating TSS for activity {id}: {e}")
        return jsonify({'error': 'Failed to calculate TSS', 'message': str(e)}), 500


# -------------------------------------------------------------------------------------------
#                         Monthly sync (Premium only)
# -------------------------------------------------------------------------------------------
@strava_bp.route("/monthly_synch", methods=["GET"])
@require_auth
def monthly_synch():
    user = User.query.get(g.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.membership_type != MembershipType.PREMIUM_TIER:
        return jsonify({
            "error": "Premium membership required",
            "message": "This feature is only available to premium members. Please upgrade your membership to access historical activity sync.",
        }), 403

    year = request.args.get('year')
    month = request.args.get('month')

    if not year:
        return jsonify({"error": "Year parameter is required"}), 400

    try:
        year = int(year)
        if year < 2000 or year > datetime.now().year:
            return jsonify({"error": f"Invalid year. Must be between 2000 and {datetime.now().year}"}), 400
    except ValueError:
        return jsonify({"error": "Year must be a valid integer"}), 400

    month_int = None
    if month:
        try:
            month_int = int(month)
            if month_int < 1 or month_int > 12:
                return jsonify({"error": "Month must be between 1 and 12"}), 400
        except ValueError:
            return jsonify({"error": "Month must be a valid integer"}), 400

    start = datetime(year, month or 1, 1, tzinfo=timezone.utc)
    if month and month < 12:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    job = synchronisation.enqueue(g.user_id, "historical", (int(start.timestamp()), int(end.timestamp())))
    return jsonify(success=True, **job), 202
