from fastapi import APIRouter

from app.api.client.routers import bind, update

client_router = APIRouter(prefix="/api/client/v1")
client_router.include_router(bind.router)
client_router.include_router(update.router)

