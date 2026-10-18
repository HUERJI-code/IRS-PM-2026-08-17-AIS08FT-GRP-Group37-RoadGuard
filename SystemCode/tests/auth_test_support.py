"""Explicit identities for legacy domain tests; auth tests use the real app/login.

No authentication bypass exists in production settings. These dependency overrides
keep domain-focused tests independent of password hashing and browser sessions.
"""
from fastapi import Request
from roadguard.auth.dependencies import current_user
from roadguard.auth.models import Account
from roadguard.main import create_app as real_create_app


def create_app(settings=None):
    app = real_create_app(settings)

    def test_identity(request: Request):
        role = "inspector" if request.url.path.startswith("/api/v1/demo/") or (
            request.method == "POST" and request.url.path == "/api/v1/inspections") else "dispatcher"
        user = Account(user_id=("1" if role == "inspector" else "2") * 32,
                       username="test-" + role, display_name="Test " + role, role=role, crew_id=None)
        with request.app.state.database.transaction() as connection:
            connection.execute("INSERT OR IGNORE INTO auth_users VALUES (?,?,?,?,?, ?,1,0)",
                               (user.user_id, user.username, user.display_name, role, None, "not-a-login-hash"))
        return user

    app.dependency_overrides[current_user] = test_identity
    return app
