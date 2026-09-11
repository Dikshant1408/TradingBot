"""
Strategy Registry API routes.
"""
from fastapi import APIRouter
from app.strategies.registry import strategy_registry

router = APIRouter(prefix="/api/strategy", tags=["Strategy"])


@router.get("/list")
def list_strategies():
    """List all registered quantitative strategies with their parameter schemas."""
    return strategy_registry.list_strategies()
