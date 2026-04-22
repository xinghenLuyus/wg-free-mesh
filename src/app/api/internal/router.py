from fastapi import APIRouter

from app.api.internal.routers import emqx

internal_router = APIRouter(prefix="/api/internal")
internal_router.include_router(emqx.router)
