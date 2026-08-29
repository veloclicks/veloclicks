import logging

from coach_service import generate_coaching

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    try:
        llm_payload  = event.get('llm_payload', {})
        detail_level = event.get('detail_level', 'simple')
        agent        = event.get('agent', 'activity')

        coaching, token_usage = generate_coaching(llm_payload, detail_level, agent)
        return {'success': True, 'coaching': coaching, 'token_usage': token_usage}

    except Exception as e:
        logger.error(f"lambda_handler() failed: {e}")
        return {'success': False, 'error': str(e)}
