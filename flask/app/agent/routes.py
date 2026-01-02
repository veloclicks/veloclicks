"""
Agent callback API endpoints.
These endpoints expose features for an agent as opposed to being a direct entrypoint for users
"""

import logging
from flask import jsonify, request
from app.agent import agent_bp
from app.models.strava import Activity
from app.strava.activity_utils import calculate_tss, calculate_power_curve, calculate_power_distribution, find_similar_activities
from app.profile.tools import get_profile
from flask_jwt_extended import jwt_required, get_jwt_identity
import json

logger = logging.getLogger(__name__)

#
# gets tss and calculates it if its not there
#
@agent_bp.route('/activity_tss', methods=['GET'])
@jwt_required()
def get_activity_tss():
    """
    Get TSS for an activity.
    Reuses existing calculate_tss function.
    """
    activity_id = request.args.get('activity_id', type=int)
    if not activity_id:
        return jsonify({'error': 'activity_id parameter required'}), 400
    user_id = get_jwt_identity()

    # Fetch activity to get current TSS or calculate if needed
    activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    # If TSS is already calculated, return it
    if activity.tss is not None:
        tss = activity.tss
    else:
        # Calculate TSS using existing function
        tss = calculate_tss(user_id, activity_id, calculation_method='power')
        if tss is None:
            return jsonify({'error': 'Could not calculate TSS'}), 500

    return jsonify({'activity_id': activity_id, 'tss': tss})
#
# gets power curve and calculates it if its not there
#
@agent_bp.route('/activity_zcurve', methods=['GET'])
@jwt_required()
def get_activity_power_curve():
    """
    Get power curve for an activity.
    Reuses existing calculate_power_curve function.
    """
    activity_id = request.args.get('activity_id', type=int)
    if not activity_id:
        return jsonify({'error': 'activity_id parameter required'}), 400
    user_id = get_jwt_identity()

    # Fetch activity to get current power curve or calculate if needed
    activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    # If power curve is already calculated, return it
    if activity.power_curve_data:
        try:
            power_curve = json.loads(activity.power_curve_data)
        except:
            power_curve = None
    else:
        power_curve = None

    # Calculate if not available
    if power_curve is None:
        power_curve = calculate_power_curve(user_id, activity_id)
        if power_curve is None:
            return jsonify({'error': 'Could not calculate power curve'}), 500

    return jsonify({'activity_id': activity_id, 'power_curve': power_curve})

#
# Gets the power distribution for an activity - assuming it has already been calculated
#
@agent_bp.route('/activity_zdist', methods=['GET'])
@jwt_required()
def get_activity_power_distribution():
    """
    Get power zone distribution for an activity.
    Reuses existing calculate_power_distribution function.
    """
    activity_id = request.args.get('activity_id', type=int)
    if not activity_id:
        return jsonify({'error': 'activity_id parameter required'}), 400
    user_id = get_jwt_identity()

    # Fetch activity to get current time in zones or calculate if needed
    activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    # If time in zones is already calculated, return it
    if activity.time_in_zones:
        try:
            time_in_zones = json.loads(activity.time_in_zones)
        except:
            time_in_zones = None
    else:
        time_in_zones = None

    # Calculate if not available
    if time_in_zones is None:
        time_in_zones = calculate_power_distribution(user_id, activity_id)
        if time_in_zones is None:
            return jsonify({'error': 'Could not calculate power distribution'}), 500

    return jsonify({'activity_id': activity_id, 'time_in_zones': time_in_zones})

#
# get basic info about the activity
#
@agent_bp.route('/activity', methods=['GET'])
@jwt_required()
def get_activity_basic_info():
    """
    Get basic activity information.
    """
    activity_id = request.args.get('activity_id', type=int)
    if not activity_id:
        return jsonify({'error': 'activity_id parameter required'}), 400
    user_id = get_jwt_identity()

    activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    return jsonify({
        'activity_id': activity.id,
        'name': activity.name,
        'type': activity.type,
        'start_date': activity.start_date.isoformat() if activity.start_date else None,
        'distance': activity.distance,
        'moving_time': activity.moving_time,
        'elapsed_time': activity.elapsed_time,
        'average_watts': activity.average_watts,
        'weighted_average_watts': activity.weighted_average_watts,
        'average_heartrate': activity.average_heartrate,
        'max_heartrate': activity.max_heartrate,
        'elevation_gain': activity.total_elevation_gain
    })

# find similar activities
@agent_bp.route('/activity_similar', methods=['GET'])
@jwt_required()
def get_similar_activities():
    """
    Get activities similar to a reference activity for comparison.
    """
    activity_id = request.args.get('activity_id', type=int)
    days_back = request.args.get('days_back', type=int, default=90)
    limit = request.args.get('limit', type=int, default=10)

    if not activity_id:
        return jsonify({'error': 'activity_id parameter required'}), 400

    user_id = get_jwt_identity()

    # Use strava domain logic to find similar activities
    similar = find_similar_activities(user_id, activity_id, days_back, limit)

    if similar is None:
        return jsonify({'error': 'Could not find similar activities'}), 500

    return jsonify({
        'reference_activity_id': activity_id,
        'similar_activities': similar,
        'count': len(similar)
    })


@agent_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_user_profile():
    """
    Get user training profile (FTP, heart rate zones, power zones).
    Excludes sensitive personal information.
    """
    user_id = get_jwt_identity()

    profile = get_profile(user_id)
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404

    # Return only training-relevant data, exclude sensitive info
    return jsonify({
        'ftp': profile['ftp'],
        'max_heart_rate': profile['max_heart_rate'],
        'resting_heart_rate': profile['resting_heart_rate'],
        'sex': profile['sex'],
        'zones': profile['zones']
    })
