"""API Gateway adapter for standalone authentication."""

import json
import os

from shared_auth import http_contract

_auth_service = None


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


def lambda_handler(event, context):
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
        result, status = http_contract.login(get_auth_service(), body)
    elif path.endswith("/register"):
        result, status = http_contract.register(get_auth_service(), body)
    elif path.endswith("/refresh"):
        headers = event.get("headers") or {}
        authorization = headers.get("Authorization") or headers.get("authorization", "")
        result, status = http_contract.refresh(get_auth_service(), body, authorization)
    else:
        return _response(404, {"message": "Not found"})
    return _response(status, result)


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
