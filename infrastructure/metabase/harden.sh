#!/usr/bin/env bash
set -euo pipefail

STACK_PATH="${STACK_PATH:-/opt/app}"
FRAGMENT_PATH="${FRAGMENT_PATH:-/tmp/benchteq-metabase-compose.yml}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

cd "$STACK_PATH"
test -f docker-compose.override.yml
test -f .env
test -f "$FRAGMENT_PATH"
docker compose config --services | grep -qx metabase

if grep -q '^METABASE_ENCRYPTION_SECRET_KEY=' .env; then
  echo "Metabase encryption key already exists; refusing to replace it." >&2
  exit 1
fi

encryption_key="$(openssl rand -base64 32 | tr -d '\n')"
printf 'METABASE_ENCRYPTION_SECRET_KEY=%s\n' "$encryption_key" >> .env

candidate="$(mktemp)"
awk '/^  metabase:/{exit} {print}' docker-compose.override.yml > "$candidate"
tail -n +2 "$FRAGMENT_PATH" >> "$candidate"

METABASE_ENCRYPTION_SECRET_KEY="$encryption_key" \
  docker compose -f docker-compose.yml -f "$candidate" config --quiet

cp -a docker-compose.override.yml "docker-compose.override.yml.pre-hardening-$TIMESTAMP"
install -m 644 "$candidate" docker-compose.override.yml
rm -f "$candidate"

docker compose config --quiet
docker compose up -d metabase

echo "Metabase hardening configuration applied."
