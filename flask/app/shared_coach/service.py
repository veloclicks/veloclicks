"""Generate structured, evidence-based cycling feedback using the configured LLM."""

import json
import logging
import os

from .coaching_prompts import ACTIVITY_COACH_PROMPT

logger = logging.getLogger(__name__)


def _parse_feedback(text: str) -> dict:
    """Validate the provider's structured response before it reaches the UI."""
    feedback = json.loads(text)
    fields = ("headline", "analysis", "takeaway")
    if not isinstance(feedback, dict) or any(
        not isinstance(feedback.get(field), str) or not feedback[field].strip()
        for field in fields
    ):
        raise ValueError("Coaching response did not contain the required fields")
    return {field: feedback[field].strip() for field in fields}


def generate_coaching(llm_payload: dict) -> tuple[dict, dict]:
    """Generate one coaching report and return its token usage."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=os.environ.get("LLM_MODEL", "claude-sonnet-5"),
        max_tokens=1200,
        system=ACTIVITY_COACH_PROMPT,
        messages=[{"role": "user", "content": json.dumps(llm_payload)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    logger.warning("Raw coaching response: %r", text)
    logger.warning("Stop reason: %s", response.stop_reason)
    feedback = _parse_feedback(text)
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
    }
    return feedback, usage


def coaching_result(llm_payload: dict, detail_level: str = "simple",
                    agent: str = "activity") -> dict:
    """Return the shared coaching contract; ignore legacy selection parameters."""
    try:
        feedback, usage = generate_coaching(llm_payload)
    except (ValueError, json.JSONDecodeError) as error:
        logger.warning("Coaching response invalid: %s", error)
        return {"success": False, "error": "Unable to generate coaching feedback"}
    except Exception:
        logger.exception("Coaching generation failed")
        return {"success": False, "error": "Unable to generate coaching feedback"}
    return {"success": True, "coaching": feedback, "token_usage": usage}
