# dashit API

A lightweight FastAPI service over the `rss_data` SQLite database with helpers to run scrapers and post to Reddit via the existing `news_manager.py`.

## Quickstart

- Python 3.10+
- Create and populate `.env` (see `.env.example`), or ensure `DB_PATH` points to your SQLite file. Default is `dashit/rss_feed_data.db`.

Install deps and run:

```
pip install -r requirements.txt
uvicorn api.main:app --reload --app-dir .
```

Now open: `http://127.0.0.1:8000/docs`

## Endpoints

- GET `/articles`: list with filters (`limit`, `offset`, `posted`, `source`, `q`, `from`, `to`, `sort`)
- GET `/articles/{id}`: fetch one
- GET `/articles/hash/{hash}`: by unique hash
- GET `/articles/unposted` and `/articles/posted`
- GET `/articles/source/{source}`
- POST `/articles`: create (computes hash like `NewsManager`)
- PATCH `/articles/{id}`: partial update
- DELETE `/articles/{id}`: delete

- POST `/scrape`: run all scrapers
- POST `/scrape/{source}`: one of `rss`, `lexington_gov`, `wkyt`, `wkyt_questions`, `newsapi`, `civiclex`, `central_bank`, `newsdata_apis`
- POST `/reddit/post-unposted?limit=5`: post queue to Reddit
- POST `/reddit/post/{id}`: post a specific article
- POST `/articles/{id}/mark-posted?posted=1`: set posted flag without Reddit

- GET `/sources`: distinct sources
- GET `/stats`: totals and by-source counts
- GET `/health`: health check
- GET `/version`: app version

## Notes

- The API reads/writes the `rss_data` table with columns: `id, hash, source, url, headline, summary, published, posted`.
- The scrapers and Reddit posting use `dashit/news_manager.py`; ensure its environment variables are configured in `.env`.
- If you keep two DBs in your workspace, set `DB_PATH` explicitly to avoid confusion.

## Dev Tips

- Run with a different DB: `DB_PATH=/full/path/to/rss_feed_data.db uvicorn api.main:app --reload --app-dir .`
- The OpenAPI docs are at `/docs` and `/openapi.json`.
