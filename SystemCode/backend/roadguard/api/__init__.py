"""Central route registry; future domain routers register here."""

from fastapi import APIRouter

from roadguard.api.health import router as health_router
from roadguard.api.demo import router as demo_router


def create_api_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    router.include_router(health_router)
    router.include_router(demo_router)
    return router
