"""Flask adapters for the existing API and the local standalone API contract."""

import os

from flask import Blueprint, current_app, jsonify, request

from app.auth import auth_bp
from app.auth.repository import FlaskUserRepository
from app.shared_auth import http_contract
from app.shared_auth.service import AuthService, DuplicateUser

local_auth_bp = Blueprint("local_auth", __name__, url_prefix="/auth/api")


def _service() -> AuthService:
    """Bind auth to Flask's database and signing configuration."""
    return AuthService(FlaskUserRepository(), current_app.config["SECRET_KEY"],
                       access_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRY_MINUTES", "30")),
                       refresh_days=int(os.getenv("REFRESH_TOKEN_EXPIRY_DAYS", "30")))


@auth_bp.post("/register")
def register():
    """Register a user using Flask's existing response contract."""
    data = request.get_json()
    try:
        _service().register(data["username"], data["email"], data["password"],
                            data["firstname"], data["lastname"], legacy=True)
    except DuplicateUser as error:
        message = "Username already exists" if str(error) == "username" else "Email already in use"
        return jsonify(message=message), 400
    return jsonify(message="User created successfully"), 201


@auth_bp.post("/login")
def login():
    """Log in by username and issue a one-hour legacy Flask token."""
    data = request.get_json()
    token = _service().login(data["username"], data["password"], legacy=True)
    if token is None:
        return jsonify(message="Invalid username or password"), 401
    return jsonify(token=token), 200


@local_auth_bp.post("/login")
@local_auth_bp.post("/register")
@local_auth_bp.post("/refresh")
def local_auth():
    """Expose the production standalone auth contract to the local frontend."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(message="Invalid JSON"), 400
    action = request.path.rsplit("/", 1)[-1]
    service = _service()
    if action == "refresh":
        result, status = http_contract.refresh(service, body, request.headers.get("Authorization", ""))
    elif action == "login":
        result, status = http_contract.login(service, body)
    else:
        result, status = http_contract.register(service, body)
    return jsonify(result), status
