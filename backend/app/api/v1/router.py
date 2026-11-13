"""Aggregates every v1 router under /api/v1. New feature routers get added here."""

from fastapi import APIRouter

from app.api.v1 import auth, health, me, org

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(org.router)
