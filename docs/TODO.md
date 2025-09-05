# TODO — LexKYNews / dashit

A focused, prioritized checklist to guide development. Use short branches and PRs per item.

## Now (P0)
- [x] Ignore SQLite temps: add `rss_feed_data.db*` to `.gitignore` to avoid noisy diffs.
- [ ] Health & stats endpoint: expose scrape counts, last-run timestamps, queue depth at `GET /stats`.
- [ ] Admin actions hardening: require API key/JWT for write endpoints in `api/routers/actions.py`.
- [ ] Stabilize scraping runs: introduce retry/backoff and source toggles in code/env.

## Next (P1)
- [ ] Review queue: endpoint + minimal UI to approve/edit before posting to Reddit.
- [ ] Smart dedupe: consolidate near-duplicate articles by URL/domain + fuzzy title match.
- [ ] Topic tags: lightweight keyword/NER tags stored on articles; filter by tag in API.
- [ ] Public curated feed: `GET /feed.{rss,json}` of approved items with summaries.

## Backend/API
- [ ] Background jobs: queue scraping/posting (RQ/Celery) with retries and metrics.
- [ ] Rate limiting: per-IP for public reads; stricter for actions.
- [ ] Config cleanup: ensure `.env.example` matches scraper package env vars (Reddit, API keys, DB_PATH).
- [ ] Content archiving: store readability-processed HTML or snapshots to mitigate link rot.

## Scrapers & Sources
- [ ] Add: Herald-Leader, UKNow, KSP/KYTC alerts, LFUCG agendas/minutes.
- [ ] Normalize: consistent source IDs, timestamps, bylines; store raw and cleaned fields.
- [ ] Error visibility: log per-source error counts; include in `/stats`.

## Frontend (web/)
- [ ] Filters/search: keyword, source, date, tags, posted/unposted.
- [ ] Saved views: quick pins like “City Hall”, “Traffic”.
- [ ] Mobile polish: list cards, dark mode toggle.
- [ ] Admin controls: buttons to run scrapers, view `/stats`, and manage review queue.

## Data & ML (lightweight)
- [ ] Similarity detection: embeddings or fuzzy string match to flag dupes.
- [ ] Keyword/NER extraction: simple spaCy/KeyBERT pipeline for tags.
- [ ] Headline quality checks: heuristics to flag low-signal items.

## Ops & Infra
- [ ] Systemd units: verify/update `deploy/*.service` and timers; add env files.
- [ ] Observability: structured logs, Sentry for API errors, Prometheus metrics.
- [ ] Backups: periodic DB and `web/dist` snapshots; document restore steps.
- [ ] Security headers/CORS: tighten Nginx and FastAPI settings.

## Quality & CI
- [ ] Tests: FastAPI routers with TestClient; scraper contract tests with fixtures.
- [ ] GitHub Actions: run tests, build web, export OpenAPI, and type-check on PRs.
- [ ] OpenAPI client: auto-regenerate `web/src/lib/openapi.ts` on API schema changes.

## Security
- [ ] Secrets hygiene: document Reddit token rotation; load via env only.
- [ ] AuthZ: restrict admin/action routes; audit for accidental public writes.
- [ ] Dependency review: schedule monthly `pip audit`/`npm audit` and pin updates.

## Nice to Have (P2)
- [ ] User alerts: email/Discord/WebPush on keyword/location rules.
- [ ] Event/calendar ingest: city events + “what’s next” widget.
- [ ] Social embed expansion: resolve and render referenced Tweets/FB posts.

## Housekeeping
- [ ] README: ensure Quickstart works end-to-end (API + web).
- [ ] Docs: brief scraper guide and contribution flow.
- [ ] Changelog: start a simple `CHANGELOG.md` with Keep a Changelog format.

---
Tip: create a branch per checkbox, keep diffs small, and ship often.
