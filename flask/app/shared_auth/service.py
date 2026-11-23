"""Authenticate users and issue tokens independently of HTTP and database drivers."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from .verification import access_token_user_id as access_token_user_id


@dataclass(frozen=True)
class Credentials:
    """User fields needed to authenticate and issue tokens."""

    id: int
    email: str
    password_hash: str | None


class DuplicateUser(Exception):
    """A username or email conflicts with an existing account."""


class UserRepository(Protocol):
    """Account lookups and writes required by authentication."""

    def by_username(self, username: str) -> Credentials | None: ...
    def by_email(self, email: str) -> Credentials | None: ...
    def by_username_or_email(self, identifier: str) -> Credentials | None: ...
    def by_id(self, user_id: int) -> Credentials | None: ...
    def create(self, username: str, email: str, password_hash: str,
               firstname: str | None, lastname: str | None) -> None: ...


class AuthService:
    """Apply shared credential rules with the entry point's historical token policy."""

    def __init__(self, users: UserRepository, secret: str,
                 access_minutes: int = 30, refresh_days: int = 30):
        self.users = users
        self.secret = secret
        self.access_minutes = access_minutes
        self.refresh_days = refresh_days

    def login(self, identifier: str, password: str, *, legacy: bool = False) -> str | None:
        """Return a signed access token if the supplied credentials match."""
        user = (self.users.by_username(identifier) if legacy
                else self.users.by_username_or_email(identifier))
        if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
            return None
        return self._access_token(user, legacy=legacy)

    def register(self, username: str, email: str, password: str,
                 firstname: str | None, lastname: str | None, *,
                 legacy: bool = False) -> None:
        """Create an account or raise DuplicateUser with the conflicting field."""
        if legacy:
            if self.users.by_username(username):
                raise DuplicateUser("username")
            existing = self.users.by_email(email)
        else:
            # The standalone API historically rejects emails matching either field.
            existing = self.users.by_username_or_email(email)
        if existing:
            raise DuplicateUser("email")
        self.users.create(username, email, generate_password_hash(password), firstname, lastname)

    def refresh(self, token: str) -> str | None:
        """Exchange a valid standalone refresh token for a new access token."""
        try:
            payload = jwt.decode(token, self.secret, algorithms=["HS256"],
                                 options={"require": ["exp", "sub"]})
        except jwt.InvalidTokenError:
            return None
        # PyJWT 2.8 and existing tokens use an integer subject.
        if payload.get("type") != "refresh" or type(payload["sub"]) is not int:
            return None
        user = self.users.by_id(payload["sub"])
        return self._access_token(user) if user else None

    def _access_token(self, user: Credentials, *, legacy: bool = False) -> str:
        """Preserve legacy Flask claims and the standalone token's frontend claims."""
        now = datetime.now(timezone.utc)
        minutes = 60 if legacy else self.access_minutes
        payload = {
            "user_id": user.id,
            "email": user.email,
            "exp": now + timedelta(minutes=minutes),
        }
        if not legacy:
            payload.update(sub=user.id, type="access", iat=now)
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def issue_refresh_token(self, user: Credentials) -> str:
        """Issue the historical standalone refresh token format for service consumers."""
        now = datetime.now(timezone.utc)
        return jwt.encode({
            "sub": user.id, "user_id": user.id, "type": "refresh",
            "iat": now, "exp": now + timedelta(days=self.refresh_days),
        }, self.secret, algorithm="HS256")
