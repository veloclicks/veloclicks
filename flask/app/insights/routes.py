"""
User-facing insights API endpoints.
"""

import logging
from flask import jsonify, request, current_app
from app.insights import insights_bp
from app.models.strava import Activity
from app.agent.orchestrator import generate_activity_insights
import jwt

logger = logging.getLogger(__name__)


def _get_user_id_from_token():
    """Extract user_id from JWT token in Authorization header."""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None

    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, IndexError):
        return None


@insights_bp.route("/activity/<int:id>", methods=["GET"])
def activity_insights(id):
    """
    Generate AI-powered insights for an activity from a training perspective.
    """
    logging.info(f"/insights/activity/{id}")

    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    # Verify activity exists and belongs to user
    activity = Activity.query.filter_by(id=id, user_id=user_id).first()
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    # Delegate to agent orchestrator
    result = generate_activity_insights(activity)

    if result['success']:
        return jsonify({
            'activity_id': id,
            'insights': result['insights'],
            'status': 'success'
        }), 200
    else:
        return jsonify({
            'error': result['error']
        }), 500
