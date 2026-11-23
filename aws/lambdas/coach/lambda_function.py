"""Lambda adapter for the standalone coaching capability."""

import logging

from shared_coach.service import coaching_result

logging.getLogger().setLevel(logging.INFO)


def lambda_handler(event, context):
    """Read the invocation fields and return the existing coaching result."""
    return coaching_result(
        event.get("llm_payload", {}),
        event.get("detail_level", "simple"),
        event.get("agent", "activity"),
    )
