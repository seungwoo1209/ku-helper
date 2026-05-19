from fastapi import APIRouter

from app.domains.auth.router import router as auth_router
from app.domains.immediate_send.router import router as immediate_send_router
from app.domains.notifications.router import router as notifications_router
from app.domains.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(notifications_router)
api_router.include_router(immediate_send_router)
