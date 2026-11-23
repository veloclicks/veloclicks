"""PostgreSQL adapter for accounts used by the standalone Auth Lambda."""

from psycopg2.errors import UniqueViolation

from shared_auth.service import Credentials, DuplicateUser


class PostgresUserRepository:
    """Read and write credentials using the Lambda's connection provider."""

    def __init__(self, get_connection):
        self.get_connection = get_connection

    def by_username(self, username: str) -> Credentials | None:
        """Look up an account by exact username."""
        return self._find("username = %s", (username,))

    def by_email(self, email: str) -> Credentials | None:
        """Look up an account by exact email."""
        return self._find("email = %s", (email,))

    def by_username_or_email(self, identifier: str) -> Credentials | None:
        """Look up the account matching either supported login identifier."""
        return self._find("email = %s OR username = %s", (identifier, identifier))

    def by_id(self, user_id: int) -> Credentials | None:
        """Retrieve current credentials by the refresh token subject."""
        return self._find("id = %s", (user_id,))

    def _find(self, condition: str, values: tuple) -> Credentials | None:
        """Run an internal fixed predicate with parameterised user values."""
        with self.get_connection().cursor() as cursor:
            cursor.execute(
                f"SELECT id, email, password_hash FROM vc_user WHERE {condition}",
                values,
            )
            row = cursor.fetchone()
        return Credentials(**row) if row else None

    def create(self, username: str, email: str, password_hash: str,
               firstname: str | None, lastname: str | None) -> None:
        """Insert an account into the existing table using its membership default."""
        try:
            with self.get_connection().cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO vc_user (username, email, password_hash, firstname, lastname)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (username, email, password_hash, firstname, lastname),
                )
        except UniqueViolation as error:
            if self.by_username(username):
                raise DuplicateUser("username") from error
            if self.by_email(email):
                raise DuplicateUser("email") from error
            raise
