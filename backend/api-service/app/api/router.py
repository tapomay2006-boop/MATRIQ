from fastapi import APIRouter

from app.api.routes import ai, health, materials, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(materials.router)
api_router.include_router(ai.router)

