"""
AI coaching feedback for completed activities.

Takes a pre-assembled llm_payload (from activity_analyser mode='llm')
and makes a single LLM call to generate coaching prose.
"""

import json
import logging
import os

from flask import current_app

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert cycling coach providing post-activity feedback.
Be specific, evidence-based, and actionable. Reference the actual numbers provided.
Keep language direct and encouraging but honest."""

COACHING_PROMPT = """Analyse this cycling activity and provide coaching feedback.

{payload}

{response_instruction}"""

RESPONSE_INSTRUCTIONS = {
    'simple': (
        "Provide a concise 2-3 paragraph coaching summary covering workout quality, "
        "execution vs target, and one key takeaway."
    ),
    'detailed': (
        "Provide comprehensive coaching feedback covering: workout quality and execution, "
        "interval-by-interval analysis where available, pacing and power fade, "
        "training value, and 2-3 specific actionable recommendations."
    ),
}


def generate_coaching(llm_payload: dict, detail_level: str = 'simple') -> dict:
    """
    Generate AI coaching feedback from a pre-assembled llm_payload.

    Args:
        llm_payload:  Output of activity_analyser.analyse_activity(mode='llm')['llm_payload']
        detail_level: 'simple' (2-3 paragraphs) or 'detailed' (comprehensive)

    Returns:
        dict with 'success' bool and 'coaching' str, or 'error' str and 'token_usage' dict
    """
    response_instruction = RESPONSE_INSTRUCTIONS.get(detail_level, RESPONSE_INSTRUCTIONS['simple'])
    prompt = COACHING_PROMPT.format(
        payload              = json.dumps(llm_payload, indent=2),
        response_instruction = response_instruction,
    )

    try:
        coaching, token_usage = _call_llm(prompt, detail_level)
        return {'success': True, 'coaching': coaching, 'token_usage': token_usage}
    except Exception as e:
        logger.error(f"generate_coaching() LLM call failed: {e}")
        return {'success': False, 'error': str(e)}


def _call_llm(prompt: str, detail_level: str) -> tuple:
    api_key = current_app.config.get('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError('AI service not configured — ANTHROPIC_API_KEY required')

    model      = os.getenv('LLM_MODEL', 'claude-sonnet-4-6-20251101')
    max_tokens = 800 if detail_level == 'simple' else 2000

    from anthropic import Anthropic
    client   = Anthropic(api_key=api_key)
    response = client.messages.create(
        model      = model,
        max_tokens = max_tokens,
        system     = SYSTEM_PROMPT,
        messages   = [{'role': 'user', 'content': prompt}],
    )

    total = response.usage.input_tokens + response.usage.output_tokens
    cost  = (response.usage.input_tokens * 0.003 / 1000) + (response.usage.output_tokens * 0.015 / 1000)
    logger.info(
        f"_call_llm() tokens: {response.usage.input_tokens} in "
        f"+ {response.usage.output_tokens} out "
        f"= {total} total | est. cost ${cost:.4f}"
    )

    text = ''.join(block.text for block in response.content if block.type == 'text')
    token_usage = {
        'input_tokens':  response.usage.input_tokens,
        'output_tokens': response.usage.output_tokens,
        'total_tokens':  response.usage.input_tokens + response.usage.output_tokens,
    }
    return text, token_usage
