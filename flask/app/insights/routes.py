"""
User-facing insights API endpoints.
"""

import logging
from flask import jsonify, request, current_app
from app.insights import insights_bp
from app.insights.tools import generate_activity_insights
from app.models.strava import Activity
from app.models.user import User, MembershipType
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


@insights_bp.route("/activity/<int:id>/ai-insights", methods=["GET"])
def activity_ai_insights(id):
    """
    Generate AI-powered insights for an activity from a training perspective (user-facing endpoint, premium only).

    Query params:
        detail_level: 'simple' (default, quick analysis) or 'detailed' (comprehensive with tool calls)
    """
    # Get detail level from query params
    detail_level = request.args.get('detail_level', 'simple')
    if detail_level not in ['simple', 'detailed']:
        return jsonify({"error": "detail_level must be 'simple' or 'detailed'"}), 400

    logging.info(f"/insights/activity/{id}/ai-insights?detail_level={detail_level}")

    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    # Check premium membership
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.membership_type != MembershipType.PREMIUM_TIER:
        return jsonify({"error": "Premium membership required for AI-powered insights"}), 403

    # Verify activity exists and belongs to user
    activity = Activity.query.filter_by(id=id, user_id=user_id).first()
    if not activity:
        return jsonify({'error': 'Activity not found'}), 404

    # Generate insights
    result = generate_activity_insights(activity, detail_level=detail_level)

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
