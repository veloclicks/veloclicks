"""
AI agent orchestration logic.
Handles all LLM interactions and tool calling for generating insights.
"""

import json
import logging
import os
from anthropic import Anthropic
from app.agent import agent_tools
from app.profile import tools as profile_tools

logger = logging.getLogger(__name__)

# Prompt templates for different detail levels
SIMPLE_ACTIVITY_PROMPT = """Provide a brief analysis of this cycling activity based on the metrics:

Activity: {name}
Activity Id: {id}
Type: {type}
Date: {date}
Distance: {distance}m
Moving Time: {moving_time}s
Elapsed Time: {elapsed_time}s
Average Power: {average_watts}W
Normalized Power: {weighted_average_watts}W
Average Heart Rate: {average_heartrate} bpm
Max Heart Rate: {max_heartrate} bpm
Elevation Gain: {elevation_gain}m

Athlete Profile:
FTP: {ftp}W
Max Heart Rate: {profile_max_hr} bpm
Resting Heart Rate: {resting_hr} bpm
Sex: {sex}
Power Zones: {power_zones}
Heart Rate Zones: {hr_zones}

Provide a concise 2-3 paragraph analysis covering:
1. Overall workout quality and intensity
2. Key highlights based on the power and duration data compared to users ftp and heart rate
3. Likely training benefit

Keep it brief and actionable."""

DETAILED_ACTIVITY_PROMPT = """Analyze this cycling activity from a training perspective and provide comprehensive insights:

Activity: {name}
Activity Id: {id}
Type: {type}
Date: {date}
Distance: {distance}m
Moving Time: {moving_time}s
Elapsed Time: {elapsed_time}s
Average Power: {average_watts}W
Normalized Power: {weighted_average_watts}W
Average Heart Rate: {average_heartrate} bpm
Max Heart Rate: {max_heartrate} bpm
Elevation Gain: {elevation_gain}m

Athlete Profile:
FTP: {ftp}W
Max Heart Rate: {profile_max_hr} bpm
Resting Heart Rate: {resting_hr} bpm
Sex: {sex}
Power Zones: {power_zones}
Heart Rate Zones: {hr_zones}

Please provide:
1. Overall assessment of the workout quality and intensity
2. Key performance highlights (peak efforts, sustained power, etc.)
3. Training value and adaptations this workout likely provides
4. Any notable patterns in power distribution
5. Comparison to similar recent activities (if relevant)

Use the available tools to get detailed metrics like TSS, power curve, power distribution, and similar activities to support your analysis."""


