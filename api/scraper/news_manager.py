from __future__ import annotations

# Thin compatibility wrapper so API endpoints can import `dashit.news_manager`
# while the implementation lives in `feed_scraper.py`.

try:
    from .feed_scraper import NewsManager  # when imported as package
except Exception:
    from feed_scraper import NewsManager  # when run as a script from project root

__all__ = ["NewsManager"]
