from fastapi import APIRouter

from app.api.v0.routers import dev
from app.core.config import settings as app_settings

api_v0_router = APIRouter(prefix=app_settings.api_v0_prefix)
api_v0_router.include_router(dev.router)
