"""
AI coaching API endpoints.
"""

import logging
from flask import jsonify, request, current_app
from app.ai_coach import ai_coach_bp
from app.models.user import User, MembershipType
from app.analytics import activity_analyser
from app.ai_coach import coach
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


@ai_coach_bp.route("/activity/<int:id>", methods=["GET"])
def activity_coaching(id):
    """
    Generate AI coaching feedback for an activity (premium only).

    Query params:
        detail_level: 'simple' (default) or 'detailed'
    """
    mode = request.args.get('mode', 'llm')
    if mode not in ('structure', 'full', 'llm'):
        return jsonify({"error": "mode must be 'structure', 'full', or 'llm'"}), 400

    detail_level = request.args.get('detail_level', 'simple')
    if detail_level not in ('simple', 'detailed'):
        return jsonify({"error": "detail_level must be 'simple' or 'detailed'"}), 400

    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.membership_type != MembershipType.PREMIUM_TIER:
        return jsonify({"error": "Premium membership required"}), 403

    result = activity_analyser.analyse_activity(user_id, id, mode=mode)
    if not result['success']:
        return jsonify({'error': result['error']}), 500

    if mode == 'structure':
        return jsonify({'identification': result['identification']}), 200

    if mode == 'full':
        return jsonify({
            'identification': result['identification'],
            'metrics':        result['metrics'],
        }), 200

    # mode == 'llm': generate coaching prose
    llm_payload = result.get('llm_payload')
    if not llm_payload:
        return jsonify({'error': 'Failed to assemble activity data'}), 500

    coaching_result = coach.generate_coaching(llm_payload, detail_level=detail_level)
    if not coaching_result['success']:
        return jsonify({'error': coaching_result['error']}), 500

    return jsonify({
        'coaching':    coaching_result['coaching'],
        'token_usage': coaching_result.get('token_usage'),
    }), 200
