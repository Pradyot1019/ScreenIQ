"""Aggregates every v1 router under /api/v1. New feature routers get added here."""

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
