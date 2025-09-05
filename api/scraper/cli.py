"""CLI entrypoint for scraper package.

Replaces legacy standalone script. Mirrors original arguments.
"""
from __future__ import annotations

import argparse

from .manager import NewsManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="News Scraper and Reddit Poster")
    parser.add_argument("--scrape", action="store_true", help="Scrape news from all sources")
    parser.add_argument("--post", action="store_true", help="Post unposted articles to Reddit")
    parser.add_argument("--limit", type=int, default=5, help="Limit number of Reddit posts")
    parser.add_argument("--source", type=str, default=None, help="Only operate on a specific source (e.g., lex18)")
    parser.add_argument("--all", action="store_true", help="Scrape and post (default if no args)")
    return parser


def main():  # pragma: no cover - thin wrapper
    parser = build_parser()
    args = parser.parse_args()
    nm = NewsManager()
    if not any([args.scrape, args.post, args.all]):
        args.all = True
    if args.scrape or args.all:
        if args.source:
            mapping = {
                "rss": nm.scrape_rss_feeds,
                "lexington_gov": nm.scrape_lexington_gov_news,
                "wkyt": nm.scrape_wkyt_news,
                "wkyt_questions": nm.scrape_wkyt_good_questions,
                "newsapi": nm.scrape_newsapi,
                "civiclex": nm.scrape_civiclex_news,
                "central_bank": nm.scrape_central_bank_center,
                "newsdata_apis": nm.scrape_newsdata_apis,
            }
            fn = mapping.get(args.source.lower())
            if fn:
                fn()
            else:
                nm.scrape_all()
        else:
            nm.scrape_all()
    if args.post or args.all:
        nm.post_unposted_articles(limit=args.limit, source=args.source)


if __name__ == "__main__":  # pragma: no cover
    main()
