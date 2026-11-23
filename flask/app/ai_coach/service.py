"""Authorize activity coaching and coordinate analytics, generation and persistence."""

from collections.abc import Callable
import json

from app.analytics import activity_analyser
from app.models.ai_coach import ActivityInsight
from app.models.db import db
from app.models.strava import Activity
from app.models.user import MembershipType, User


class CoachingError(Exception):
    """A coaching failure with the status used by the existing HTTP API."""

    def __init__(self, message: str | None, status: int):
        super().__init__(message)
        self.message = message
        self.status = status


def _authorize_activity(user_id: int, activity_id: int) -> None:
    """Require a premium account and an activity owned by that account."""
    user = db.session.get(User, user_id)
    if not user:
        raise CoachingError("User not found", 404)
    if user.membership_type != MembershipType.PREMIUM_TIER:
        raise CoachingError("Premium membership required", 403)
    if not Activity.query.filter_by(id=activity_id, user_id=user_id).first():
        raise CoachingError("Activity not found", 404)


def _activity_payload(user_id: int, activity_id: int) -> dict:
    """Request the established analytics payload used by coaching prompts."""
    result = activity_analyser.analyse_activity(user_id, activity_id, mode="llm")
    if not result["success"]:
        raise CoachingError(result["error"], 500)
    payload = result.get("llm_payload")
    if not payload:
        raise CoachingError("Failed to assemble activity data", 500)
    return payload


def activity_summary(user_id: int, activity_id: int) -> dict:
    """Return the coaching summary for an activity the account may access."""
    _authorize_activity(user_id, activity_id)
    return _activity_payload(user_id, activity_id)


def activity_coaching(user_id: int, activity_id: int,
                      generate: Callable[[dict], dict]) -> dict:
    """Read the stored insight or generate and persist feedback for this activity."""
    _authorize_activity(user_id, activity_id)
    return generate_activity_insight(user_id, activity_id, generate)


def generate_activity_insight(user_id: int, activity_id: int,
                              generate: Callable[[dict], dict]) -> dict:
    """Read or generate an insight for an authorized API request or an admin command."""
    insight_type = "ACTIVITY_INSIGHT"
    # Preserve one cached report per activity, including legacy plain-text reports.
    insight = ActivityInsight.query.filter_by(
        activity_id=activity_id, user_id=user_id, insight_type=insight_type,
    ).first()
    if insight:
        try:
            cached = json.loads(insight.coach_insight)
        except (ValueError, TypeError):
            cached = insight.coach_insight
        return {"coaching": cached}

    result = generate(_activity_payload(user_id, activity_id))
    if not result.get("success"):
        raise CoachingError(result.get("error"), 500)

    db.session.add(ActivityInsight(
        activity_id=activity_id, user_id=user_id,
        insight_type=insight_type, coach_insight=json.dumps(result["coaching"]),
    ))
    db.session.commit()
    return {"coaching": result["coaching"], "token_usage": result.get("token_usage")}
