#!/usr/bin/env python3
"""
Standalone poster: submit the last N unposted articles from a source (default: wtvq) to Reddit.

Usage:
  python tools/post_wtvq.py            # posts last 5 from wtvq
  python tools/post_wtvq.py --limit 3  # posts last 3 from wtvq
  python tools/post_wtvq.py --source lex18 --limit 2
  python tools/post_wtvq.py --dry-run  # prints what would post, no Reddit calls

Env required:
  REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT,
  and either REDDIT_REFRESH_TOKEN or REDDIT_USERNAME + REDDIT_PASSWORD
  SUBREDDIT_NAME (defaults to newsoflexingtonky)
  DB_PATH (defaults to rss_feed_data.db at repo root)
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import time
import unicodedata
from typing import Optional
from urllib.parse import urlparse

import praw
from dotenv import load_dotenv


def build_reddit_config() -> dict[str, str]:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    refresh_token = os.getenv("REDDIT_REFRESH_TOKEN")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")

    missing = [k for k, v in {
        "REDDIT_CLIENT_ID": client_id,
        "REDDIT_CLIENT_SECRET": client_secret,
        "REDDIT_USER_AGENT": user_agent,
    }.items() if not v]
    if missing:
        raise RuntimeError("Missing env: " + ", ".join(missing))

    cfg: dict[str, str] = {
        "client_id": client_id,  # type: ignore[arg-type]
        "client_secret": client_secret,  # type: ignore[arg-type]
        "user_agent": user_agent,  # type: ignore[arg-type]
    }
    if refresh_token:
        cfg["refresh_token"] = refresh_token
    else:
        if not username or not password:
            raise RuntimeError("Provide REDDIT_REFRESH_TOKEN or REDDIT_USERNAME and REDDIT_PASSWORD")
        cfg["username"] = username
        cfg["password"] = password
    return cfg


def sanitize_title(text: str) -> str:
    repl = {
        "\u2018": "'", "\u2019": "'",
        "\u201C": '"', "\u201D": '"',
        "\u2013": "-", "\u2014": "-",
        "\u2026": "...", "\u00A0": " ",
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text


def get_flair_id(headline: str) -> Optional[str]:
    # Mirror feed_scraper.py heuristic using env FLAIR IDs
    fid_general = os.getenv("FLAIR_ID_GENERAL")
    fid_fire = os.getenv("FLAIR_ID_FIRE")
    fid_homeless = os.getenv("FLAIR_ID_HOMELESS")
    h = headline.lower()
    if any(w in h for w in ["shot", "shots", "shooter", "shooters", "shooting", "gunshot", "gunshots"]):
        return fid_general
    if "fire" in h:
        return fid_fire
    if any(w in h for w in ["homeless", "homelessness", "unhoused"]):
        return fid_homeless
    return None


def resolve_db_path(env_path: Optional[str]) -> str:
    # Resolve DB path relative to repo root if not absolute
    if env_path and os.path.isabs(env_path):
        return env_path
    # repo root = parent of this file's directory (tools/..)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, env_path or "rss_feed_data.db")


def fetch_unposted(db_path: str, source: str, limit: int):
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, url, headline, source, published
            FROM rss_data
            WHERE posted = 0 AND source = ?
            ORDER BY published DESC, id DESC
            LIMIT ?
            """,
            (source, limit),
        )
        return cur.fetchall()


def mark_posted(db_path: str, post_id: int):
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE rss_data SET posted = 1 WHERE id = ?", (post_id,))
        conn.commit()


def main():
    load_dotenv()
    ap = argparse.ArgumentParser(description="Post last N unposted items from a source to Reddit")
    ap.add_argument("--source", default="wtvq", help="Source key (default: wtvq)")
    ap.add_argument("--limit", type=int, default=5, help="How many to post (default: 5)")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without posting")
    args = ap.parse_args()

    db_path = resolve_db_path(os.getenv("DB_PATH"))
    items = fetch_unposted(db_path, args.source.lower(), args.limit)
    if not items:
        print("No unposted items found for", args.source)
        return

    print(f"Posting {len(items)} item(s) from {args.source}…")

    subreddit_name = os.getenv("SUBREDDIT_NAME", "newsoflexingtonky")
    reddit = None if args.dry_run else praw.Reddit(**build_reddit_config())

    posted = 0
    for post_id, url, headline, source, published in items:
        title = f"[{source.upper()}] {headline}"
        title = sanitize_title(title)
        if len(title) > 300:
            title = title[:297] + "..."

        print(f"→ {title[:80]} | {url}")

        if args.dry_run:
            continue

        try:
            sub = reddit.subreddit(subreddit_name)
            submission = sub.submit(title=title, url=url)
            flair_id = get_flair_id(headline)
            if flair_id:
                try:
                    submission.flair.select(flair_id)
                except Exception:
                    pass
            mark_posted(db_path, post_id)
            posted += 1
            time.sleep(2)
        except Exception as e:
            print("! Failed:", e)

    print(f"Done. Posted {posted}/{len(items)}")


if __name__ == "__main__":
    main()
