"""Scraper package exposing NewsManager and CLI entry.

Usage (programmatic):
    from scraper import NewsManager

CLI (equivalent to legacy feed_scraper.py):
    python -m scraper.cli --all
"""

from .manager import NewsManager  # re-export

__all__ = ["NewsManager"]
