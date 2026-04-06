"""
AI coaching API endpoints.
"""

import logging
import boto3
import json
import os
from flask import jsonify, request, current_app
from app.ai_coach import ai_coach_bp
from app.models.user import User, MembershipType
from app.models.strava import Activity
from app.models.ai_coach import ActivityInsight
from app.models.db import db
from app.analytics import activity_analyser
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


def _get_lambda_client():
    """Return a boto3 Lambda client — local endpoint if configured, otherwise real AWS."""
    endpoint_url = os.environ.get('COACH_LAMBDA_ENDPOINT')
    kwargs = dict(region_name='eu-west-2')
    if endpoint_url:
        kwargs['endpoint_url'] = endpoint_url
        kwargs['aws_access_key_id'] = 'local'
        kwargs['aws_secret_access_key'] = 'local'
    return boto3.client('lambda', **kwargs)


@ai_coach_bp.route("/activity/<int:id>", methods=["GET"])
def activity_coaching(id):
    """Return persisted AI coaching insight, or generate and persist one via the coach Lambda."""
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

    activity = Activity.query.filter_by(id=id, user_id=user_id).first()
    if not activity:
        return jsonify({"error": "Activity not found"}), 404

    # Return cached insight if already generated
    insight = ActivityInsight.query.filter_by(
        activity_id=id, user_id=user_id, insight_type='ACTIVITY_INSIGHT',
    ).first()
    if insight:
        return jsonify({'coaching': insight.coach_insight}), 200

    # Generate via Lambda
    result = activity_analyser.analyse_activity(user_id, id, mode='llm')
    if not result['success']:
        return jsonify({'error': result['error']}), 500

    llm_payload = result.get('llm_payload')
    if not llm_payload:
        return jsonify({'error': 'Failed to assemble activity data'}), 500

    function_name = os.environ.get('COACH_LAMBDA_NAME', 'veloclicks-coach')
    client = _get_lambda_client()
    response = client.invoke(
        FunctionName=function_name,
        Payload=json.dumps({'llm_payload': llm_payload, 'detail_level': detail_level}),
    )
    coaching_result = json.loads(response['Payload'].read())

    if not coaching_result.get('success'):
        return jsonify({'error': coaching_result.get('error')}), 500

    insight = ActivityInsight(
        activity_id=id,
        user_id=user_id,
        insight_type='ACTIVITY_INSIGHT',
        coach_insight=coaching_result['coaching'],
    )
    db.session.add(insight)
    db.session.commit()

    return jsonify({
        'coaching':    coaching_result['coaching'],
        'token_usage': coaching_result.get('token_usage'),
    }), 200


@ai_coach_bp.route("/activity/<int:id>/summary", methods=["GET"])
def activity_summary(id):
    """Return the JSON activity summary (llm_payload) that would be sent to the coach."""
    user_id = _get_user_id_from_token()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.membership_type != MembershipType.PREMIUM_TIER:
        return jsonify({"error": "Premium membership required"}), 403

    activity = Activity.query.filter_by(id=id, user_id=user_id).first()
    if not activity:
        return jsonify({"error": "Activity not found"}), 404

    result = activity_analyser.analyse_activity(user_id, id, mode='llm')
    if not result['success']:
        return jsonify({'error': result['error']}), 500

    llm_payload = result.get('llm_payload')
    if not llm_payload:
        return jsonify({'error': 'Failed to assemble activity data'}), 500

    return jsonify({'summary': llm_payload}), 200
