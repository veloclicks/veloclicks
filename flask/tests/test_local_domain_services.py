"""Exercise Flask auth and coaching contracts against isolated account and activity data."""

import datetime
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import jwt
from werkzeug.security import generate_password_hash

os.environ["LOG_LEVEL"] = "WARNING"

from app import create_app
from app.auth.repository import FlaskUserRepository
from app.models import Activity, User, db
from app.models.user import MembershipType
from app.shared_auth.service import AuthService

SECRET = "test-only-auth-signing-key"
ACCOUNT = {"username": "rider", "email": "rider@example.test", "password": "test-password",
           "firstname": "Test", "lastname": "Rider"}


class LocalDomainServicesTest(unittest.TestCase):
    """Verify auth adapters and the full Flask coaching flow without AWS or paid inference."""

    def setUp(self):
        with patch.dict(os.environ, {"LOCAL_DOMAIN_SERVICES": "1"}):
            with patch.multiple("app.config.Config", SQLALCHEMY_DATABASE_URI="sqlite://",
                                SECRET_KEY=SECRET):
                self.app = create_app()
        self.client = self.app.test_client()
        self.settings = patch.dict(os.environ, {
            "LOCAL_DOMAIN_SERVICES": "1",
            "ANTHROPIC_API_KEY": "fake-provider-key",
            "ACCESS_TOKEN_EXPIRY_MINUTES": "30",
        })
        self.settings.start()
        self.addCleanup(self.settings.stop)
        with self.app.app_context():
            db.create_all()

    def test_register_and_login_across_adapters(self):
        """A local standalone registration can log in via either historical contract."""
        response = self.client.post("/auth/api/register", json=ACCOUNT)
        self.assertEqual((response.status_code, response.json),
                         (201, {"message": "Registration successful"}))
        self.assertEqual(self.client.post("/auth/api/register", json=ACCOUNT).status_code, 409)
        duplicate = self.client.post("/api/register", json=ACCOUNT)
        self.assertEqual((duplicate.status_code, duplicate.json),
                         (400, {"message": "Username already exists"}))
        self.assertEqual(self.client.post(
            "/auth/api/register", json={**ACCOUNT, "email": "other@example.test"},
        ).status_code, 409)
        credentials = {"username": ACCOUNT["email"], "password": ACCOUNT["password"]}
        access = self.client.post("/auth/api/login", json=credentials)
        self.assertEqual(access.status_code, 200)
        self.assertEqual(self.client.get("/api/profile", headers=self._bearer(access.json["token"])).status_code, 200)
        self.assertEqual(self.client.post("/api/login", json=credentials).status_code, 401)
        legacy = self.client.post("/api/login", json={**credentials, "username": ACCOUNT["username"]})
        self.assertEqual(legacy.status_code, 200)
        payload = jwt.decode(legacy.json["token"], SECRET, algorithms=["HS256"])
        self.assertEqual(set(payload), {"user_id", "email", "exp"})
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        self.assertAlmostEqual(payload["exp"] - now, 3600, delta=5)
        self.assertEqual(self.client.post("/auth/api/login", json={**credentials, "password": "wrong"}).status_code, 401)
        self.assertEqual(self.client.post("/auth/api/login", json=[]).status_code, 400)

    def test_refresh_accepts_legacy_integer_subject_and_rejects_access_token(self):
        """Refresh supports both request forms and rejects expired or wrongly typed tokens."""
        with self.app.app_context():
            # An existing Werkzeug PBKDF2 account must remain usable after the refactor.
            db.session.add(User(username=ACCOUNT["username"], email=ACCOUNT["email"],
                                password_hash=generate_password_hash(
                                    ACCOUNT["password"], method="pbkdf2:sha256")))
            db.session.commit()
            repository = FlaskUserRepository()
            token = AuthService(repository, SECRET).issue_refresh_token(
                repository.by_username(ACCOUNT["username"]),
            )
        self.assertEqual(self.client.post("/api/login", json=ACCOUNT).status_code, 200)
        response = self.client.post("/auth/api/refresh", json={}, headers=self._bearer(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post("/auth/api/refresh", json={"refresh_token": token}).status_code, 200)
        self.assertEqual(self.client.get("/api/profile", headers=self._bearer(token)).status_code, 401)
        self.assertEqual(self.client.post("/auth/api/refresh", json={"refresh_token": response.json["token"]}).status_code, 401)
        self.assertEqual(self.client.post("/auth/api/refresh", json={}).status_code, 400)
        expired = jwt.encode({"sub": 1, "type": "refresh", "exp": 1}, SECRET, algorithm="HS256")
        self.assertEqual(self.client.post("/auth/api/refresh", json={"refresh_token": expired}).status_code, 401)

    def _bearer(self, token):
        """Construct an authorization header for client requests."""
        return {"Authorization": f"Bearer {token}"}

    def _coaching_account(self, membership):
        """Register a test rider and attach a ride with a configurable membership."""
        self.client.post("/auth/api/register", json=ACCOUNT)
        with self.app.app_context():
            user = User.query.filter_by(username=ACCOUNT["username"]).one()
            user.membership_type = membership
            db.session.add(Activity(id=42, user_id=user.id))
            db.session.commit()
        return self._bearer(self.client.post("/auth/api/login", json=ACCOUNT).json["token"])

    @patch("anthropic.Anthropic")
    @patch("app.ai_coach.service.activity_analyser.analyse_activity")
    def test_coaching_generation_summary_and_cache(self, analyse, anthropic):
        """First request runs the prompt and stores the text for all detail levels."""
        headers = self._coaching_account(MembershipType.PREMIUM_TIER)
        analyse.return_value = {"success": True, "llm_payload": {"distance": 50000}}
        create = anthropic.return_value.messages.create
        create.return_value = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Consistent pacing")],
            usage=SimpleNamespace(input_tokens=9, output_tokens=3),
        )
        url = "/ai-coach/activity/42"
        self.assertEqual(self.client.get(url + "/summary", headers=headers).json,
                         {"summary": {"distance": 50000}})
        response = self.client.get(url + "?detail_level=detailed", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            "coaching": "Consistent pacing",
            "token_usage": {"input_tokens": 9, "output_tokens": 3, "total_tokens": 12},
        })
        request = create.call_args.kwargs
        self.assertEqual(request["max_tokens"], 5000)
        self.assertIn("comprehensive coaching feedback", request["messages"][0]["content"])
        self.assertIn('"distance": 50000', request["messages"][0]["content"])
        self.assertEqual(self.client.get(url, headers=headers).json, {"coaching": "Consistent pacing"})
        create.assert_called_once()
        self.assertEqual(analyse.call_count, 2)

    @patch("anthropic.Anthropic")
    @patch("app.ai_coach.service.activity_analyser.analyse_activity")
    def test_coaching_errors_do_not_cache(self, analyse, anthropic):
        """Authorization, missing activities, analytics and provider errors retain their status."""
        headers = self._coaching_account(MembershipType.FREE_TIER)
        url = "/ai-coach/activity/42"
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, headers=headers).status_code, 403)
        analyse.assert_not_called()
        with self.app.app_context():
            User.query.one().membership_type = MembershipType.PREMIUM_TIER
            db.session.commit()
        self.assertEqual(self.client.get("/ai-coach/activity/43", headers=headers).status_code, 404)
        self.assertEqual(self.client.get(url + "?detail_level=bad", headers=headers).status_code, 400)
        analyse.return_value = {"success": False, "error": "Analysis failed"}
        self.assertEqual(self.client.get(url, headers=headers).json, {"error": "Analysis failed"})
        analyse.return_value = {"success": True, "llm_payload": {"distance": 50000}}
        create = anthropic.return_value.messages.create
        create.side_effect = RuntimeError("Provider failed")
        for _ in range(2):
            response = self.client.get(url, headers=headers)
            self.assertEqual((response.status_code, response.json), (500, {"error": "Provider failed"}))
        self.assertEqual(create.call_count, 2)
