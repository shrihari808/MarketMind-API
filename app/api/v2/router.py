"""
Master Router for MarketMind API v2.
Aggregates all domain sub-routers under the '/api/v2' prefix.
"""

from fastapi import APIRouter

from app.api.v2.endpoints.health import router as health_router
from app.api.v2.endpoints.chat import router as chat_router
from app.api.v2.endpoints.rag import router as rag_router
from app.api.v2.endpoints.dashboard import router as dashboard_router
from app.api.v2.endpoints.stocks import router as stocks_router
from app.api.v2.endpoints.research import router as research_router
from app.api.v2.endpoints.vault import router as vault_router

api_v2_router = APIRouter(prefix="/api/v2")

api_v2_router.include_router(health_router)
api_v2_router.include_router(chat_router)
api_v2_router.include_router(rag_router)
api_v2_router.include_router(vault_router)
api_v2_router.include_router(dashboard_router)
api_v2_router.include_router(stocks_router)
api_v2_router.include_router(research_router)
