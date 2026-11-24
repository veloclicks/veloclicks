"""API Gateway adapter for standalone authentication."""

from time import perf_counter

_module_started = perf_counter()

import json
import os

from shared_auth import http_contract

_auth_service = None
_module_import_ms = round((perf_counter() - _module_started) * 1000, 2)
_first_invocation = True


def get_auth_service():
    """Reuse the service across invocations and defer loading the database driver."""
    global _auth_service
    if _auth_service is None:
        from db import get_connection
        from repository import PostgresUserRepository
        from shared_auth.service import AuthService

        _auth_service = AuthService(
            PostgresUserRepository(get_connection),
            os.environ["SECRET_KEY"],
            access_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRY_MINUTES", "30")),
            refresh_days=int(os.getenv("REFRESH_TOKEN_EXPIRY_DAYS", "30")),
        )
    return _auth_service


def handler(event, context):
    global _first_invocation
    started = perf_counter()
    path = event.get("path") or event.get("rawPath", "")
    operation = next((name for name in ("login", "register", "refresh") if path.endswith("/" + name)), "other")
    timings = {
        "event": "auth_latency",
        "operation": operation,
        "request_id": getattr(context, "aws_request_id", None),
        "gateway_request_id": event.get("requestContext", {}).get("requestId"),
        "cold_invocation": _first_invocation,
    }
    if _first_invocation:
        timings["module_import_ms"] = _module_import_ms
    _first_invocation = False
    try:
        response = _handle_request(event, timings)
        timings["status"] = response["statusCode"]
        return response
    finally:
        timings["handler_ms"] = round((perf_counter() - started) * 1000, 2)
        print(json.dumps(timings, separators=(",", ":")))


def _handle_request(event, timings):
    """Map API Gateway v1 or v2 requests to the standalone auth API contract."""
    path = event.get("path") or event.get("rawPath", "")
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    if method == "OPTIONS":
        return _response(200, {})
    if method != "POST":
        return _response(405, {"message": "Method not allowed"})

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"message": "Invalid JSON"})
    if not isinstance(body, dict):
        return _response(400, {"message": "Invalid JSON"})

    if path.endswith("/login"):
        phase_started = perf_counter()
        service = get_auth_service()
        timings["service_setup_ms"] = round((perf_counter() - phase_started) * 1000, 2)
        phase_started = perf_counter()
        result, status = http_contract.login(service, body)
        timings["login_ms"] = round((perf_counter() - phase_started) * 1000, 2)
        if status == 200:
            from shared_auth.verification import access_token_user_id
            import jwt
            token = result.get("access_token")
            if isinstance(token, str):
                try:
                    timings["user_id"] = access_token_user_id(token, os.environ["SECRET_KEY"])
                except jwt.InvalidTokenError:
                    pass
    elif path.endswith("/register"):
        result, status = http_contract.register(get_auth_service(), body)
    elif path.endswith("/refresh"):
        headers = event.get("headers") or {}
        authorization = headers.get("Authorization") or headers.get("authorization", "")
        result, status = http_contract.refresh(get_auth_service(), body, authorization)
    else:
        return _response(404, {"message": "Not found"})
    phase_started = perf_counter()
    response = _response(status, result)
    timings["json_response_ms"] = round((perf_counter() - phase_started) * 1000, 2)
    return response


def _response(status_code: int, body: dict) -> dict:
    """Encode the response and preserve the existing API Gateway CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.environ.get("CORS_ORIGIN", "*"),
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body),
    }
