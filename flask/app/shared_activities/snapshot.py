"""Read and write owner-scoped snapshot objects without importing database code."""

from collections.abc import Callable
import hashlib
import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile

from .entitlement import PREMIUM, activity_cutoff, utc_naive


@lru_cache(maxsize=1)
def _s3():
    """Reuse a client with short timeouts suitable for first-page reads."""
    import boto3
    from botocore.config import Config

    return boto3.client("s3", config=Config(connect_timeout=2, read_timeout=3,
                                            retries={"total_max_attempts": 2}))


def _key(user_id: int) -> str:
    """Derive a storage key from the verified user ID only."""
    return f"activity-snapshots/{user_id}.json"


def storage_configured() -> bool:
    """Return whether this runtime has a shared snapshot destination."""
    return bool(os.getenv("ACTIVITY_SNAPSHOT_BUCKET") or os.getenv("ACTIVITY_SNAPSHOT_DIRECTORY"))


def _read(user_id: int) -> bytes:
    """Read one bounded object from S3 or the local Docker volume."""
    bucket = os.getenv("ACTIVITY_SNAPSHOT_BUCKET")
    if bucket:
        from botocore.exceptions import ClientError

        try:
            with _s3().get_object(Bucket=bucket, Key=_key(user_id))["Body"] as body:
                return body.read(262145)
        except ClientError as error:
            if error.response["Error"]["Code"] in ("NoSuchKey", "404", "AccessDenied"):
                raise FileNotFoundError from error
            raise
    directory = os.getenv("ACTIVITY_SNAPSHOT_DIRECTORY")
    if not directory:
        raise FileNotFoundError
    with (Path(directory) / _key(user_id)).open("rb") as body:
        return body.read(262145)


def encode(user_id: int, activities: list[dict]) -> tuple[bytes, str]:
    """Encode deterministic JSON and a content digest for no-op detection."""
    body = json.dumps({"user_id": user_id, "activities": activities},
                      sort_keys=True, separators=(",", ":")).encode()
    return body, hashlib.sha256(body).hexdigest()


def stored_digest(user_id: int) -> str | None:
    """Hash the stored bytes so a seed can restore missing or damaged objects."""
    try:
        return hashlib.sha256(_read(user_id)).hexdigest()
    except FileNotFoundError:
        return None


def write(user_id: int, body: bytes) -> None:
    """Replace one private object atomically in the configured adapter."""
    bucket = os.getenv("ACTIVITY_SNAPSHOT_BUCKET")
    if bucket:
        _s3().put_object(Bucket=bucket, Key=_key(user_id), Body=body,
                         ContentType="application/json", ServerSideEncryption="AES256")
        return
    path = Path(os.environ["ACTIVITY_SNAPSHOT_DIRECTORY"]) / _key(user_id)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temp = Path(file.name)
        file.write(body)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def read(user_id: int, current_tier: Callable[[], str | None]) -> dict | None:
    """Return a valid snapshot, checking live tier only if a row is restricted."""
    try:
        raw = _read(user_id)
        if len(raw) > 262144:
            return None
        payload = json.loads(raw)
        rows = payload["activities"]
        if payload["user_id"] != user_id or not isinstance(rows, list) or len(rows) > 50:
            return None
        seen = set()
        dated = []
        for row in rows:
            if row["user_id"] != user_id or type(row["id"]) is not int or row["id"] in seen:
                return None
            seen.add(row["id"])
            dated.append((row, utc_naive(datetime.fromisoformat(row["start_date"]))))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    cutoff = activity_cutoff("FREE_TIER")
    if any(date < cutoff for _, date in dated):
        if current_tier() != PREMIUM:
            rows = [row for row, date in dated if date >= cutoff]
    return {"activities": rows}
