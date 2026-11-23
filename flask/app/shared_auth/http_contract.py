"""Public standalone API response mappings shared by both HTTP adapters."""

from .service import AuthService, DuplicateUser


def login(service: AuthService, body: dict) -> tuple[dict, int]:
    """Translate the standalone login request and return its public response."""
    username, password = body.get("username"), body.get("password")
    if not username or not password:
        return {"message": "Username and password required"}, 400
    token = service.login(username, password)
    if token is None:
        return {"message": "Invalid credentials"}, 401
    return {"token": token}, 200


def register(service: AuthService, body: dict) -> tuple[dict, int]:
    """Translate the standalone registration request and report duplicate accounts."""
    email, password = body.get("email"), body.get("password")
    if not email or not password:
        return {"message": "Email and password required"}, 400
    try:
        service.register(body.get("username") or email, email, password,
                         body.get("firstname"), body.get("lastname"))
    except DuplicateUser:
        return {"message": "User already exists"}, 409
    return {"message": "Registration successful"}, 201


def refresh(service: AuthService, body: dict, authorization: str) -> tuple[dict, int]:
    """Accept a refresh token in the authorization header or request body."""
    token = authorization.removeprefix("Bearer ") if authorization else body.get("refresh_token")
    if not token:
        return {"message": "Refresh token required"}, 400
    access_token = service.refresh(token)
    if access_token is None:
        return {"message": "Invalid or expired token"}, 401
    return {"token": access_token}, 200
