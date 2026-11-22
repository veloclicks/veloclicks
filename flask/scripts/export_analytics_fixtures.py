"""Export recent cycling activity streams for deterministic analytics regression tests.

Run from repository root:
  docker compose exec -T flask python scripts/export_analytics_fixtures.py > analytics-fixtures.json

Uses the existing local DB and Strava token; no database writes intended.
Do not commit the output: it contains personal exercise measurements.
"""
import json
import sys
from datetime import datetime, timedelta, timezone

from app import create_app
from app.models import Activity, User
from app.strava.service import get_activity_streams, get_activity_laps

DAYS = 90
LIMIT = 30
STREAM_TYPES = ["time", "watts", "heartrate", "cadence", "altitude", "velocity_smooth", "moving", "grade_smooth"]


def main():
    app = create_app()
    with app.app_context():
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=DAYS)
        rides = (Activity.query
                 .filter(Activity.start_date_local >= since)
                 .filter(Activity.type.in_(["Ride", "VirtualRide"]))
                 .order_by(Activity.start_date_local.desc())
                 .limit(LIMIT).all())
        if not rides:
            raise RuntimeError("No rides found in local DB in last 90 days")
        output = {"schema_version": "fixtures-1", "exported_at": datetime.now(timezone.utc).isoformat(),
                  "activities": []}
        for ride in rides:
            print(f"Fetching {ride.start_date_local} {ride.name} ({ride.id})", file=sys.stderr)
            try:
                streams = get_activity_streams(ride.user_id, ride.id, STREAM_TYPES)
                laps = get_activity_laps(ride.user_id, ride.id)
            except Exception as exc:
                print(f"Skipping {ride.id}: {exc}", file=sys.stderr)
                continue
            if not streams or "time" not in streams:
                print(f"Skipping {ride.id}: no time stream", file=sys.stderr)
                continue
            user = User.query.get(ride.user_id)
            metadata = ride.to_dict()
            metadata.pop("user_id", None)
            # Preserve sample alignment and original stream metadata. No GPS coordinates,
            # athlete name, tokens, account identifiers or database secrets exported.
            output["activities"].append({
                "activity": metadata,
                "athlete": {"ftp_w": ride.ftp or (user.ftp if user else None),
                            "max_hr_bpm": user.max_heart_rate if user else None},
                "streams": {k: v for k, v in streams.items() if k in STREAM_TYPES},
                "laps": laps or [],
            })
        if not output["activities"]:
            raise RuntimeError("No activities with accessible streams; check Strava connection")
        json.dump(output, sys.stdout, default=str, separators=(",", ":"))
        sys.stdout.write("\n")
        print(f"Exported {len(output['activities'])} rides", file=sys.stderr)


if __name__ == "__main__":
    main()
