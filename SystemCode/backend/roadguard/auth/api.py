from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from roadguard.database import read_revision
from roadguard.schemas import ErrorResponse
from roadguard.schemas.workflow import TaskRecord
from .access import active_actor, latest_ga
from .dependencies import access_control, current_user, validate_origin
from .models import Account, CrewWorkspacePlan, CrewWorkspaceResponse, LoginRequest, LogoutResponse, SessionResponse
from .service import SESSION_COOKIE, SESSION_SECONDS

ERRORS = {code: {"model": ErrorResponse} for code in (401, 403, 429, 503)}
router = APIRouter(prefix="/auth", tags=["Authentication"], responses=ERRORS)
crew_router = APIRouter(tags=["Crew workspace"], dependencies=[Depends(access_control)], responses=ERRORS)


@router.post("/login", response_model=SessionResponse)
def login(request: Request, response: Response, payload: LoginRequest):
    validate_origin(request)
    token, session = request.app.state.auth_service.login(payload.username, payload.password.get_secret_value(),
        request.client.host if request.client else "unknown", request.cookies.get(SESSION_COOKIE))
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=request.app.state.settings.auth_cookie_secure,
                        samesite="strict", max_age=SESSION_SECONDS, path="/")
    response.headers["Cache-Control"] = "no-store"
    return session


@router.get("/session", response_model=SessionResponse)
def session(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return request.app.state.auth_service.session(request.cookies.get(SESSION_COOKIE))


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response, account: Annotated[Account, Depends(current_user)]):
    request.app.state.auth_service.logout(request.cookies[SESSION_COOKIE])
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=request.app.state.settings.auth_cookie_secure, samesite="strict")
    response.headers["Cache-Control"] = "no-store"
    return LogoutResponse()


@crew_router.get("/crew/workspace", response_model=CrewWorkspaceResponse,
                 summary="The authenticated crew's latest GA route and current tasks only")
def workspace(request: Request):
    account = request.state.account
    with request.app.state.database.connect() as connection:
        active_actor(connection, account)
        crew = request.app.state.crew_service._get(connection, account.crew_id)
        plan = latest_ga(connection)
        scoped = None
        tasks = []
        if plan:
            route = next((r for r in plan.crew_routes if r.crew_id == account.crew_id), None)
            scoped = CrewWorkspacePlan(**plan.model_dump(include=set(CrewWorkspacePlan.model_fields) - {"crew_routes"}),
                                       crew_routes=[route] if route else [])
            for stop in route.stops if route else []:
                row = connection.execute("SELECT record_json FROM tasks WHERE task_id=?", (stop.task_id,)).fetchone()
                if row:
                    tasks.append(TaskRecord.model_validate_json(row[0]))
        return CrewWorkspaceResponse(crew=crew, plan=scoped, tasks=tasks, input_revision=read_revision(connection))
