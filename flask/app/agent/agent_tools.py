"""
Tool definitions for Anthropic Claude API.
These define what functions the AI agent can call to get activity data.
"""

import logging
from app.strava.activity_utils import calculate_tss, calculate_power_curve, calculate_power_distribution, find_similar_activities, get_key_power_curve_durations

logger = logging.getLogger(__name__)


def execute_tool(tool_name: str, tool_input: dict, user_id: int, activity_id: int):
    """
    Execute a tool call by routing to the appropriate domain function.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Parameters for the tool
        user_id: User ID for authorization
        activity_id: Current activity ID (for context)

    Returns:
        Tool execution result
    """
    try:
        if tool_name == "get_activity_tss":
            tss = calculate_tss(user_id, tool_input['activity_id'], calculation_method='power')
            return {'activity_id': tool_input['activity_id'], 'tss': tss}

        elif tool_name == "get_activity_power_curve":
            power_curve = calculate_power_curve(user_id, tool_input['activity_id'])
            # Filter to key durations to reduce token usage
            if power_curve and len(power_curve) > 0:
                power_curve = get_key_power_curve_durations(power_curve)
            return {'activity_id': tool_input['activity_id'], 'power_curve': power_curve}

        elif tool_name == "get_activity_power_distribution":
            time_in_zones = calculate_power_distribution(user_id, tool_input['activity_id'])
            return {'activity_id': tool_input['activity_id'], 'time_in_zones': time_in_zones}

        elif tool_name == "get_similar_activities":
            days_back = tool_input.get('days_back', 90)
            limit = tool_input.get('limit', 10)
            similar = find_similar_activities(user_id, tool_input['activity_id'], days_back, limit)
            return {
                'reference_activity_id': tool_input['activity_id'],
                'similar_activities': similar,
                'count': len(similar) if similar else 0
            }

        else:
            return {'error': f'Unknown tool: {tool_name}'}

    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}")
        return {'error': str(e)}


def get_tool_definitions():
    """
    Returns the tool definitions for Anthropic's function calling API.
    """
    return [
        {
            "name": "get_activity_tss",
            "description": "Get the Training Stress Score (TSS) for an activity. TSS measures training load - a typical hour-long threshold workout yields TSS ~100. Higher TSS indicates more training stress.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "activity_id": {
                        "type": "integer",
                        "description": "The ID of the activity"
                    }
                },
                "required": ["activity_id"]
            }
        },
        {
            "name": "get_activity_power_curve",
            "description": "Get the power curve for an activity. Returns maximum average power sustained at key durations (5s, 10s, 15s, 30s, 1min, 2min, 3min, 5min, 8min, 10min, 12min, 15min, 20min, 30min, 40min, 1hr, 90min, 2hr, 3hr, 4hr, 5hr, 6hr). Useful for identifying peak efforts, FTP estimation (20min power), and comparing performance across different effort durations.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "activity_id": {
                        "type": "integer",
                        "description": "The ID of the activity"
                    }
                },
                "required": ["activity_id"]
            }
        },
        {
            "name": "get_activity_power_distribution",
            "description": "Get time spent in each power zone for an activity. Shows how much time was spent in different intensity zones (recovery, endurance, tempo, threshold, VO2 max, anaerobic). Useful for understanding workout intensity distribution.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "activity_id": {
                        "type": "integer",
                        "description": "The ID of the activity"
                    }
                },
                "required": ["activity_id"]
            }
        },
        {
            "name": "get_similar_activities",
            "description": "Find activities similar to the current one for comparison. Returns up to 5 activities with similar type, duration (within 25%), and intensity (within 20%) from the past 90 days. Use sparingly - only call if comparison context is essential for the insight.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "activity_id": {
                        "type": "integer",
                        "description": "The ID of the reference activity to compare against"
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to look back (default 28, max 28)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of similar activities to return (default 5, max 10)"
                    }
                },
                "required": ["activity_id"]
            }
        }
    ]
