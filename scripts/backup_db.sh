#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_DIR"

DB_SERVICE="${DB_SERVICE:-db}"
DB_NAME="${DB_NAME:-learning}"
DB_USER="${DB_USER:-learning}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}-${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

docker compose up -d "$DB_SERVICE" >/dev/null

docker compose exec -T "$DB_SERVICE" pg_dump \
  --username "$DB_USER" \
  --dbname "$DB_NAME" \
  --format plain \
  --no-owner \
  --no-privileges \
  --clean \
  --if-exists \
  > "$BACKUP_FILE"

printf 'Database backup written to: %s\n' "$BACKUP_FILE"
printf 'Restore with: docker compose exec -T %s psql --username %s --dbname %s < %s\n' "$DB_SERVICE" "$DB_USER" "$DB_NAME" "$BACKUP_FILE"
