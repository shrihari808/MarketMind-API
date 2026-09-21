"""
Search Engine Factory.
Provides developer-configurable search provider resolution (DuckDuckGo, Serper, Brave).
Adheres to the Open/Closed and Dependency Inversion principles.
"""

from typing import Optional
from app.core.config import get_settings
from app.core.logging import logger
from app.domain.interfaces.search import SearchEngine
from app.infrastructure.search.duckduckgo import DuckDuckGoSearcher
from app.infrastructure.search.serper import SerperSearcher
from app.infrastructure.search.brave import BraveSearcher


class SearchEngineFactory:
    """Factory for resolving and instantiating configured SearchEngine instances."""

    _PROVIDERS = {
        "duckduckgo": DuckDuckGoSearcher,
        "serper": SerperSearcher,
        "brave": BraveSearcher,
    }

    @classmethod
    def get_search_engine(
        cls,
        provider: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> SearchEngine:
        """
        Resolves and instantiates the search engine.
        
        Args:
            provider: 'duckduckgo', 'serper', or 'brave'. If None, reads from Settings.SEARCH_PROVIDER.
            api_key: Optional API key override. If None, reads from Settings.

        Returns:
            SearchEngine: An active search engine instance.
        """
        settings = get_settings()
        selected_provider = (provider or settings.SEARCH_PROVIDER).strip().lower()

        if selected_provider not in cls._PROVIDERS:
            supported = list(cls._PROVIDERS.keys())
            raise ValueError(
                f"Unknown search provider '{selected_provider}'. Supported providers: {supported}"
            )

        logger.info(f"Instantiating search engine provider: '{selected_provider}'")

        if selected_provider == "duckduckgo":
            return DuckDuckGoSearcher()
        elif selected_provider == "serper":
            return SerperSearcher(api_key=api_key or settings.SERPER_API_KEY)
        elif selected_provider == "brave":
            return BraveSearcher(api_key=api_key or settings.BRAVE_API_KEY)

        # Fallback to DuckDuckGo if unexpected
        return DuckDuckGoSearcher()
