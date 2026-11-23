"""API Gateway adapter for the isolated activities-list prototype."""

import json
import logging
import os
from urllib.parse import parse_qs

import jwt
from shared_auth.verification import access_token_user_id

logger = logging.getLogger(__name__)


def handler(event, context):
    """Authenticate and serve a paginated GET, with an unauthenticated CORS preflight."""
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    if method == "OPTIONS":
        return _response(200, {})
    if method != "GET":
        return _response(405, {"error": "Method not allowed"})

    secret = os.environ["SECRET_KEY"]
    headers = {name.lower(): value for name, value in (event.get("headers") or {}).items()}
    try:
        # Match the deployed Flask header parsing and reuse its token verifier.
        token = headers.get("authorization", "").split(" ")[1]
        user_id = access_token_user_id(token, secret)
    except (jwt.InvalidTokenError, IndexError):
        return _response(401, {"error": "Authentication required"})

    query = event.get("queryStringParameters") or {}
    raw_query = event.get("rawQueryString")
    if raw_query is not None:
        query = {key: values[0] for key, values in parse_qs(raw_query, keep_blank_values=True).items()}
    elif event.get("multiValueQueryStringParameters"):
        query = {key: values[0] for key, values in event["multiValueQueryStringParameters"].items()}

    # Reject unauthorized requests before importing SQLAlchemy or opening a DB connection.
    from sqlalchemy.exc import SQLAlchemyError
    from activity_list import InvalidPage, activity_page, database_engine

    try:
        engine = database_engine(os.environ["DATABASE_URL"])
        return _response(200, activity_page(engine, user_id, query, secret))
    except InvalidPage as error:
        return _response(400, {"error": str(error)})
    except SQLAlchemyError as error:
        logger.error("Activities database query failed (%s)", type(error).__name__)
        return _response(500, {"error": "Could not load activities"})


def _response(status: int, body: dict) -> dict:
    """Encode proxy JSON and preserve cross-origin bearer requests."""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.getenv("CORS_ORIGIN", "*"),
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body, separators=(",", ":")),
    }
