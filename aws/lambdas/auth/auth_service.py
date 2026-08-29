import datetime
import os

import jwt
from werkzeug.security import check_password_hash, generate_password_hash


class AuthService:
    def __init__(self, get_connection):
        self._get_conn = get_connection
        self._jwt_secret = os.environ["SECRET_KEY"]
        self._access_token_expiry = int(os.environ.get("ACCESS_TOKEN_EXPIRY_MINUTES", "30"))
        self._refresh_token_expiry = int(os.environ.get("REFRESH_TOKEN_EXPIRY_DAYS", "30"))

    def login(self, username: str, password: str):
        # Accepts username or email — matches existing Flask auth behaviour
        user = self._get_user_by_username_or_email(username)
        if user is None:
            return None
        if not self._check_password(password, user["password_hash"]):
            return None
        return self._make_tokens(user)

    def register(self, username: str, email: str, password: str, firstname=None, lastname=None):
        # Check by email to prevent duplicate accounts
        existing = self._get_user_by_username_or_email(email)
        if existing is not None:
            return None

        # WHY generate_password_hash (werkzeug) and not bcrypt:
        # Flask's User model uses werkzeug's generate_password_hash to store
        # passwords. Using a different algorithm here would produce hashes that
        # Flask cannot verify, breaking login for users registered via this lambda.
        password_hash = generate_password_hash(password)

        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO vc_user (username, email, password_hash, firstname, lastname)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, username, email, firstname, lastname
                """,
                (username, email, password_hash, firstname, lastname),
            )
            user = cur.fetchone()

        return self._make_tokens(user)

    def refresh(self, token: str):
        # Validate that this is a refresh token, not an access token
        try:
            payload = jwt.decode(token, self._jwt_secret, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

        if payload.get("type") != "refresh":
            return None

        user = self._get_user_by_id(payload["sub"])
        if user is None:
            return None
        return self._make_tokens(user)

    def _get_user_by_username_or_email(self, identifier: str):
        conn = self._get_conn()
        with conn.cursor() as cur:
            # WHY vc_user and not users:
            # Flask's User model declares __tablename__ = 'vc_user'. All tables
            # in this project use the vc_ prefix.
            cur.execute(
                "SELECT id, username, email, firstname, lastname, password_hash "
                "FROM vc_user WHERE email = %s OR username = %s",
                (identifier, identifier),
            )
            return cur.fetchone()

    def _get_user_by_id(self, user_id: int):
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, firstname, lastname, password_hash "
                "FROM vc_user WHERE id = %s",
                (user_id,),
            )
            return cur.fetchone()

    def _check_password(self, password: str, password_hash: str) -> bool:
        # WHY werkzeug check_password_hash and not bcrypt:
        # Passwords were hashed by Flask using werkzeug. bcrypt cannot verify
        # werkzeug's pbkdf2 hashes — using it here would reject every valid password.
        return check_password_hash(password_hash, password)

    def _make_tokens(self, user) -> dict:
        # Include both sub and user_id — sub for flask-jwt-extended, user_id for frontend JWT decode
        now = datetime.datetime.utcnow()
        access_payload = {
            "sub": user["id"],
            "user_id": user["id"],
            "email": user["email"],
            "type": "access",
            "iat": now,
            "exp": now + datetime.timedelta(minutes=self._access_token_expiry),
        }
        refresh_payload = {
            "sub": user["id"],
            "user_id": user["id"],
            "type": "refresh",
            "iat": now,
            "exp": now + datetime.timedelta(days=self._refresh_token_expiry),
        }
        return {
            "access_token": jwt.encode(access_payload, self._jwt_secret, algorithm="HS256"),
            "refresh_token": jwt.encode(refresh_payload, self._jwt_secret, algorithm="HS256"),
        }
