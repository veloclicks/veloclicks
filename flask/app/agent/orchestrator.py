"""
AI agent orchestration logic.
Handles all LLM interactions and tool calling for generating insights.
"""

import logging
import os
import anthropic
from app.agent.tools import get_tool_definitions
from app.strava.activity_utils import calculate_tss, calculate_power_curve, calculate_power_distribution, find_similar_activities
from app.profile.tools import get_profile
from app.models.strava import Activity

logger = logging.getLogger(__name__)


def _execute_tool(tool_name: str, tool_input: dict, user_id: int, activity_id: int):
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
            return {'activity_id': tool_input['activity_id'], 'power_curve': power_curve}

        elif tool_name == "get_activity_power_distribution":
            time_in_zones = calculate_power_distribution(user_id, tool_input['activity_id'])
            return {'activity_id': tool_input['activity_id'], 'time_in_zones': time_in_zones}

        elif tool_name == "get_activity_basic_info":
            activity = Activity.query.filter_by(id=tool_input['activity_id'], user_id=user_id).first()
            if not activity:
                return {'error': 'Activity not found'}
            return {
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
            }

        elif tool_name == "get_similar_activities":
            days_back = tool_input.get('days_back', 90)
            limit = tool_input.get('limit', 10)
            similar = find_similar_activities(user_id, tool_input['activity_id'], days_back, limit)
            return {
                'reference_activity_id': tool_input['activity_id'],
                'similar_activities': similar,
                'count': len(similar) if similar else 0
            }

        elif tool_name == "get_user_profile":
            profile = get_profile(user_id)
            if not profile:
                return {'error': 'Profile not found'}
            # Return only training-relevant data
            return {
                'ftp': profile['ftp'],
                'max_heart_rate': profile['max_heart_rate'],
                'resting_heart_rate': profile['resting_heart_rate'],
                'sex': profile['sex'],
                'zones': profile['zones']
            }

        else:
            return {'error': f'Unknown tool: {tool_name}'}

    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}")
        return {'error': str(e)}


def generate_activity_insights(activity):
    """
    Generate AI-powered insights for an activity.

    Args:
        activity: Activity model instance

    Returns:
        dict: Contains 'success' boolean and either 'insights' text or 'error' message
    """
    print(f">>>>>> orchestrator getting insights for Activity with id{activity.id}")
    try:
        # Get Anthropic API key from environment
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not set in environment")
            return {
                'success': False,
                'error': 'AI service not configured'
            }

        # Initialize Anthropic client
        client = anthropic.Anthropic(api_key=api_key)

        # Get tool definitions
        tools = get_tool_definitions()

        # Initial prompt to the AI
        initial_message = f"""Analyze this cycling activity from a training perspective and provide insights:

Activity: {activity.name}
Activity Id: {activity.id}
Type: {activity.type}
Date: {activity.start_date}
Distance: {activity.distance}m
Moving Time: {activity.moving_time}s
Average Power: {activity.average_watts}W
Normalized Power: {activity.weighted_average_watts}W

Please provide:
1. Overall assessment of the workout quality and intensity
2. Key performance highlights (peak efforts, sustained power, etc.)
3. Training value and adaptations this workout likely provides
4. Any notable patterns in power distribution

Use the available tools to get detailed metrics like TSS, power curve, and power distribution to support your analysis."""

        messages = [{"role": "user", "content": initial_message}]

        # Tool calling loop with cost tracking
        max_iterations = 10
        max_tokens_total = 50000  # Stop if we exceed 50K tokens (~$1-2 cost) to prevent runaway costs
        iteration = 0
        total_input_tokens = 0
        total_output_tokens = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Anthropic API call iteration {iteration}")

            # Call Anthropic API
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                tools=tools,
                messages=messages
            )

            # Track token usage
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens
            logger.info(f"Stop reason: {response.stop_reason}, Tokens: {response.usage.input_tokens} in + {response.usage.output_tokens} out (Total: {total_input_tokens + total_output_tokens})")

            # Check if we're exceeding token budget
            if total_input_tokens + total_output_tokens > max_tokens_total:
                logger.warning(f"Token limit exceeded: {total_input_tokens + total_output_tokens} > {max_tokens_total}")
                return {
                    'success': False,
                    'error': 'Analysis exceeded token budget - please try with a simpler request'
                }

            # Check if we're done
            if response.stop_reason == "end_turn":
                # Extract final text response
                insight_text = ""
                for block in response.content:
                    if block.type == "text":
                        insight_text += block.text

                logger.info(f"Insight generation complete. Total tokens: {total_input_tokens + total_output_tokens} (Input: {total_input_tokens}, Output: {total_output_tokens})")

                return {
                    'success': True,
                    'insights': insight_text,
                    'token_usage': {
                        'input_tokens': total_input_tokens,
                        'output_tokens': total_output_tokens,
                        'total_tokens': total_input_tokens + total_output_tokens
                    }
                }

            # Handle tool use
            elif response.stop_reason == "tool_use":
                # Add assistant's response to messages
                messages.append({"role": "assistant", "content": response.content})

                # Execute all tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.info(f"Executing tool: {block.name} with input: {block.input}")

                        # Execute the tool
                        result = _execute_tool(block.name, block.input, activity.user_id, activity.id)

                        # Add result to tool_results
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result)
                        })

                # Add tool results to messages
                messages.append({"role": "user", "content": tool_results})

            else:
                logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                break

        # If we exceeded max iterations
        logger.warning(f"Exceeded max iterations ({max_iterations})")
        return {
            'success': False,
            'error': 'Analysis took too many steps'
        }

    except Exception as e:
        logger.error(f"Error generating insights for activity {activity.id}: {str(e)}")
        return {
            'success': False,
            'error': f'Failed to generate insights: {str(e)}'
        }
