"""Passwords stay hashed; opaque sessions are validated against SQLite on every request."""

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from uuid import uuid4

from roadguard.database import Database
from roadguard.errors import AppError
from .models import Account, Role, SessionResponse

SESSION_COOKIE = "roadguard_session"
SESSION_SECONDS = 8 * 60 * 60


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str, salt: bytes | None = None) -> str:
    if not 12 <= len(password) <= 256:
        raise ValueError("Passwords must contain 12 to 256 characters.")
    salt = salt or secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode(), salt=salt, n=2**17, r=8, p=1, maxmem=256 * 1024**2)
    return f"scrypt17${salt.hex()}${value.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        name, salt, value = encoded.split("$")
        if name != "scrypt17" or len(salt) != 32 or len(value) != 128:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**17, r=8, p=1, maxmem=256 * 1024**2)
        return hmac.compare_digest(actual.hex(), value)
    except (ValueError, TypeError):
        return False


def account_from_row(row) -> Account:
    return Account(user_id=row["user_id"], username=row["username"], display_name=row["display_name"],
                   role=row["role"], crew_id=row["crew_id"])


class AuthService:
    def __init__(self, database: Database, crew_ids: list[str]):
        self.database, self.crew_ids = database, crew_ids
        # Unknown accounts take the same expensive verification path.
        self.dummy_hash = hash_password(secrets.token_urlsafe(24))

    def create_user(self, username: str, display_name: str, role: Role, crew_id: str | None, password: str) -> Account:
        username = username.lower()
        if not re.fullmatch(r"[a-z0-9_.-]{1,32}", username) or not 1 <= len(display_name.strip()) <= 64:
            raise ValueError("Invalid account name.")
        if role not in {"inspector", "crew", "dispatcher"} or (role == "crew" and crew_id not in self.crew_ids) or (role != "crew" and crew_id is not None):
            raise ValueError("Invalid account role or crew binding.")
        encoded = hash_password(password)
        user = Account(user_id=uuid4().hex, username=username, display_name=display_name.strip(), role=role, crew_id=crew_id)
        try:
            with self.database.transaction() as connection:
                connection.execute("INSERT INTO auth_users VALUES (?,?,?,?,?,?,1,?)",
                                   (user.user_id, username, user.display_name, role, crew_id, encoded, int(time.time())))
        except sqlite3.IntegrityError:
            raise ValueError("The account already exists.") from None
        return user

    def set_password(self, username: str, password: str):
        encoded = hash_password(password)
        with self.database.transaction() as connection:
            row = connection.execute("SELECT user_id FROM auth_users WHERE username=?", (username.lower(),)).fetchone()
            if not row:
                raise ValueError("The account does not exist.")
            connection.execute("UPDATE auth_users SET password_hash=? WHERE user_id=?", (encoded, row[0]))
            connection.execute("DELETE FROM auth_sessions WHERE user_id=?", (row[0],))

    def _reserve_login(self, username: str, address: str, now: int):
        # Shared across processes; count attempts before doing expensive password work.
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM auth_login_limits WHERE window_start<?", (now - 900,))
            for key, limit in (("account:" + digest(username), 10), ("address:" + digest(address), 60)):
                row = connection.execute("SELECT attempts FROM auth_login_limits WHERE limit_key=?", (key,)).fetchone()
                if row and row[0] >= limit:
                    raise AppError("login_rate_limited", "Too many login attempts. Retry later.", 429)
                connection.execute("INSERT INTO auth_login_limits VALUES (?,?,1) ON CONFLICT(limit_key) DO UPDATE SET attempts=attempts+1", (key, now))

    def login(self, username: str, password: str, address: str, previous_token: str | None = None):
        username, now = username.lower(), int(time.time())
        self._reserve_login(username, address, now)
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM auth_users WHERE username=?", (username,)).fetchone()
        valid = verify_password(password, row["password_hash"] if row else self.dummy_hash)
        if not valid or row is None or not row["enabled"]:
            raise AppError("invalid_credentials", "Username or password is incorrect.", 401)
        token = secrets.token_urlsafe(32)
        expires = now + SESSION_SECONDS
        with self.database.transaction() as connection:
            # Reject a password reset/disable that happened during verification.
            active = connection.execute("SELECT * FROM auth_users WHERE user_id=? AND enabled=1", (row["user_id"],)).fetchone()
            if not active or active["password_hash"] != row["password_hash"]:
                raise AppError("invalid_credentials", "Username or password is incorrect.", 401)
            connection.execute("DELETE FROM auth_sessions WHERE expires_at<=?", (now,))
            if previous_token:
                connection.execute("DELETE FROM auth_sessions WHERE token_hash=?", (digest(previous_token),))
            connection.execute("INSERT INTO auth_sessions VALUES (?,?,?)", (digest(token), row["user_id"], expires))
            connection.execute("DELETE FROM auth_login_limits WHERE limit_key=?", ("account:" + digest(username),))
        return token, SessionResponse(user=account_from_row(active), csrf_token=digest("csrf:" + token), expires_at=expires)

    def session(self, token: str | None) -> SessionResponse:
        if not token or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise AppError("authentication_required", "Sign in to continue.", 401)
        with self.database.connect() as connection:
            row = connection.execute("SELECT u.*,s.expires_at FROM auth_sessions s JOIN auth_users u ON u.user_id=s.user_id "
                                     "WHERE s.token_hash=? AND s.expires_at>? AND u.enabled=1", (digest(token), int(time.time()))).fetchone()
        if not row or (row["role"] == "crew" and row["crew_id"] not in self.crew_ids):
            raise AppError("authentication_required", "Sign in to continue.", 401)
        return SessionResponse(user=account_from_row(row), csrf_token=digest("csrf:" + token), expires_at=row["expires_at"])

    def logout(self, token: str):
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE token_hash=?", (digest(token),))
