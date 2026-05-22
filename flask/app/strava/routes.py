from datetime import datetime, timedelta
import os
import logging
from dotenv import load_dotenv

from flask import jsonify, Blueprint, request, current_app, redirect
import jwt

load_dotenv()
from app.models import db, User, Activity
from app.models.user import MembershipType
from app.strava import service

strava_bp = Blueprint('strava', __name__, url_prefix='/strava')

FRONTEND_URL = os.getenv('FRONTEND_URL')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def _get_user_id_from_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, IndexError):
        return None


# -------------------------------------------------------------------------------------------
#                         Strava Authentication and Permission
# -------------------------------------------------------------------------------------------
@strava_bp.route('/strava_auth/', methods=['POST', 'GET'])
@strava_bp.route('/strava_auth', methods=['POST', 'GET'])
@strava_bp.route('/auth/', methods=['POST', 'GET'])
@strava_bp.route('/auth', methods=['POST', 'GET'])
def strava_auth():
    error = request.args.get('error')
    if error:
        return redirect(f"{FRONTEND_URL}/profile/strava-connect?error=access_denied")

    code = request.args.get('code')
    state = request.args.get('state')

    if not code or not state:
        return redirect(f"{FRONTEND_URL}/profile/strava-connect?error=missing_params")

    redirect_uri = f"{request.url_root.rstrip('/')}/strava/strava_auth/"

    try:
        result = service.handle_oauth_callback(int(state), code, redirect_uri)
    except Exception as e:
        logging.error(f'Exception in strava_auth: {e}')
        return redirect(f"{FRONTEND_URL}/profile/strava-connect?error=connection_failed")

    if not result['success']:
        return redirect(f"{FRONTEND_URL}/profile/strava-connect?error={result['error']}")

    return redirect(f"{FRONTEND_URL}/activities?strava_connected=true&activities={result['activity_count']}")


# -------------------------------------------------------------------------------------------
#                         Sync — incremental sync from last_synch_epoch
# -------------------------------------------------------------------------------------------
@strava_bp.route('/synch/')
def strava_synch():
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required", "success": False}), 401

    sync_result = service.perform_incremental_sync(user_id)

    if sync_result is None:
        return jsonify({"error": "Failed to fetch activities", "success": False})

    return jsonify({
        "success": True,
        "new_activities": sync_result['new_count'],
        "total_processed": sync_result['total_processed'],
        "message": f"Sync completed. {sync_result['new_count']} new activities added out of {sync_result['total_processed']} processed.",
    })


# -------------------------------------------------------------------------------------------
#                         Activities — return stored activities with optional year filter
# -------------------------------------------------------------------------------------------
@strava_bp.route('/activities/')
def strava_activities():
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    years_param = request.args.get('years')

    if years_param:
        try:
            selected_years = [int(y.strip()) for y in years_param.split(',')]
            start_date = datetime(min(selected_years), 1, 1)
            end_date = datetime(max(selected_years), 12, 31, 23, 59, 59)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid years parameter"}), 400
    else:
        now = datetime.now()
        start_date = now - timedelta(days=180)
        end_date = now

    activities = service.get_stored_activities(user_id, start_date, end_date)
    return jsonify([a.to_dict() for a in activities])


# -------------------------------------------------------------------------------------------
#                         Bulk historical sync (hardcoded 2022–2024 window)
# -------------------------------------------------------------------------------------------
@strava_bp.route('/strava/all_activities/')
def get_all_activities():
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    after_epoch = 1640995200   # 2022-01-01
    before_epoch = 1704067200  # 2024-01-01

    result = service.sync_activities(user_id, before_epoch, after_epoch)
    if result is not None:
        return jsonify(result)
    return jsonify({"error": "Failed to fetch activities"})


# -------------------------------------------------------------------------------------------
#                         Get activity by id
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>", methods=["GET"])
def activity(id):
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    activity = Activity.query.filter_by(id=id, user_id=user_id).first()
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    return jsonify(activity.to_dict())


# -------------------------------------------------------------------------------------------
#                         Get activity streams by id
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>/streams", methods=["GET"])
def activity_streams(id):
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    stream_types = request.args.get('types', 'latlng').split(',')

    from app.strava.streams import get_activity_streams
    streams_data = get_activity_streams(user_id, id, stream_types)

    if streams_data is None:
        return jsonify({'error': 'Failed to retrieve activity streams or no stream data available'}), 404

    return jsonify(streams_data)


# -------------------------------------------------------------------------------------------
#                         Get optimized elevation profile
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>/elevation-profile", methods=["GET"])
def activity_elevation_profile(id):
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    profile_data = service.get_elevation_profile(user_id, id)

    if profile_data is None:
        return jsonify({'error': 'Failed to retrieve elevation profile data or no stream data available'}), 404

    return jsonify(profile_data)


# -------------------------------------------------------------------------------------------
#                         Update RPE for a single activity
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>/rpe", methods=["PUT"])
def update_activity_rpe(id):
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    activity = Activity.query.filter_by(id=id, user_id=user_id).first()
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
def bulk_update_activities_rpe():
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data or 'updates' not in data:
        return jsonify({'error': 'Missing "updates" field in request body'}), 400

    result = service.update_rpe(user_id, data['updates'])

    if result['success']:
        return jsonify({'message': result['message'], 'count': result['count']}), 200
    return jsonify({'error': result['error'], 'message': result['message']}), 400


# -------------------------------------------------------------------------------------------
#                         Calculate power metrics for activity
# -------------------------------------------------------------------------------------------
@strava_bp.route("/activity/<int:id>/calculate-power-metrics", methods=["POST"])
def calculate_activity_power_metrics_endpoint(id):
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    activity = Activity.query.filter_by(id=id, user_id=user_id).first()
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    from app.analytics.activity_power import calculate_power_metrics

    try:
        result = calculate_power_metrics(user_id, id)
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
def calculate_activity_tss_endpoint(id):
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    activity = Activity.query.filter_by(id=id, user_id=user_id).first()
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    from app.analytics.activity_tss import calculate_tss

    try:
        tss = calculate_tss(user_id, id)

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
def monthly_synch():
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    user = User.query.get(user_id)
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

    result = service.sync_activities_by_month(user_id, year, month_int)

    if result:
        return jsonify({
            "success": True,
            "total_activities": result['total_activities'],
            "total_new": result['total_new'],
            "months_processed": result['months_processed'],
            "month_results": result['month_results'],
            "message": f"Successfully synced {result['total_new']} new activities out of {result['total_activities']} total.",
        })
    return jsonify({"error": "Failed to retrieve activities", "success": False}), 500
