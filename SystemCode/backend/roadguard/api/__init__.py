"""Central route registry; future domain routers register here."""

from fastapi import APIRouter, Depends
from roadguard.auth.api import router as auth_router, crew_router as workspace_router
from roadguard.auth.dependencies import access_control

from roadguard.api.health import router as health_router
from roadguard.api.demo import router as demo_router
from roadguard.api.workflow import router as workflow_router
from roadguard.crews.api import router as crews_router
from roadguard.routing.api import router as routing_router


def create_api_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    router.include_router(health_router)
    router.include_router(auth_router)
    router.include_router(workspace_router)
    for domain_router in (demo_router, workflow_router, crews_router, routing_router):
        router.include_router(domain_router, dependencies=[Depends(access_control)],
                              responses={401: {"description": "Authentication required"}, 403: {"description": "Forbidden"}})
    return router
