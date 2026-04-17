from fastapi import APIRouter

from app.api.v1.routers import auth, backups, configs, endpoints, mesh, nodes, settings, system
from app.core.config import settings as app_settings

api_router = APIRouter(prefix=app_settings.api_v1_prefix)

api_router.include_router(auth.router)
api_router.include_router(configs.router)
api_router.include_router(nodes.router)
api_router.include_router(mesh.router)
api_router.include_router(endpoints.router)
api_router.include_router(endpoints.download_router)
api_router.include_router(settings.router)
api_router.include_router(backups.router)
api_router.include_router(system.router)
api_router.include_router(system.events_router)
