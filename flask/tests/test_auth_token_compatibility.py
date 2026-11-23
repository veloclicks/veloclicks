"""Lock down historical JWT claims before moving auth into a shared service."""

import datetime
import os
import unittest
from unittest.mock import Mock, patch

import jwt

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-only-auth-signing-key")
os.environ["LOG_LEVEL"] = "WARNING"

from app import application
from app.common.auth import require_auth
from app.shared_auth.service import AuthService, Credentials
from flask import g

SECRET = "test-only-auth-signing-key"


class TokenCompatibilityTest(unittest.TestCase):
    """Preserve frontend claims and validate both historical access token shapes."""

    def test_standalone_token_claims_and_lifetimes(self):
        repository = Mock()
        repository.by_username_or_email.return_value = user = Credentials(
            7, "rider@example.test", "legacy-hash")
        service = AuthService(repository, SECRET)
        with patch("app.shared_auth.service.check_password_hash", return_value=True):
            access_token = service.login("rider", "password")
        refresh_token = service.issue_refresh_token(user)
        access = jwt.decode(access_token, SECRET, algorithms=["HS256"])
        refresh = jwt.decode(refresh_token, SECRET, algorithms=["HS256"])
        self.assertEqual((access["sub"], access["user_id"], access["email"], access["type"]),
                         (7, 7, "rider@example.test", "access"))
        self.assertEqual(access["exp"] - access["iat"], 30 * 60)
        self.assertEqual((refresh["sub"], refresh["user_id"], refresh["type"]), (7, 7, "refresh"))
        self.assertEqual(refresh["exp"] - refresh["iat"], 30 * 86400)

    def test_historical_access_tokens_are_accepted(self):
        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
        for claims in ({}, {"sub": 7, "type": "access"}):
            payload = {"user_id": 7, "email": "rider@example.test", "exp": expires, **claims}
            token = jwt.encode(payload, SECRET, algorithm="HS256")
            with application.test_request_context(headers={"Authorization": f"Bearer {token}"}):
                with patch.dict(application.config, SECRET_KEY=SECRET):
                    self.assertEqual(require_auth(lambda: g.user_id)(), 7)

    def test_protected_route_rejects_invalid_tokens(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        tokens = (
            jwt.encode({"user_id": 7, "type": "refresh", "exp": now + datetime.timedelta(minutes=5)},
                       SECRET, algorithm="HS256"),
            jwt.encode({"user_id": 7, "exp": now - datetime.timedelta(minutes=5)},
                       SECRET, algorithm="HS256"),
            jwt.encode({"exp": now + datetime.timedelta(minutes=5)}, SECRET, algorithm="HS256"),
            jwt.encode({"user_id": 7, "exp": now + datetime.timedelta(minutes=5)},
                       "different-signing-key", algorithm="HS256"),
            "malformed",
        )
        for token in tokens:
            with self.subTest(token=token), application.test_request_context(
                headers={"Authorization": f"Bearer {token}"}
            ), patch.dict(application.config, SECRET_KEY=SECRET):
                response, status = require_auth(lambda: self.fail("called protected view"))()
                self.assertEqual(status, 401)
                self.assertEqual(response.json, {"error": "Authentication required"})
