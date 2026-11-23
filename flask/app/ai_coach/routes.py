"""HTTP endpoints for activity coaching and its analytics summary."""

from flask import g, jsonify, request

from app.ai_coach import ai_coach_bp, service
from app.ai_coach.gateway import get_coaching
from app.common.auth import require_auth


@ai_coach_bp.errorhandler(service.CoachingError)
def _coaching_error(error: service.CoachingError):
    """Preserve the public error response for coaching and summary requests."""
    return jsonify(error=error.message), error.status


@ai_coach_bp.route("/activity/<int:id>", methods=["GET"])
@require_auth
def activity_coaching(id):
    """Return an existing insight or generate one at the requested detail level."""
    return jsonify(service.activity_coaching(g.user_id, id, get_coaching))


@ai_coach_bp.route("/activity/<int:id>/summary", methods=["GET"])
@require_auth
def activity_summary(id):
    """Return the activity analytics payload used for coaching."""
    return jsonify(summary=service.activity_summary(g.user_id, id))
