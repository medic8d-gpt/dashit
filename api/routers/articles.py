from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..models import ArticleCreate, ArticleOut, ArticleUpdate


router = APIRouter(prefix="/articles", tags=["articles"])


def _row_to_article(row) -> ArticleOut:
    return ArticleOut(
        id=row["id"],
        hash=row["hash"],
        source=row["source"],
        url=row["url"],
        headline=row["headline"],
        summary=row["summary"],
        published=row["published"],
        posted=row["posted"],
    )


@router.get("", response_model=list[ArticleOut])
def list_articles(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    posted: Optional[int] = Query(None, ge=0, le=1),
    source: Optional[str] = None,
    q: Optional[str] = Query(None, description="Search headline/summary"),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    sort: str = Query("published_desc", regex="^(published_(asc|desc)|id_(asc|desc))$"),
):
    clauses = []
    params: list = []

    if posted is not None:
        clauses.append("posted = ?")
        params.append(posted)
    if source:
        clauses.append("source = ?")
        params.append(source)
    if q:
        clauses.append("(headline LIKE ? OR summary LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    if date_from:
        clauses.append("published >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("published <= ?")
        params.append(date_to)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = {
        "published_desc": "published DESC, id DESC",
        "published_asc": "published ASC, id ASC",
        "id_desc": "id DESC",
        "id_asc": "id ASC",
    }[sort]

    rows = db.query_all(
        f"""
        SELECT id, hash, source, url, headline, summary, published, posted
        FROM rss_data
        {where}
        ORDER BY {order}
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return [_row_to_article(r) for r in rows]


@router.get("/latest", response_model=list[ArticleOut])
def list_latest(
    limit: int = Query(20, ge=1, le=200),
    source: Optional[str] = None,
    posted: Optional[int] = Query(None, ge=0, le=1),
):
    # Convenience endpoint for the frontend: "latest N" by published date.
    clauses = []
    params: list = []
    if source:
        clauses.append("source = ?")
        params.append(source)
    if posted is not None:
        clauses.append("posted = ?")
        params.append(posted)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query_all(
        f"""
        SELECT id, hash, source, url, headline, summary, published, posted
        FROM rss_data
        {where}
        ORDER BY published DESC, id DESC
        LIMIT ?
        """,
        (*params, limit),
    )
    return [_row_to_article(r) for r in rows]


@router.get("/columns", response_model=list[str])
def list_columns():
    # Introspect table columns safely
    rows = db.query_all("PRAGMA table_info(rss_data)")
    return [r["name"] for r in rows]


@router.get("/distinct/{column}", response_model=list[str])
def distinct_values(column: str, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    # Whitelist known columns to prevent SQL injection
    allowed = set(list_columns())
    if column not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown column '{column}'")
    sql = f"SELECT DISTINCT {column} AS v FROM rss_data ORDER BY v LIMIT ? OFFSET ?"
    rows = db.query_all(sql, (limit, offset))
    return [r["v"] for r in rows]


@router.get("/{id}", response_model=ArticleOut)
def get_article(id: int):
    row = db.query_one(
        "SELECT id, hash, source, url, headline, summary, published, posted FROM rss_data WHERE id = ?",
        (id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    return _row_to_article(row)


@router.get("/hash/{hash}", response_model=ArticleOut)
def get_article_by_hash(hash: str):
    row = db.query_one(
        "SELECT id, hash, source, url, headline, summary, published, posted FROM rss_data WHERE hash = ?",
        (hash,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    return _row_to_article(row)


@router.get("/unposted", response_model=list[ArticleOut])
def list_unposted(limit: int = 50, offset: int = 0):
    rows = db.query_all(
        """
        SELECT id, hash, source, url, headline, summary, published, posted
        FROM rss_data
        WHERE posted = 0
        ORDER BY published DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    return [_row_to_article(r) for r in rows]


@router.get("/posted", response_model=list[ArticleOut])
def list_posted(limit: int = 50, offset: int = 0):
    rows = db.query_all(
        """
        SELECT id, hash, source, url, headline, summary, published, posted
        FROM rss_data
        WHERE posted = 1
        ORDER BY published DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    return [_row_to_article(r) for r in rows]


@router.get("/source/{source}", response_model=list[ArticleOut])
def by_source(source: str, limit: int = 50, offset: int = 0):
    rows = db.query_all(
        """
        SELECT id, hash, source, url, headline, summary, published, posted
        FROM rss_data
        WHERE source = ?
        ORDER BY published DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (source, limit, offset),
    )
    return [_row_to_article(r) for r in rows]


@router.post("", response_model=ArticleOut, status_code=201)
def create_article(payload: ArticleCreate):
    # Hash generation mirrors NewsManager.generate_hash
    import hashlib

    published = payload.published or payload.__dict__.get("published")
    unique_string = (payload.url or "") + (payload.headline or "") + (published or "")
    entry_hash = hashlib.sha256(unique_string.encode("utf-8")).hexdigest()

    try:
        last_id = db.execute(
            """
            INSERT INTO rss_data (hash, source, url, headline, summary, published, posted)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_hash,
                payload.source,
                payload.url,
                payload.headline,
                payload.summary,
                payload.published,
                payload.posted or 0,
            ),
        )
    except Exception as e:
        # Likely a unique constraint on hash
        raise HTTPException(status_code=400, detail=f"Could not insert article: {e}")

    row = db.query_one(
        "SELECT id, hash, source, url, headline, summary, published, posted FROM rss_data WHERE id = ?",
        (last_id,),
    )
    return _row_to_article(row)


@router.patch("/{id}", response_model=ArticleOut)
def update_article(id: int, payload: ArticleUpdate):
    row = db.query_one("SELECT * FROM rss_data WHERE id = ?", (id,))
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")

    # Build dynamic update
    fields = []
    params = []
    for key in ["source", "url", "headline", "summary", "published", "posted"]:
        val = getattr(payload, key, None)
        if val is not None:
            fields.append(f"{key} = ?")
            params.append(val)

    if not fields:
        return _row_to_article(row)

    params.append(id)
    db.execute(f"UPDATE rss_data SET {', '.join(fields)} WHERE id = ?", params)

    row = db.query_one(
        "SELECT id, hash, source, url, headline, summary, published, posted FROM rss_data WHERE id = ?",
        (id,),
    )
    return _row_to_article(row)


@router.delete("/{id}", status_code=204)
def delete_article(id: int):
    count = db.execute("DELETE FROM rss_data WHERE id = ?", (id,))
    if count == 0:
        raise HTTPException(status_code=404, detail="Article not found")
    return None
