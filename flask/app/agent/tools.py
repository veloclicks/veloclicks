"""
AI agent orchestration logic.
Handles all LLM interactions and tool calling for generating insights.
"""

import json
import logging
import os
import litellm
from app.agent import agent_tools
from app.profile import tools as profile_tools

logger = logging.getLogger(__name__)

# Configure LiteLLM
litellm.drop_params = True  # Drop unsupported params for different providers
litellm.set_verbose = False  # Set to True for debugging

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


def _get_model_config():
    """
    Get LLM model configuration from environment variables.

    Returns:
        dict: Model configuration with 'name' and optional API key

    Raises:
        ValueError: If required API keys are not set
    """
    # Default to Claude Sonnet 4
    model_name = os.getenv('LLM_MODEL', 'claude-sonnet-4-20250514')

    # Set API keys based on model provider
    if model_name.startswith('claude'):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not set in environment")
            raise ValueError("AI service not configured - ANTHROPIC_API_KEY required")
        os.environ['ANTHROPIC_API_KEY'] = api_key
    elif model_name.startswith('gpt'):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY not set in environment")
            raise ValueError("AI service not configured - OPENAI_API_KEY required")
        os.environ['OPENAI_API_KEY'] = api_key
    elif model_name.startswith('qwen'):
        # Qwen via Alibaba Cloud or other providers
        api_key = os.getenv('QWEN_API_KEY')
        if api_key:
            os.environ['QWEN_API_KEY'] = api_key
        # For local Ollama, no API key needed

    return {'model': model_name}


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
        # Get model configuration
        model_config = _get_model_config()
        model_name = model_config['model']
        logger.info(f"Using LLM model: {model_name}")

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

            # Call LLM via LiteLLM
            # Build request parameters
            request_params = {
                "model": model_name,
                "max_tokens": max_tokens,
                "messages": messages
            }
            # Only include tools if we have any
            if tools:
                request_params["tools"] = tools

            response = litellm.completion(**request_params)

            # Track token usage
            total_input_tokens += response.usage.prompt_tokens
            total_output_tokens += response.usage.completion_tokens
            finish_reason = response.choices[0].finish_reason
            logger.info(f"Finish reason: {finish_reason}, Tokens: {response.usage.prompt_tokens} in + {response.usage.completion_tokens} out (Total: {total_input_tokens + total_output_tokens})")

            # Check if we're exceeding token budget
            if total_input_tokens + total_output_tokens > max_tokens_total:
                logger.warning(f"Token limit exceeded: {total_input_tokens + total_output_tokens} > {max_tokens_total}")
                return {
                    'success': False,
                    'error': 'Analysis exceeded token budget - please try with a simpler request'
                }

            # Get the message from the response
            message = response.choices[0].message

            # Check if we're done (no tool calls)
            if finish_reason == "stop" or not hasattr(message, 'tool_calls') or not message.tool_calls:
                # Extract final text response
                insight_text = message.content or ""

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
            elif message.tool_calls:
                # Add assistant's response to messages
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": message.tool_calls
                })

                # Execute all tool calls
                for tool_call in message.tool_calls:
                    logger.info(f"Executing tool: {tool_call.function.name} with input: {tool_call.function.arguments}")

                    # Parse arguments (they come as JSON string)
                    tool_input = json.loads(tool_call.function.arguments)

                    # Execute the tool
                    result = agent_tools.execute_tool(tool_call.function.name, tool_input, activity.user_id, activity.id)

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
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
