"""Flask authorization decorator for both deployed access token contracts."""

from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from app.shared_auth.service import access_token_user_id


def require_auth(view):
    """Run the view with the authenticated user ID, or return the existing 401."""
    @wraps(view)
    def decorated(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        try:
            token = authorization.split(" ")[1]
            g.user_id = access_token_user_id(token, current_app.config["SECRET_KEY"])
        except (jwt.InvalidTokenError, IndexError):
            return jsonify(error="Authentication required"), 401
        return view(*args, **kwargs)
    return decorated
