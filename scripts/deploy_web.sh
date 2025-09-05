#!/usr/bin/env bash
set -euo pipefail

# Build and deploy the web (Vite) frontend to production directory.
# Usage: ./scripts/deploy_web.sh [--no-build]
# Requires: rsync, npm, permissions to write /var/www/lexkynews.com/html

BUILD=1
if [[ "${1:-}" == "--no-build" ]]; then BUILD=0; fi

pushd "$(dirname "$0")/../web" >/dev/null
if [[ $BUILD -eq 1 ]]; then
  echo "[deploy] Installing dependencies (CI-friendly)" >&2
  npm ci
  echo "[deploy] Building" >&2
  npm run build
else
  echo "[deploy] Skipping build (using existing dist/)" >&2
fi

if [[ ! -d dist ]]; then
  echo "[deploy] ERROR: dist/ missing; run without --no-build" >&2
  exit 1
fi

TARGET=/var/www/lexkynews.com/html
TMPSTAMP=$(date +%Y%m%d%H%M%S)
BACKUP_PARENT=/var/www/lexkynews.com/deploys
mkdir -p "$BACKUP_PARENT"

# Backup current live site (lightweight, excludes large .map files if any)
if [[ -d "$TARGET" ]]; then
  echo "[deploy] Creating backup of current site" >&2
  tar -czf "$BACKUP_PARENT/live_backup_${TMPSTAMP}.tar.gz" -C "$TARGET" . || echo "[deploy] Warning: backup failed"
fi

echo "[deploy] Rsync to $TARGET" >&2
rsync -a --delete dist/ "$TARGET/"

# Copy an OpenAPI spec if present (optional)
if [[ -f ../docs/openapi.json ]]; then
  cp ../docs/openapi.json "$TARGET/openapi.json"
fi

echo "[deploy] Done." >&2
popd >/dev/null
