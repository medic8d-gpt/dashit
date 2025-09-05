# Database Directory

Central location for SQLite databases used by the project.

Default primary DB: `rss_feed_data.db`

Behavior:
- If `DB_PATH` env var is set, that path is used (absolute or relative to CWD).
- If legacy root `rss_feed_data.db` exists, it is still honored (no forced move).
- Otherwise a new DB is created here: `database/rss_feed_data.db`.

To migrate legacy DB:
```bash
mv rss_feed_data.db database/
```
(or leave it; code will continue using legacy file until removed.)

Backups suggestion:
```bash
sqlite3 database/rss_feed_data.db ".backup backups/rss_$(date +%F-%H%M).sqlite3"
```
