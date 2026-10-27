from fastapi import APIRouter

from app.api.v1 import auth, datasets, health, organizations, projects

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(projects.router)
api_router.include_router(datasets.router)
