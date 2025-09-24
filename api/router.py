from fastapi import APIRouter
from . import chatbot
from . import tracker
from .market_content import chatwithfiles, youtube_sum
from . import graph_openai1
from .fundamentals_rag import fundamental_chat2, corp
from .dashboard import dashboard
from .dashboard.portfolio import portfolio_snapshot
from .dashboard.stock import stock_snapshot
from .dashboard import trending
from .timeline import timeline
from .doc_rag import doc_chat
from .graph import main as graph_main
from .graph import main as event_graph_main

from streaming import streaming

# Create a single master router
api_router = APIRouter()

# --- Include all the individual routers into the master router ---
# This provides a clean, single point of registration in main.py
api_router.include_router(chatbot.router, tags=["Chatbot"])
api_router.include_router(chatwithfiles.router, tags=["Market Content"])
api_router.include_router(youtube_sum.router, tags=["Market Content"])
api_router.include_router(graph_openai1.router, tags=["Graphing"])
api_router.include_router(streaming.cmots_rag, tags=["Streaming RAG"])
api_router.include_router(streaming.web_rag, tags=["Streaming RAG"])
api_router.include_router(streaming.red_rag, tags=["Streaming RAG"])
api_router.include_router(streaming.yt_rag, tags=["Streaming RAG"])
api_router.include_router(fundamental_chat2.fund_rag, tags=["Fundamentals RAG"])
api_router.include_router(corp.corp_rag, tags=["Fundamentals RAG"])
api_router.include_router(dashboard.router, tags=["Dashboard"])
api_router.include_router(portfolio_snapshot.router, tags=["Dashboard"])
api_router.include_router(stock_snapshot.router, tags=["Dashboard"])
api_router.include_router(trending.router, tags=["Dashboard"])
api_router.include_router(tracker.router, tags=["Tracker"])
api_router.include_router(timeline.router, tags=["Timeline"])
api_router.include_router(doc_chat.router, tags=["Document RAG"])
api_router.include_router(graph_main.router, prefix="/graph", tags=["Knowledge Graph"])
api_router.include_router(event_graph_main.router, prefix="/graph", tags=["Financial Event Graph"])