def _get_llm_client():
    """
    Get LLM client based on LLM_PROVIDER environment variable.

    Returns:
        tuple: (client, model_name, provider)

    Raises:
        ValueError: If required API keys are not set or provider is unsupported
    """
    from flask import current_app

    provider = os.getenv('LLM_PROVIDER', 'anthropic').lower()
    model_name = os.getenv('LLM_MODEL', 'claude-sonnet-4-20250514')

    if provider == 'anthropic':
        # Try to get from Flask config first (which resolves SSM), fall back to env var
        api_key = current_app.config.get('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not set in environment")
            raise ValueError("AI service not configured - ANTHROPIC_API_KEY required")
        client = Anthropic(api_key=api_key)
        return client, model_name, provider
    elif provider == 'qwen':
        # Placeholder for Qwen support - to be implemented
        raise ValueError("Qwen provider not yet implemented")
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")



def run_agent_workflow(activity, detail_level='simple'):
    """
    Execute the LLM agent workflow with tool calling loop for activity analysis.

    Args:
        activity: Activity model instance
        detail_level: 'simple' (quick analysis, no tools) or 'detailed' (comprehensive with tools)

    Returns:
        dict: Contains 'success' boolean and either 'insights' text or 'error' message
    """
    print(f">>>>>> orchestrator running agent workflow for Activity {activity.id} with detail_level={detail_level}")
    try:
        # Get LLM client
        client, model_name, provider = _get_llm_client()
        logger.info(f"Using LLM provider: {provider}, model: {model_name}")

        # Get user profile data to include in prompt (used by both simple and detailed)
        profile = profile_tools.get_profile(activity.user_id)
        if not profile:
            logger.error(f"Profile not found for user {activity.user_id}")
            return {
                'success': False,
                'error': 'User profile not found'
            }

        # Format zones for display (filter by type since zones is a list)
        all_zones = profile['zones']
        power_zones = [z for z in all_zones if z.get('type') == 'power']
        hr_zones = [z for z in all_zones if z.get('type') == 'heart_rate']

        power_zones_str = "\n".join([f"  {z['display_name']}: {z['min_value']}-{z['max_value']}W"
                                     for z in power_zones])
        hr_zones_str = "\n".join([f"  {z['display_name']}: {z['min_value']}-{z['max_value']} bpm"
                                  for z in hr_zones])

        # Prepare context data for prompt formatting (same for both detail levels)
        prompt_context = {
            'name': activity.name,
            'id': activity.id,
            'type': activity.type,
            'date': activity.start_date,
            'distance': activity.distance,
            'moving_time': activity.moving_time,
            'elapsed_time': activity.elapsed_time,
            'average_watts': activity.average_watts,
            'weighted_average_watts': activity.weighted_average_watts,
            'average_heartrate': activity.average_heartrate or 'N/A',
            'max_heartrate': activity.max_heartrate or 'N/A',
            'elevation_gain': activity.total_elevation_gain or 0,
            'ftp': profile['ftp'] or 'Not set',
            'profile_max_hr': profile['max_heart_rate'] or 'Not set',
            'resting_hr': profile['resting_heart_rate'] or 'Not set',
            'sex': profile['sex'] or 'Not specified',
            'power_zones': power_zones_str if power_zones_str else 'Not configured',
            'hr_zones': hr_zones_str if hr_zones_str else 'Not configured'
        }

        # Configure based on detail level
        if detail_level == 'simple':
            # Simple: No tools, brief analysis
            tools = []
            initial_message = SIMPLE_ACTIVITY_PROMPT.format(**prompt_context)
            max_tokens = 800
            max_iterations = 1  # No tool calling for simple
            max_tokens_total = 1000
        else:
            # Detailed: Full tool access, comprehensive analysis
            tools = agent_tools.get_tool_definitions()
            initial_message = DETAILED_ACTIVITY_PROMPT.format(**prompt_context)
            max_tokens = 4096
            max_iterations = 10
            max_tokens_total = 50000

        messages = [{"role": "user", "content": initial_message}]

        # Tool calling loop with cost tracking
        iteration = 0
        total_input_tokens = 0
        total_output_tokens = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"LLM API call iteration {iteration}")

            # Call LLM API
            if provider == 'anthropic':
                # Build request parameters for Anthropic SDK
                request_params = {
                    "model": model_name,
                    "max_tokens": max_tokens,
                    "messages": messages
                }
                # Only include tools if we have any
                if tools:
                    request_params["tools"] = tools

                response = client.messages.create(**request_params)

                # Track token usage
                total_input_tokens += response.usage.input_tokens
                total_output_tokens += response.usage.output_tokens
                finish_reason = response.stop_reason
                logger.info(f"Finish reason: {finish_reason}, Tokens: {response.usage.input_tokens} in + {response.usage.output_tokens} out (Total: {total_input_tokens + total_output_tokens})")
            else:
                # Placeholder for other providers
                raise ValueError(f"Unsupported provider: {provider}")

            # Check if we're exceeding token budget
            if total_input_tokens + total_output_tokens > max_tokens_total:
                logger.warning(f"Token limit exceeded: {total_input_tokens + total_output_tokens} > {max_tokens_total}")
                return {
                    'success': False,
                    'error': 'Analysis exceeded token budget - please try with a simpler request'
                }

            # Handle response based on provider
            if provider == 'anthropic':
                # Anthropic SDK response format
                # Check if we're done (no tool calls)
                if finish_reason == "end_turn":
                    # Extract final text response from content blocks
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

                # Handle tool calls
                elif finish_reason == "tool_use":
                    # Add assistant's response to messages
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    # Execute all tool calls
                    for block in response.content:
                        if block.type == "tool_use":
                            logger.info(f"Executing tool: {block.name} with input: {block.input}")

                            # Execute the tool
                            result = agent_tools.execute_tool(block.name, block.input, activity.user_id, activity.id)

                            # Add tool result to messages
                            messages.append({
                                "role": "user",
                                "content": [{
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps(result)
                                }]
                            })

                else:
                    logger.warning(f"Unexpected finish reason: {finish_reason}")
                    break

        # If we exceeded max iterations
        logger.warning(f"Exceeded max iterations ({max_iterations})")
        return {
            'success': False,
            'error': 'Analysis took too many steps'
        }

    except ValueError as e:
        # API key not configured
        return {
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        logger.error(f"Error generating insights for activity {activity.id}: {str(e)}")
        return {
            'success': False,
            'error': f'Failed to generate insights: {str(e)}'
        }
