from __future__ import annotations

from collections import Counter

from fastapi import APIRouter

from .. import db
from ..models import StatsOut


router = APIRouter(prefix="", tags=["admin"])


@router.get("/", include_in_schema=False)
def index():
    # Lightweight landing page for quick sanity checks and to avoid confusing 404s
    return {
        "name": "dashit-api",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "stats": "/stats",
    }


@router.get("/sources", response_model=list[str])
def list_sources():
    rows = db.query_all("SELECT DISTINCT source FROM rss_data ORDER BY source")
    return [r["source"] for r in rows]


@router.get("/stats", response_model=StatsOut)
def stats():
    total_row = db.query_one("SELECT COUNT(*) AS c FROM rss_data")
    posted_row = db.query_one("SELECT COUNT(*) AS c FROM rss_data WHERE posted = 1")
    rows = db.query_all("SELECT source FROM rss_data")
    counts = Counter([r["source"] for r in rows])
    return StatsOut(
        total=total_row["c"],
        posted=posted_row["c"],
        unposted=total_row["c"] - posted_row["c"],
        by_source=dict(counts),
    )


@router.get("/health")
def health():
    # Simple DB touch
    db.query_one("SELECT 1")
    return {"status": "ok"}


@router.get("/version")
def version():
    return {"name": "dashit-api", "version": "0.1.0"}
