from fastapi import APIRouter, Depends

from app.api.v1.routers import auth, backups, configs, endpoints, mesh, nodes, settings, system
from app.core.config import settings as app_settings
from app.api.v1.deps import require_current_user

api_router = APIRouter(prefix=app_settings.api_v1_prefix)

api_router.include_router(auth.router)
protected = [Depends(require_current_user)]
api_router.include_router(configs.router, dependencies=protected)
api_router.include_router(nodes.router, dependencies=protected)
api_router.include_router(mesh.router, dependencies=protected)
api_router.include_router(endpoints.router, dependencies=protected)
api_router.include_router(settings.router, dependencies=protected)
api_router.include_router(backups.router, dependencies=protected)
api_router.include_router(system.router)
api_router.include_router(system.events_router)
