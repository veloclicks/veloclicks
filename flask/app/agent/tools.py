"""
Tool definitions for Anthropic Claude API.
These define what functions the AI agent can call to get activity data.
"""

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
            "description": "Get the power curve for an activity. Returns maximum average power the athlete sustained for various durations (1 second to 12 hours). Useful for identifying peak efforts and comparing performance.",
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
            "name": "get_activity_basic_info",
            "description": "Get basic information about an activity including name, type, distance, duration, average power, normalized power, and other core metrics.",
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
        },
        {
            "name": "get_user_profile",
            "description": "Get the athlete's training profile including FTP (Functional Threshold Power), max heart rate, resting heart rate, and configured power/heart rate zones. Use this to understand the athlete's fitness level and training zones.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    ]
