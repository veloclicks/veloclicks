import json
import os

_auth_service = None


def get_auth_service():
    # Lazy import keeps cold start fast — dependencies only loaded on first request
    global _auth_service
    if _auth_service is None:
        from auth_service import AuthService
        from db import get_connection
        _auth_service = AuthService(get_connection)
    return _auth_service


def handler(event, context):
    # Support both API Gateway v1 (httpMethod/path) and v2 (requestContext.http)
    path = event.get("path", "") or event.get("rawPath", "")
    method = event.get("httpMethod", "") or event.get("requestContext", {}).get("http", {}).get("method", "")

    if method == "OPTIONS":
        return _response(200, {})

    if method != "POST":
        return _response(405, {"message": "Method not allowed"})

    try:
        body = json.loads(event.get("body", "{}") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"message": "Invalid JSON"})

    if path.endswith("/login"):
        return _login(body)
    elif path.endswith("/register"):
        return _register(body)
    elif path.endswith("/refresh"):
        return _refresh(body, event.get("headers", {}))
    else:
        return _response(404, {"message": "Not found"})


def _login(body):
    username = body.get("username")
    password = body.get("password")
    if not username or not password:
        return _response(400, {"message": "Username and password required"})

    result = get_auth_service().login(username, password)
    if result is None:
        return _response(401, {"message": "Invalid credentials"})

    # Frontend reads data.token — not data.access_token
    return _response(200, {"token": result["access_token"]})


def _register(body):
    username = body.get("username")
    email = body.get("email")
    password = body.get("password")
    firstname = body.get("firstname")
    lastname = body.get("lastname")

    if not email or not password:
        return _response(400, {"message": "Email and password required"})

    result = get_auth_service().register(
        username=username or email,
        email=email,
        password=password,
        firstname=firstname,
        lastname=lastname,
    )
    if result is None:
        return _response(409, {"message": "User already exists"})

    # Frontend only checks response.ok on register — does not consume body
    return _response(201, {"message": "Registration successful"})


def _refresh(body, headers):
    # Accept token from Authorization header or request body
    auth_header = headers.get("Authorization", "") or headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header else body.get("refresh_token")
    if not token:
        return _response(400, {"message": "Refresh token required"})

    result = get_auth_service().refresh(token)
    if result is None:
        return _response(401, {"message": "Invalid or expired token"})

    return _response(200, {"token": result["access_token"]})


def _response(status_code: int, body: dict) -> dict:
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
