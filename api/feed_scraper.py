#!/usr/bin/env python3
"""Compatibility shim.

Original monolithic implementation moved into package `scraper`.
Keep this file so existing cron/systemd jobs continue working.

Prefer:  python -m scraper.cli --all
Or:      from scraper import NewsManager
"""

from scraper.cli import main  # type: ignore F401 re-export

if __name__ == "__main__":  # pragma: no cover
    main()
