#!/bin/sh
set -e

if [ -n "$DATABASE_URL" ]; then
  DB_HOST="${DB_HOST:-db}"
  DB_PORT="${DB_PORT:-5432}"
  until nc -z "$DB_HOST" "$DB_PORT"; do
    echo "Waiting for database at $DB_HOST:$DB_PORT..."
    sleep 1
  done
fi

python manage.py migrate --noinput

exec "$@"
