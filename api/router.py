from fastapi import APIRouter
# --- Import all the individual router objects from your application ---
from .dashboard import dashboard
from .dashboard.portfolio import portfolio_snapshot
from .dashboard.stock import stock_snapshot
from .dashboard import trending
from .timeline import timeline
from .doc_rag import doc_chat

from streaming import streaming

# single master router
api_router = APIRouter()

# --- Include all the individual routers into the master router ---
# This provides a clean, single point of registration in main.py
api_router.include_router(streaming.web_rag, tags=["Streaming RAG"])
api_router.include_router(streaming.red_rag, tags=["Streaming RAG"])
api_router.include_router(streaming.yt_rag, tags=["Streaming RAG"])
api_router.include_router(dashboard.router, tags=["Dashboard"])
api_router.include_router(portfolio_snapshot.router, tags=["Dashboard"])
api_router.include_router(stock_snapshot.router, tags=["Dashboard"])
api_router.include_router(trending.router, tags=["Dashboard"])
api_router.include_router(timeline.router, tags=["Timeline"])
api_router.include_router(doc_chat.router, tags=["Document RAG"])