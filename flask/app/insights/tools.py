"""
Insights generation tools.
Core business logic for generating AI-powered activity insights.
"""

import logging
from typing import Dict
from app.models.strava import Activity
from app.models.user import User, MembershipType
from app.agent import tools as agent_tools

logger = logging.getLogger(__name__)

#
# entry point for AI insights for an activity
#
def generate_activity_insights(activity: Activity, is_admin: bool = False, detail_level: str = 'simple') -> Dict:
    """
    Generate AI-powered insights for an activity from a training perspective (premium feature).

    Args:
        activity: Activity model instance
        is_admin: If True, bypass premium check (for CLI admin use only)
        detail_level: 'simple' (quick analysis, default) or 'detailed' (comprehensive with tools)

    Returns:
        dict: Contains 'success' boolean and either 'insights' text or 'error' message
    """
    logger.info(f"Generating insights for activity {activity.id}, user {activity.user_id}, is_admin={is_admin}, detail_level={detail_level}")

    # Check premium membership (unless admin)
    if not is_admin:
        user = User.query.get(activity.user_id)
        if not user:
            logger.error(f"User {activity.user_id} not found")
            return {
                'success': False,
                'error': 'User not found'
            }

        if user.membership_type != MembershipType.PREMIUM_TIER:
            logger.warning(f"User {activity.user_id} attempted to access premium feature without premium membership")
            return {
                'success': False,
                'error': 'Premium membership required for AI-powered insights'
            }

    # Delegate to agent infrastructure
    result = agent_tools.run_agent_workflow(activity, detail_level=detail_level)

    return result
