from typing import Annotated
import hmac

from fastapi import Depends, Header, Request, Security
from fastapi.security import APIKeyCookie

from roadguard.errors import AppError
from .models import Account
from .service import SESSION_COOKIE

cookie = APIKeyCookie(name=SESSION_COOKIE, auto_error=False)


def validate_origin(request: Request):
    origin = request.headers.get("origin")
    if origin is not None and origin not in request.app.state.settings.auth_allowed_origins:
        raise AppError("forbidden_origin", "This origin is not allowed.", 403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise AppError("forbidden_origin", "Cross-site requests are not allowed.", 403)


def current_user(request: Request, token: Annotated[str | None, Security(cookie)] = None,
                 csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token", description="Required for writes; returned by /auth/login or /auth/session.")] = None) -> Account:
    session = request.app.state.auth_service.session(token)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        validate_origin(request)
        if not hmac.compare_digest(csrf_token or "", session.csrf_token):
            raise AppError("csrf_failed", "Reload your session before submitting.", 403)
    request.state.account = session.user
    return session.user


# Deny by default, including any future business route until explicitly classified.
PERMISSIONS = {
    ("GET", "/assistant/change-requests"): {"dispatcher"},
    ("POST", "/assistant/change-requests"): {"dispatcher"},
    ("GET", "/assistant/change-requests/{change_id}"): {"dispatcher"},
    ("POST", "/assistant/change-requests/{change_id}/confirm"): {"dispatcher"},
    ("POST", "/assistant/change-requests/{change_id}/cancel"): {"dispatcher"},
    ("POST", "/assistant/change-requests/{change_id}/replan"): {"dispatcher"},
    ("GET", "/assistant/status"): {"dispatcher"},
    ("POST", "/assistant/query"): {"dispatcher"},
    ("POST", "/assistant/knowledge/search"): {"dispatcher"},
    ("GET", "/demo/scenarios"): {"inspector"},
    ("POST", "/demo/assessments"): {"inspector"},
    ("POST", "/inspections"): {"inspector"},
    ("GET", "/inspections"): {"dispatcher"},
    ("GET", "/inspections/{inspection_id}"): {"inspector", "crew", "dispatcher"},
    ("GET", "/inspections/{inspection_id}/image"): {"inspector", "crew", "dispatcher"},
    ("POST", "/inspections/{inspection_id}/review"): {"dispatcher"},
    ("GET", "/tasks"): {"dispatcher"},
    ("GET", "/tasks/snapshot"): {"dispatcher"},
    ("GET", "/tasks/{task_id}"): {"crew", "dispatcher"},
    ("PATCH", "/tasks/{task_id}"): {"crew", "dispatcher"},
    ("GET", "/crews"): {"dispatcher"},
    ("PATCH", "/crews/{crew_id}"): {"dispatcher"},
    ("GET", "/route-plans/latest"): {"dispatcher"},
    ("GET", "/route-plans/{plan_id}"): {"dispatcher"},
    ("POST", "/route-plans/recalculate"): {"dispatcher"},
    ("GET", "/crew/workspace"): {"crew"},
}


def access_control(request: Request, account: Annotated[Account, Depends(current_user)]):
    path = request.scope["route"].path.removeprefix("/api/v1")
    if account.role not in PERMISSIONS.get((request.method, path), set()):
        raise AppError("forbidden", "This account cannot perform that action.", 403)
    request.state.account = account
