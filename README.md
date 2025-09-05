# LexKYNews Monorepo

FastAPI backend + React (Vite) frontend for LexKYNews. This repo contains the API, scraping helpers, and the static website used in production.

## Stack

- API: Python 3.12+, FastAPI, SQLite
# LexKYNews Monorepo

FastAPI backend + React (Vite) frontend for LexKYNews. This repo contains the API, scraping helpers, and the static website used in production.

## Stack

- API: Python 3.12+, FastAPI, SQLite
- Web: Node 20+, React 18, Vite
- Ops: Nginx, systemd

## Repository structure

```bash
.
├─ api/                # FastAPI app (routers, models, db)
├─ web/                # Public React site (Vite) — deployed (Nginx serves web/dist)
├─ frontend/           # Deprecated (duplicate of web/). Use `web/` going forward.
├─ tools/              # Utilities (e.g., export_openapi.py)
├─ deploy/             # Ops (e.g., systemd unit)
├─ docs/               # OpenAPI and request examples
├─ requirements.txt    # API deps
├─ .env(.example)      # Environment config
└─ README.md
```

Production (server):

## Quickstart

API (dev):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp -n .env.example .env  # edit as needed
uvicorn api.main:app --reload --app-dir .
# http://127.0.0.1:8000/docs
```

Web (dev):

```bash
cd web
npm ci
npm run dev
# http://localhost:5173
```

## Environment

- Copy `.env.example` to `.env` and set variables. Important:
  - `DB_PATH` — path to SQLite DB (defaults: legacy `rss_feed_data.db` in repo root if present; else `database/rss_feed_data.db`)
  - Scraper/Reddit creds (see `scraper/manager.py` for required env vars)

## Build & deploy

Web (static site):

```bash
cd web
npm ci
npm run build
# Deploy contents of web/dist/ to /var/www/lexkynews.com/html
```

API (service):

```bash
# Dev
uvicorn api.main:app --host 0.0.0.0 --port 4000 --app-dir .

# Systemd (example unit in deploy/lexkynews-api.service)
# Copy, edit paths/env, then enable & start
```

Nginx (SPA + API proxy): `location / { try_files $uri $uri/ /index.html; }` and `location /api/ { proxy_pass http://127.0.0.1:4000/; }`.

## Scraper (modular)

The original monolithic `feed_scraper.py` and compatibility `news_manager.py` were removed. Use the package:

```
python -m scraper.cli --scrape
python -m scraper.cli --post --limit 5
python -m scraper.cli --all
```

Programmatic:
```python
from scraper import NewsManager
nm = NewsManager()
nm.scrape_all()
nm.post_unposted_articles(limit=5)
```

Systemd unit updated to call `python -m scraper.cli`.

Database storage now lives in `database/` (auto-created). Legacy root `rss_feed_data.db` is still used if it exists; remove or move it to adopt the new location.

### Automation (systemd)

Scrape + post timers (see `deploy/`):

```
sudo cp deploy/lexkynews-scrape.service /etc/systemd/system/
sudo cp deploy/lexkynews-scrape.timer /etc/systemd/system/
sudo cp deploy/lexkynews-post.service /etc/systemd/system/
sudo cp deploy/lexkynews-post.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lexkynews-scrape.timer lexkynews-post.timer
systemctl list-timers | grep lexkynews
```

Adjust intervals in the `*.timer` files (`OnUnitActiveSec`).

## API overview

Key routes (see `docs/openapi.json` and `/docs`):

- Articles CRUD, filters, posted/unposted
- Scrape endpoints (rss, lexington_gov, wkyt, civiclex, etc.)
- Reddit posting helpers
- `/sources`, `/stats`, `/health`, `/version`

## Branching — should we use branches?

Yes. Keep `main` stable; use short‑lived feature branches.

Minimal flow:

```bash
git switch -c feature/my-change
# edit code
git add -A && git commit -m "feat: describe change"
git push -u origin feature/my-change
# open a PR into main
```

You can push to `main` for small, low‑risk edits, but PRs are preferred for review and rollback safety.
