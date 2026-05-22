#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_DIR"

compose_env_args=""

if [ -f "$PROJECT_DIR/.env" ]; then
  compose_env_args="$compose_env_args --env-file $PROJECT_DIR/.env"
fi

if [ -f "$PROJECT_DIR/.env.email" ]; then
  compose_env_args="$compose_env_args --env-file $PROJECT_DIR/.env.email"
fi

# shellcheck disable=SC2086
docker compose $compose_env_args run --rm web python manage.py generate_daily_lessons
