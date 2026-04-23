from fastapi import APIRouter

from app.api.client.routers import bind

client_router = APIRouter(prefix="/api/client/v1")
client_router.include_router(bind.router)

