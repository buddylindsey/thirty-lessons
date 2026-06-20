#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_DIR"

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.e2e.yml"
TEST_DB="${E2E_DATABASE_NAME:-learning_e2e}"

cleanup() {
  docker compose $COMPOSE_FILES stop e2e-web >/dev/null 2>&1 || true
  docker compose exec -T db psql -U learning -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS ${TEST_DB} WITH (FORCE);" >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

docker compose up -d db
docker compose exec -T db psql -U learning -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS ${TEST_DB} WITH (FORCE);"
docker compose exec -T db psql -U learning -d postgres -v ON_ERROR_STOP=1 \
  -c "CREATE DATABASE ${TEST_DB};"

docker compose $COMPOSE_FILES up -d --build e2e-web

E2E_DOCKER=1 \
E2E_ALLOW_DB_RESET=1 \
E2E_MANAGE_SERVICE=e2e-web \
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8001 \
npx playwright test
