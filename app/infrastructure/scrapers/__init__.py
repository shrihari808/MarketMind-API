"""
Web Scraper Infrastructure Package.
"""

from app.domain.interfaces.scraper import WebScraper
from app.infrastructure.scrapers.web_scraper import TrafilaturaWebScraper

__all__ = ["WebScraper", "TrafilaturaWebScraper"]
