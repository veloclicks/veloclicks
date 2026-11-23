"""Verify Veloclicks access tokens without loading password hashing."""

import jwt


def access_token_user_id(token: str, secret: str) -> int:
    """Return the user ID from either access-token format and reject refresh tokens."""
    payload = jwt.decode(token, secret, algorithms=["HS256"],
                         options={"require": ["exp", "user_id"]})
    if payload.get("type", "access") != "access" or type(payload["user_id"]) is not int:
        raise jwt.InvalidTokenError("Invalid access token")
    return payload["user_id"]
