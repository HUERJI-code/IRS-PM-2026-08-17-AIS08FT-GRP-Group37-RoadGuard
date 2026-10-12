"""Health reports only the implemented application/database foundation."""

import sqlite3

from fastapi import APIRouter, Request

from roadguard.database import DatabaseStateError, read_revision
from roadguard.errors import AppError
from roadguard.schemas import ErrorResponse, HealthResponse


router = APIRouter(tags=["Infrastructure"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse, "description": "Infrastructure database is unavailable."}},
    summary="Check application and SQLite infrastructure",
)
def health(request: Request) -> HealthResponse:
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise AppError("database_unavailable", "The infrastructure database is unavailable.", 503)
    try:
        with database.connect() as connection:
            revision = read_revision(connection)
    except (sqlite3.Error, OSError, DatabaseStateError) as exc:
        raise AppError("database_unavailable", "The infrastructure database is unavailable.", 503) from exc
    return HealthResponse(status="ok", database="ok", api_version="v1", input_revision=revision)
