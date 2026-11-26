"""Exercise durable sync scenarios, authorization, and snapshot publication."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import jwt
import pytest

from app import create_app
from app.config import Config
from app.models import Activity, SyncHistory, User, db
from app.models.activity_work import ActivitySnapshotWork, ActivitySyncJob
from app.models.user import MembershipType
from app.shared_activities import snapshot
from app.shared_activities.entitlement import activity_cutoff
from app.strava import snapshots, strava_client, synchronisation as sync

NOW = datetime.now(timezone.utc).replace(microsecond=0)
SECRET = "progressive-test-secret"


@pytest.fixture
def app(monkeypatch, tmp_path):
    """Provide one isolated rider and private file storage."""
    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", "sqlite://")
    monkeypatch.setattr(Config, "SECRET_KEY", SECRET)
    monkeypatch.setattr(sync, "_now", lambda: NOW)
    monkeypatch.delenv("ACTIVITY_SNAPSHOT_BUCKET", raising=False)
    monkeypatch.setenv("ACTIVITY_SNAPSHOT_DIRECTORY", str(tmp_path))
    application = create_app()
    with application.app_context():
        db.create_all()
        db.session.add(User(id=1, username="test", email="test@example.test",
                            strava_access_token="test-access", strava_refresh_token="test-refresh",
                            token_expiry_epoch=int(NOW.timestamp()) + 3600))
        db.session.commit()
        yield application


def _job():
    """Reload the current job after a simulated process restart."""
    db.session.remove()
    return db.session.get(ActivitySyncJob, 1)


def _ride(activity_id, epoch):
    """Return a synthetic Strava ride at an exact UTC epoch."""
    return {"id": activity_id, "start_date": datetime.fromtimestamp(epoch, timezone.utc).isoformat()}


def _auth(*, expired=False, token_type="access"):
    """Build a test access or rejected token for the Flask adapter."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=-1 if expired else 60)
    return {"Authorization": "Bearer " + jwt.encode(
        {"user_id": 1, "exp": expires, "type": token_type}, SECRET, algorithm="HS256"
    )}


def test_new_user_resumes_pages_and_imports_history(app, monkeypatch):
    """BS02: persist recent rides first, finish coverage, and resume older work."""
    monkeypatch.setattr(strava_client, "PAGE_SIZE", 2)
    assert sync.enqueue(1)["syncing"]
    first = _job()
    assert first.to_epoch - first.from_epoch == 30 * 86400
    start, end = first.from_epoch, first.to_epoch
    fetch = Mock(side_effect=[
        [_ride(2, start), _ride(3, end)],
        [_ride(4, start + 1)],
        [],
    ])
    monkeypatch.setattr(strava_client, "fetch_activity_page", fetch)
    assert sync.process_one("test", "test")
    assert SyncHistory.query.count() == 0
    assert db.session.get(Activity, 2) and not db.session.get(Activity, 3)
    assert _job().page == 2
    assert sync.process_one("test", "test")
    second = _job()
    assert second.kind == "history" and second.to_epoch == start
    assert second.revision == 2 and second.recent_watermark == end
    assert sync.process_one("test", "test")
    assert db.session.get(User, 1).last_synch_epoch == end
    assert SyncHistory.query.count() == 1
    assert SyncHistory.query.one().to_date.replace(tzinfo=timezone.utc) == NOW
    assert fetch.call_args_list[1].args[-1] == 2


def test_retry_keeps_cursor_and_failed_window_uncovered(app, monkeypatch):
    """BS03: a failed continuation neither advances the cursor nor marks coverage."""
    monkeypatch.setattr(strava_client, "PAGE_SIZE", 1)
    sync.enqueue(1)
    job = _job()
    response = Mock(side_effect=[
        [_ride(1, job.to_epoch - 1)],
        strava_client.StravaFailure("rate_limit", 900),
        [],
    ])
    monkeypatch.setattr(strava_client, "fetch_activity_page", response)
    sync.process_one("test", "test")
    sync.process_one("test", "test")
    job = _job()
    assert job.status == "retry" and job.page == 2
    assert job.next_attempt.replace(tzinfo=timezone.utc) == NOW + timedelta(seconds=900)
    assert SyncHistory.query.count() == 0 and Activity.query.count() == 1
    assert not sync.process_one("test", "test")
    monkeypatch.setattr(sync, "_now", lambda: NOW + timedelta(minutes=15))
    assert sync.process_one("test", "test")
    assert SyncHistory.query.count() == 1 and Activity.query.count() == 1


def test_failed_persistence_rolls_back_the_page(app, monkeypatch):
    """A page that fails after adding a row is retried without recording coverage."""
    sync.enqueue(1)
    monkeypatch.setattr(strava_client, "fetch_activity_page", lambda *args: [])

    def fail(user, job, rows):
        db.session.add(Activity(id=9, user_id=user.id, start_date=NOW.replace(tzinfo=None)))
        db.session.flush()
        raise ValueError

    monkeypatch.setattr(sync, "_persist_rows", fail)
    sync.process_one("test", "test")
    assert Activity.query.count() == SyncHistory.query.count() == 0
    assert _job().status == "retry" and _job().page == 1


def test_manual_cap_and_recent_watermark_are_independent_of_history(app):
    """Manual sync stops at one calendar year and other callers share its slot."""
    now_epoch = int(NOW.timestamp())
    db.session.add(ActivitySyncJob(user_id=1, status="complete", from_epoch=0, to_epoch=1,
                                  next_attempt=NOW, recent_watermark=now_epoch - 600 * 86400))
    db.session.commit()
    sync.enqueue(1, "manual")
    job = _job()
    assert job.from_epoch == int(NOW.replace(year=NOW.year - 1).timestamp())
    sync.enqueue(1, "historical", (10, 20))
    job = _job()
    assert job.kind == "recent" and job.to_epoch == now_epoch
    assert job.recent_watermark == now_epoch - 600 * 86400


