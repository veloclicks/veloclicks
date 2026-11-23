"""Exercise keyset pagination and the legacy activity-list contract."""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import jwt

from app import create_app
from app.models import Activity, User, db

SECRET = "activity-pagination-test-key"
URL = "/strava/activities/"


class ActivityPaginationTest(unittest.TestCase):
    """Use isolated stored rides to test response shapes and continuation rules."""

    def setUp(self):
        with patch.multiple("app.config.Config", SQLALCHEMY_DATABASE_URI="sqlite://",
                            SECRET_KEY=SECRET):
            self.app = create_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            db.session.add_all(User(id=i, username=f"rider{i}", email=f"rider{i}@example.test")
                               for i in (1, 2, 3))
            db.session.commit()

    def _add_rides(self, count, user_id=1, first_id=1, date=None):
        """Seed rides with the same timestamp to exercise the cursor tie-breaker."""
        start = date or datetime(2026, 1, 1)
        with self.app.app_context():
            db.session.add_all(Activity(id=i, user_id=user_id, start_date=start)
                               for i in range(first_id, first_id + count))
            db.session.commit()

    def _request(self, user_id=1, **params):
        """Send a signed request and return the Flask response."""
        token = jwt.encode({"user_id": user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=1)},
                           SECRET, algorithm="HS256")
        return self.client.get(URL, query_string=params, headers={"Authorization": f"Bearer {token}"})

    def test_first_page_sizes_and_legacy_response(self):
        """Small histories return at most 50 with no unnecessary continuation."""
        self._add_rides(12, user_id=2)
        self._add_rides(50, user_id=3, first_id=100)
        self._add_rides(1, user_id=3, first_id=999, date=datetime(2024, 1, 1))
        for user_id, expected in ((1, 0), (2, 12), (3, 50)):
            with self.subTest(user_id=user_id):
                response = self._request(user_id, years="2025,2026", limit=50)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json["activities"]), expected)
                self.assertIsNone(response.json["next_cursor"])
        legacy = self._request(3, years="2025,2026")
        self.assertEqual(legacy.status_code, 200)
        self.assertIsInstance(legacy.json, list)
        self.assertEqual(len(legacy.json), 50)

    def test_walk_500_activities_with_identical_dates(self):
        """All tied rides appear once, in a stable order, over ten requests."""
        self._add_rides(500)
        self._add_rides(1, user_id=2, first_id=501)
        cursor = None
        found = []
        for index in range(10):
            params = {"years": "2025,2026", "limit": 50}
            if cursor:
                params["cursor"] = cursor
            response = self._request(**params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json["activities"]), 50)
            found.extend(row["id"] for row in response.json["activities"])
            cursor = response.json["next_cursor"]
            self.assertEqual(bool(cursor), index < 9)
        self.assertEqual(found, list(range(500, 0, -1)))

    def test_invalid_cursor_and_limit(self):
        """Reject tampered cursors, other users and date ranges, and bad limits."""
        self._add_rides(2)
        cursor = self._request(years="2026", limit=1).json["next_cursor"]
        for user_id, params in (
            (1, {"years": "2026", "limit": 1, "cursor": cursor[:-1]}),
            (2, {"years": "2026", "limit": 1, "cursor": cursor}),
            (1, {"years": "2025", "limit": 1, "cursor": cursor}),
            (1, {"cursor": cursor}),
            (1, {"limit": 0}),
            (1, {"limit": 51}),
            (1, {"limit": "invalid"}),
        ):
            with self.subTest(user_id=user_id, params=params):
                self.assertEqual(self._request(user_id, **params).status_code, 400)

    def test_continuation_preserves_default_date_window(self):
        """A continuation keeps the same rolling range as its first page."""
        start = datetime(2026, 6, 1)
        self._add_rides(2, date=start)
        with patch("app.strava.routes.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2026, 11, 23)
            first = self._request(limit=1).json
            clock.now.return_value = datetime(2027, 1, 1)
            second = self._request(limit=1, cursor=first["next_cursor"]).json
        self.assertEqual([row["id"] for row in second["activities"]], [1])
        self.assertIsNone(second["next_cursor"])
