import json
import logging
import os

from coaching_prompts import ACTIVITY_COACH_PROMPT

logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
        "pacing and power fade with reference to the time series, terrain correlation, "
        "any technique flags, and 2-3 specific actionable recommendations."
    ),
}

_AGENT_PROMPTS = {
    'activity': ACTIVITY_COACH_PROMPT,
}


def generate_coaching(llm_payload, detail_level, agent):
    system_prompt = _AGENT_PROMPTS.get(agent, ACTIVITY_COACH_PROMPT)

    response_instruction = RESPONSE_INSTRUCTIONS.get(detail_level, RESPONSE_INSTRUCTIONS['simple'])
    prompt = COACHING_PROMPT.format(
        payload              = json.dumps(llm_payload, indent=2),
        response_instruction = response_instruction,
    )

    return _call_llm(prompt, system_prompt, detail_level)


def _call_llm(prompt, system_prompt, detail_level):
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError('ANTHROPIC_API_KEY not set')

    model      = os.environ.get('LLM_MODEL', 'claude-sonnet-5')
    max_tokens = 3000 if detail_level == 'simple' else 5000

    from anthropic import Anthropic
    client   = Anthropic(api_key=api_key)
    response = client.messages.create(
        model      = model,
        max_tokens = max_tokens,
        system     = system_prompt,
        messages   = [{'role': 'user', 'content': prompt}],
    )

    total = response.usage.input_tokens + response.usage.output_tokens
    cost  = (response.usage.input_tokens * 0.003 / 1000) + (response.usage.output_tokens * 0.015 / 1000)
    logger.info(
        f"tokens: {response.usage.input_tokens} in "
        f"+ {response.usage.output_tokens} out "
        f"= {total} total | est. cost ${cost:.4f}"
    )

    text = ''.join(block.text for block in response.content if block.type == 'text')
    token_usage = {
        'input_tokens':  response.usage.input_tokens,
        'output_tokens': response.usage.output_tokens,
        'total_tokens':  total,
    }
    return text, token_usage
