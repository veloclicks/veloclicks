"""Compare the isolated SQLAlchemy Core adapter with the existing Flask endpoint."""

from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import subprocess
import sys

import jwt
import pytest

from app import create_app
from app.config import Config
from app.models import Activity, User, db

SECRET = "prototype-parity-test-key"
PROTOTYPE = Path(__file__).resolve().parents[2] / "aws/lambdas/activities"
URL = "/strava/activities/"


def test_handler_import_does_not_load_flask_or_sqlalchemy():
    """Check that importing a cold adapter avoids the web and database stacks."""
    subprocess.run([sys.executable, "-c",
                    "import handler,sys; assert not {'flask','app','sqlalchemy','psycopg2','werkzeug'} & sys.modules.keys()"],
                   cwd=PROTOTYPE, check=True)


@pytest.fixture
def adapters(monkeypatch):
    """Run both adapters against the same test database and signing key."""
    monkeypatch.syspath_prepend(str(PROTOTYPE))
    prototype = importlib.import_module("handler")
    page_module = importlib.import_module("activity_list")
    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", "sqlite://")
    monkeypatch.setattr(Config, "SECRET_KEY", SECRET)
    monkeypatch.setenv("SECRET_KEY", SECRET)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    app = create_app()
    client = app.test_client()
    with app.app_context():
        db.create_all()
        db.session.add_all(User(id=i, username=f"rider{i}", email=f"rider{i}@example.test")
                           for i in (1, 2, 3, 4))
        start = datetime(2026, 6, 1, 12, 30, 59, 150000)
        db.session.add_all(Activity(
            id=i, user_id=1, name=f"Ride {i}", start_date=start,
            start_date_local=start + timedelta(hours=1) if i % 2 else None,
            moving_time=1200.126, weighted_average_watts=217.154, tss=56.28, rpe=7, ftp=251,
        ) for i in range(1, 501))
        db.session.add_all(Activity(id=i, user_id=2, start_date=start) for i in range(1001, 1013))
        db.session.add_all(Activity(id=i, user_id=4, start_date=start) for i in range(1101, 1151))
        db.session.add(Activity(id=2000, user_id=1, start_date=datetime(2024, 1, 1)))
        db.session.commit()
        engine = db.engine
    monkeypatch.setattr(page_module, "database_engine", lambda _url: engine)

    def call(user_id, *, token_type=None, params=None):
        """Return parsed outputs from both HTTP adapters for the same request."""
        claims = {"user_id": user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
        if token_type:
            claims.update(sub=user_id, type=token_type)
        token = jwt.encode(claims, SECRET, algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}
        legacy = client.get(URL, query_string=params or {}, headers=headers)
        proxy = prototype.handler({"httpMethod": "GET", "headers": headers,
                                   "queryStringParameters": params or {}}, None)
        return (legacy.status_code, legacy.json), (proxy["statusCode"], json.loads(proxy["body"]))

    call.application = app
    return call, prototype


@pytest.mark.parametrize(("user_id", "size"), [(2, 12), (3, 0), (4, 50)])
def test_small_first_pages(adapters, user_id, size):
    """A complete first page has no cursor, including exactly 50 rides."""
    call, _ = adapters
    flask, prototype = call(user_id, params={"years": "2026", "limit": "50"})
    assert flask == prototype
    assert len(prototype[1]["activities"]) == size
    assert prototype[1]["next_cursor"] is None


def test_pagination_and_cursor_interchange(adapters):
    """Exchange cursors between adapters and preserve all tied rows and values."""
    call, _ = adapters
    params = {"years": "2026", "limit": "50"}
    found = []
    for request_number in range(10):
        flask, prototype = call(1, token_type="access", params=params)
        assert flask == prototype
        status, page = prototype
        assert status == 200
        if request_number == 0:
            row = page["activities"][0]
            assert row["start_date"] == "2026-06-01T12:30:59.150000"
            assert row["start_date_local"] is None
            assert row["average_watts"] is None
            assert row["moving_time"] == 1200.13
            assert row["tss"] == 56.3
        found += [row["id"] for row in page["activities"]]
        params["cursor"] = (flask if request_number % 2 else prototype)[1]["next_cursor"]
    assert found == list(range(500, 0, -1))
    assert params["cursor"] is None


def test_security_and_invalid_parameters(adapters):
    """Reject cross-owner and wrong-range cursors, refresh tokens and bad input."""
    call, prototype = adapters
    options = prototype.handler({"httpMethod": "OPTIONS"}, None)
    assert options["statusCode"] == 200
    assert prototype.handler({"httpMethod": "GET"}, None)["statusCode"] == 401
    params = {"years": "2026", "limit": "1"}
    cursor = call(1, params=params)[0][1]["next_cursor"]
    for user_id, query in (
        (2, {**params, "cursor": cursor}),
        (1, {**params, "cursor": cursor, "years": "2025"}),
        (1, {**params, "cursor": cursor[:-1]}),
        (1, {"cursor": cursor}),
        (1, {"limit": "0"}),
        (1, {"limit": "51"}),
        (1, {"limit": "bad"}),
        (1, {"limit": "1", "years": "invalid"}),
    ):
        flask, response = call(user_id, params=query)
        assert flask == response
        assert response[0] == 400
    flask, response = call(1, token_type="refresh", params=params)
    assert flask == response
    assert response[0] == 401


def test_rolling_window_cursor_parity(adapters, monkeypatch):
    """A cursor carries the original 180-day window between either adapter."""
    call, _ = adapters
    flask_routes = importlib.import_module("app.strava.routes")
    prototype_query = importlib.import_module("activity_list")

    class Clock(datetime):
        """Freeze both date-window builders while exercising a later request."""

        date = datetime(2026, 11, 23, 12)

        @classmethod
        def now(cls, tz=None):
            """Return the controlled clock without altering datetime parsing."""
            return cls.date

    monkeypatch.setattr(flask_routes, "datetime", Clock)
    monkeypatch.setattr(prototype_query, "datetime", Clock)
    initial_flask, initial_prototype = call(1, params={"limit": "1"})
    assert initial_flask == initial_prototype
    cursor = initial_flask[1]["next_cursor"]
    assert cursor
    Clock.date = datetime(2027, 1, 1)
    later_flask, later_prototype = call(1, params={"limit": "1", "cursor": cursor})
    assert later_flask == later_prototype
    assert [row["id"] for row in later_prototype[1]["activities"]] == [499]


def test_cors_allows_both_production_hosts(adapters, monkeypatch):
    """Scope CORS to the configured production origins, including www."""
    _, prototype = adapters
    origins = ("https://www.veloclicks.com", "https://veloclicks-prod.vercel.app")
    monkeypatch.setenv("CORS_ORIGIN", ",".join(origins))
    for origin in (*origins, "https://unrelated.example"):
        for method in ("OPTIONS", "GET"):
            result = prototype.handler({"httpMethod": method, "headers": {"Origin": origin}}, None)
            assert result["headers"]["Vary"] == "Origin"
            expected = origin if origin in origins else None
            assert result["headers"].get("Access-Control-Allow-Origin") == expected


def test_snapshot_hit_without_database_import(tmp_path, monkeypatch):
    """A cold snapshot hit uses the valid access token and no SQLAlchemy imports."""
    monkeypatch.setenv("SECRET_KEY", SECRET)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ACTIVITY_SNAPSHOT_BUCKET", raising=False)
    monkeypatch.setenv("ACTIVITY_SNAPSHOT_DIRECTORY", str(tmp_path))
    directory = tmp_path / "activity-snapshots"
    directory.mkdir()
    (directory / "1.json").write_text(json.dumps({"user_id": 1, "activities": [
        {"id": 10, "user_id": 1, "start_date": datetime.now(timezone.utc).isoformat()},
    ]}))
    script = """
import json, os, sys, time
import jwt
from handler import handler
def request(user_id, typ="access", expiration=None):
    token = jwt.encode({"user_id": user_id, "type": typ, "exp": expiration or time.time()+60},
                       os.environ["SECRET_KEY"], algorithm="HS256")
    return handler({"httpMethod": "GET", "path": "/strava/activities/snapshot",
                    "headers": {"Authorization": "Bearer " + token}}, None)
response = request(1)
assert response["statusCode"] == 200 and json.loads(response["body"])["activities"][0]["id"] == 10
assert request(2)["statusCode"] == 404
assert request(1, "refresh")["statusCode"] == 401
assert request(1, expiration=time.time()-60)["statusCode"] == 401
assert not {"sqlalchemy", "psycopg2", "flask", "activity_list"} & sys.modules.keys()
"""
    subprocess.run([sys.executable, "-c", script], cwd=PROTOTYPE, check=True)


def test_basic_and_premium_list_entitlement_parity(adapters):
    """Apply the same rolling window to Flask and standalone pages."""
    from app.models.user import MembershipType

    call, _ = adapters
    params = {"years": "2024", "limit": "50"}
    flask, prototype = call(1, params=params)
    assert flask == prototype == (200, {"activities": [], "next_cursor": None})
    with call.application.app_context():
        db.session.get(User, 1).membership_type = MembershipType.PREMIUM_TIER
        db.session.commit()
    flask, prototype = call(1, params=params)
    assert flask == prototype
    assert [row["id"] for row in prototype[1]["activities"]] == [2000]
