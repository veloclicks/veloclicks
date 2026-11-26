"""API Gateway adapter for the isolated activities-list prototype."""

from time import perf_counter

_module_started = perf_counter()

import json
import logging
import os
from urllib.parse import parse_qs

import jwt
from shared_auth.verification import access_token_user_id

logger = logging.getLogger(__name__)
_module_import_ms = round((perf_counter() - _module_started) * 1000, 2)
_first_invocation = True
_first_get = True


def handler(event, context):
    """Authenticate and serve a paginated GET, with an unauthenticated CORS preflight."""
    global _first_invocation, _first_get
    started = perf_counter()
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    timings = {
        "event": "activities_latency",
        "request_id": getattr(context, "aws_request_id", None),
        "gateway_request_id": event.get("requestContext", {}).get("requestId"),
        "method": method if method in ("GET", "OPTIONS") else "OTHER",
        "cold_invocation": _first_invocation,
        "first_get": method == "GET" and _first_get,
    }
    if _first_invocation:
        timings["module_import_ms"] = _module_import_ms
    _first_invocation = False
    if method == "GET":
        _first_get = False
    try:
        headers = {name.lower(): value for name, value in (event.get("headers") or {}).items()}
        status, body = _handle_request(event, headers, timings)
        timings["status"] = status
        phase_started = perf_counter()
        response = _response(status, body, headers.get("origin"))
        timings["json_response_ms"] = round((perf_counter() - phase_started) * 1000, 2)
        timings["response_bytes"] = len(response["body"].encode("utf-8"))
        return response
    finally:
        timings["handler_ms"] = round((perf_counter() - started) * 1000, 2)
        print(json.dumps(timings, separators=(",", ":")))


def _handle_request(event: dict, headers: dict, timings: dict | None = None) -> tuple[int, dict]:
    """Select the HTTP result before applying the shared headers."""
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    if method == "OPTIONS":
        return 200, {}
    if method != "GET":
        return 405, {"error": "Method not allowed"}

    timings = {} if timings is None else timings
    phase_started = perf_counter()
    secret = os.environ["SECRET_KEY"]
    try:
        # Match the deployed Flask header parsing and reuse its token verifier.
        token = headers.get("authorization", "").split(" ")[1]
        user_id = access_token_user_id(token, secret)
    except (jwt.InvalidTokenError, IndexError):
        return 401, {"error": "Authentication required"}
    finally:
        timings["auth_ms"] = round((perf_counter() - phase_started) * 1000, 2)

    path = event.get("path") or event.get("rawPath") or ""
    if path.rstrip("/").endswith("/strava/activities/snapshot"):
        from shared_activities import snapshot

        def tier():
            from activity_list import database_engine, user_tier

            return user_tier(database_engine(os.environ["DATABASE_URL"]), user_id)

        try:
            result = snapshot.read(user_id, tier)
        except Exception as error:
            logger.warning("Snapshot unavailable (%s)", type(error).__name__)
            result = None
        return (200, result) if result is not None else (404, {"error": "Snapshot unavailable"})

    query = event.get("queryStringParameters") or {}
    raw_query = event.get("rawQueryString")
    if raw_query is not None:
        query = {key: values[0] for key, values in parse_qs(raw_query, keep_blank_values=True).items()}
    elif event.get("multiValueQueryStringParameters"):
        query = {key: values[0] for key, values in event["multiValueQueryStringParameters"].items()}

    timings["page_type"] = "continuation" if "cursor" in query else "initial"

    # Reject unauthorized requests before importing SQLAlchemy or opening a DB connection.
    phase_started = perf_counter()
    from sqlalchemy.exc import SQLAlchemyError
    from activity_list import InvalidPage, activity_page, database_engine
    timings["lazy_import_ms"] = round((perf_counter() - phase_started) * 1000, 2)

    try:
        phase_started = perf_counter()
        engine = database_engine(os.environ["DATABASE_URL"])
        timings["engine_setup_ms"] = round((perf_counter() - phase_started) * 1000, 2)
        return 200, activity_page(engine, user_id, query, secret, timings)
    except InvalidPage as error:
        return 400, {"error": str(error)}
    except SQLAlchemyError as error:
        logger.error("Activities database query failed (%s)", type(error).__name__)
        return 500, {"error": "Could not load activities"}


def _response(status: int, body: dict, origin: str | None) -> dict:
    """Allow cross-origin bearer requests only from configured frontend origins."""
    allowed_origins = {value.strip() for value in os.getenv("CORS_ORIGIN", "*").split(",")}
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "private, no-store",
        "Access-Control-Allow-Headers": "Authorization,Content-Type",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Vary": "Origin",
    }
    if "*" in allowed_origins:
        headers["Access-Control-Allow-Origin"] = "*"
    elif origin in allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body, separators=(",", ":")),
    }
