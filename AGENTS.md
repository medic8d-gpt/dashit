# Repository Guidelines

These guidelines assume work happens directly on a live server. Favor small, safe changes with quick rollback.

## Project Structure & Module Organization
- `api/`: FastAPI app (routers, models, db). Entry: `api/main.py`.
- `web/`: React (Vite) site. Build artifacts in `web/dist/`.
- `tools/`: Utilities (OpenAPI export, posting helpers).
- `deploy/`: Systemd services/timers and ops examples.
- Root: `news_manager.py`, `feed_scraper.py`, `.env.example`, `requirements.txt`.

## Live Update & Ops Commands
- Update code (on server): `git pull --ff-only`
- Build web: `cd web && npm ci && npm run build`
- Deploy web: `sudo rsync -a web/dist/ /var/www/<domain>/html/`
- Nginx reload (safe): `sudo nginx -t && sudo systemctl reload nginx`
- API restart: `sudo systemctl restart lexkynews-api && sudo systemctl status --no-pager lexkynews-api`
- DB backup (SQLite): `sqlite3 rss_feed_data.db '.backup backups/rss_$(date +%F-%H%M).sqlite3'`

## Coding Style & Naming
- Python: PEP 8, 4‑space indent, type hints where practical. Modules `snake_case`, classes `PascalCase`, functions/vars `snake_case`.
- TypeScript/React: Components `PascalCase`, hooks `useX`, others `camelCase`.
- Routes live in `api/routers/` with clear tags and explicit models.
- Config via `.env` (start from `.env.example`). Never commit secrets.

## Smoke Testing (Production)
- After deploy, verify: `curl -fsS http://<domain>/api/health`, `curl -fsS http://<domain>/api/version`, and load the homepage.
- For data paths, spot‑check: `GET /api/articles?limit=1` and any scraper trigger endpoints (if enabled).

## Commit & Pull Request Guidelines
- Commits: Conventional style (e.g., `feat: add WKYT scraper`, `fix(api): handle empty feed`). Keep diffs small and scoped.
- Main-first: Small fixes may go straight to `main`. For risky changes, use `feature/<short-name>` and open a PR.
- PRs: Describe intent, include screenshots for UI, and link issues when applicable.

## Security & Configuration Tips
- Secrets only in environment files or server env; never commit tokens or `rss_feed_data.db*`.
- Lock down action/admin routes; enable timeouts and retries in scrapers.
- Serve the web build via Nginx; proxy `/api/` to the FastAPI service. Keep systemd units in `deploy/` updated.
