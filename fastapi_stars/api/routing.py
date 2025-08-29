from fastapi import APIRouter

from .v1 import auth, users, info, order

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/v1/users", tags=["users"])
api_router.include_router(info.router, prefix="/v1/info", tags=["info"])
api_router.include_router(order.router, prefix="/v1/orders", tags=["orders"])