def test_revoke_blocks_automatic_until_reconnect(app, monkeypatch):
    """BS04: show cached rides, block repeated background requests and allow reconnection."""
    client = app.test_client()
    db.session.add(Activity(id=2, user_id=1, start_date=NOW.replace(tzinfo=None)))
    db.session.commit()
    assert snapshots.seed(1)
    fetch = Mock(side_effect=strava_client.StravaFailure("reconnect"))
    refresh = Mock(side_effect=strava_client.StravaFailure("reconnect"))
    monkeypatch.setattr(strava_client, "fetch_activity_page", fetch)
    monkeypatch.setattr(strava_client, "refresh_credentials", refresh)
    sync.enqueue(1)
    sync.process_one("test", "test")
    assert sync.status(1)["reconnect"] and not sync.status(1)["syncing"]
    assert client.get("/strava/activities/snapshot", headers=_auth()).json["activities"][0]["id"] == 2
    assert client.get("/strava/activities/?limit=50", headers=_auth()).json["activities"][0]["id"] == 2
    sync.enqueue(1)
    assert not sync.process_one("test", "test")
    assert fetch.call_count == refresh.call_count == 1
    assert SyncHistory.query.count() == 0
    assert sync.connect(1, lambda: dict(access_token="again", refresh_token="again",
                                        expires_at=int(NOW.timestamp()) + 3600))["success"]
    assert sync.status(1)["syncing"]


def test_snapshot_noop_invalidated_and_entitlement_safety(app, monkeypatch):
    """BS01 and FR07: retain unchanged bytes, publish edits, and protect older rows."""
    db.session.add_all([
        Activity(id=2, user_id=1, start_date=NOW.replace(tzinfo=None), rpe=4),
        Activity(id=3, user_id=1, start_date=NOW.replace(year=2021, tzinfo=None)),
    ])
    user = db.session.get(User, 1)
    user.membership_type = MembershipType.PREMIUM_TIER
    db.session.commit()
    assert snapshots.seed(1)
    wrap = Mock(wraps=snapshot.write)
    monkeypatch.setattr(snapshot, "write", wrap)
    assert snapshots.seed(1)
    wrap.assert_not_called()
    user.membership_type = MembershipType.FREE_TIER
    db.session.commit()
    client = app.test_client()
    assert [row["id"] for row in client.get("/strava/activities/snapshot", headers=_auth()).json["activities"]] == [2]
    assert client.get("/strava/activity/3", headers=_auth()).status_code == 404
    assert Activity.query.count() == 2
    assert client.get("/strava/activities/snapshot", headers=_auth(expired=True)).status_code == 401
    assert client.get("/strava/activities/snapshot", headers=_auth(token_type="refresh")).status_code == 401
    db.session.get(Activity, 2).rpe = 6
    db.session.get(ActivitySnapshotWork, 1).next_attempt = NOW
    db.session.commit()
    assert snapshots.process_one()
    wrap.assert_called_once()
    assert snapshot.read(1, lambda: pytest.fail("recent-only hit queried membership"))["activities"][0]["rpe"] == 6
    assert snapshot.read(2, lambda: "PREMIUM_TIER") is None


def test_empty_success_does_not_rewrite_snapshot(app, monkeypatch):
    """BS01: an empty window still advances successful coverage and the watermark."""
    assert snapshots.seed(1)
    sync.enqueue(1)
    monkeypatch.setattr(strava_client, "fetch_activity_page", lambda *args: [])
    assert sync.process_one("test", "test")
    assert SyncHistory.query.count() == 1
    assert _job().recent_watermark == int(NOW.timestamp())
    write = Mock()
    monkeypatch.setattr(snapshot, "write", write)
    assert snapshots.seed(1)
    write.assert_not_called()


def test_strava_exclusive_boundaries(monkeypatch):
    """The outbound query includes the first UTC second in a half-open window."""
    response = Mock(status_code=200)
    response.json.return_value = []
    request = Mock(return_value=response)
    monkeypatch.setattr(strava_client.requests, "request", request)
    assert strava_client.fetch_activity_page("test", 100, 200, 2) == []
    assert request.call_args.kwargs["params"] == {
        "after": 99, "before": 200, "page": 2, "per_page": strava_client.PAGE_SIZE,
    }
    assert activity_cutoff("FREE_TIER", datetime(2024, 2, 29)) == datetime(2023, 2, 28)


def test_oauth_queues_recent_work_with_signed_owner_and_required_scope(app, monkeypatch):
    """An OAuth callback needs signed owner state and the complete activity scope."""
    from urllib.parse import parse_qs, urlsplit

    client = app.test_client()
    supplied = Mock(return_value={
        "access_token": "fixture", "refresh_token": "fixture",
        "expires_at": int(NOW.timestamp()) + 3600,
    })
    monkeypatch.setattr(strava_client, "exchange_authorization_code", supplied)
    url = client.get("/strava/oauth-url", headers=_auth()).json["url"]
    state = parse_qs(urlsplit(url).query)["state"][0]
    query = {"code": "fake", "state": state, "scope": "read,activity:read_all"}
    results = [
        client.get("/strava/strava_auth/", query_string={**query, "state": "1"}),
        client.get("/strava/strava_auth/", query_string={**query, "scope": "activity:read"}),
    ]
    assert all("/profile/strava-connect?" in response.location for response in results)
    supplied.assert_not_called()
    response = client.get("/strava/strava_auth/", query_string=query)
    assert "/activities?strava_connected=true" in response.location
    supplied.assert_called_once()
    assert sync.status(1)["syncing"]
