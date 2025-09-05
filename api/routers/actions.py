from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import db

router = APIRouter(prefix="", tags=["actions"])


def _get_news_manager():
    # Import lazily to avoid importing heavy deps if not used
    # Provide a clear HTTP error if the optional dependency/module is missing.
    try:
        # Try absolute import (module in project root)
        from news_manager import NewsManager  # type: ignore
    except Exception:
        try:
            # Fallback to package-relative (when installed as a package)
            from ...news_manager import NewsManager  # type: ignore
        except Exception as e:  # ImportError or config error
            raise HTTPException(
                status_code=503,
                detail=f"NewsManager unavailable: {e}. Ensure 'news_manager.py' and required env vars are configured.",
            )
    return NewsManager()


@router.post("/scrape")
def scrape_all():
    nm = _get_news_manager()
    added = nm.scrape_all()
    return {"added": added}


@router.post("/scrape/{source}")
def scrape_source(source: str):
    nm = _get_news_manager()
    source = source.lower()
    # Map simple names to NewsManager methods
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
    if source not in mapping:
        raise HTTPException(status_code=400, detail=f"Unknown source '{source}'")
    added = mapping[source]()
    return {"source": source, "added": added}


@router.post("/reddit/post-unposted")
def reddit_post_unposted(limit: int = Query(5, ge=1, le=50), source: str | None = Query(None)):
    nm = _get_news_manager()
    count = nm.post_unposted_articles(limit=limit, source=source)
    return {"posted": count, "source": source}


@router.post("/reddit/post/{id:int}")
def reddit_post_one(id: int):
    # Fetch the article
    row = db.query_one(
        "SELECT id, url, headline, source FROM rss_data WHERE id = ?",
        (id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")

    from ...news_manager import NewsManager

    nm = NewsManager()
    ok = nm.post_to_reddit(row["id"], row["url"], row["headline"], row["source"])
    if not ok:
        raise HTTPException(status_code=500, detail="Reddit post failed")
    return {"posted": True, "id": id}


@router.post("/articles/{id:int}/mark-posted")
def mark_posted(id: int, posted: int = Query(1, ge=0, le=1)):
    updated = db.execute("UPDATE rss_data SET posted = ? WHERE id = ?", (posted, id))
    if updated == 0:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"id": id, "posted": posted}
