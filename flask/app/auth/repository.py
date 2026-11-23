"""SQLAlchemy account storage for the shared authentication service."""

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.models import User, db
from app.shared_auth.service import Credentials, DuplicateUser


class FlaskUserRepository:
    """Translate ORM user records to the auth service's credential contract."""

    def by_username(self, username: str) -> Credentials | None:
        """Look up a user by exact username."""
        return _credentials(User.query.filter_by(username=username).first())

    def by_email(self, email: str) -> Credentials | None:
        """Look up a user by exact email."""
        return _credentials(User.query.filter_by(email=email).first())

    def by_username_or_email(self, identifier: str) -> Credentials | None:
        """Look up a user by either identifier as the standalone API does."""
        return _credentials(User.query.filter(
            or_(User.username == identifier, User.email == identifier)
        ).first())

    def by_id(self, user_id: int) -> Credentials | None:
        """Look up the current account for a refresh token."""
        return _credentials(db.session.get(User, user_id))

    def create(self, username: str, email: str, password_hash: str,
               firstname: str | None, lastname: str | None) -> None:
        """Persist an account and map concurrent uniqueness collisions to conflicts."""
        db.session.add(User(username=username, email=email, password_hash=password_hash,
                            firstname=firstname, lastname=lastname))
        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            if self.by_username(username):
                raise DuplicateUser("username") from error
            if self.by_email(email):
                raise DuplicateUser("email") from error
            raise


def _credentials(user: User | None) -> Credentials | None:
    """Expose only fields required by the shared auth logic."""
    return Credentials(user.id, user.email, user.password_hash) if user else None
