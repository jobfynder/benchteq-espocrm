#!/usr/bin/env bash
set -euo pipefail

STACK_PATH="${STACK_PATH:-/opt/app}"
FRAGMENT_PATH="${FRAGMENT_PATH:-/tmp/benchteq-metabase-compose.yml}"
BACKUP_REFERENCE="${BACKUP_REFERENCE:?Set BACKUP_REFERENCE}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

cd "$STACK_PATH"

test -f docker-compose.yml
test -f docker-compose.override.yml
test -f .env
test -f "$FRAGMENT_PATH"

if docker compose config --services | grep -qx metabase; then
  echo "Metabase service already exists; refusing to overwrite it." >&2
  exit 1
fi

if grep -qE '^(METABASE_DB_PASSWORD|METABASE_REPORTING_PASSWORD)=' .env; then
  echo "Metabase secrets already exist; refusing to overwrite them." >&2
  exit 1
fi

app_password="$(openssl rand -hex 32)"
reporting_password="$(openssl rand -hex 32)"
admin_password="$(sed -n 's/^ADMIN_PASSWORD=//p' .env | tail -n 1 | tr -d '\r')"
test -n "$admin_password"

install -d -m 700 "$STACK_PATH/pre-metabase-$TIMESTAMP"
cp -a docker-compose.override.yml "$STACK_PATH/pre-metabase-$TIMESTAMP/"
cp -a .env "$STACK_PATH/pre-metabase-$TIMESTAMP/"
printf '%s\n' "$BACKUP_REFERENCE" > "$STACK_PATH/pre-metabase-$TIMESTAMP/backup-reference.txt"
chmod 600 "$STACK_PATH/pre-metabase-$TIMESTAMP/.env"

printf '\nMETABASE_DB_PASSWORD=%s\nMETABASE_REPORTING_PASSWORD=%s\n' \
  "$app_password" "$reporting_password" >> .env

candidate="$(mktemp)"
cp docker-compose.override.yml "$candidate"
tail -n +2 "$FRAGMENT_PATH" >> "$candidate"

METABASE_DB_PASSWORD="$app_password" \
  docker compose -f docker-compose.yml -f "$candidate" config --quiet

docker compose exec -T -e MYSQL_PWD="$admin_password" mysql \
  mysql --user=root <<SQL
CREATE DATABASE IF NOT EXISTS metabase_app
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'metabase_app'@'%'
  IDENTIFIED WITH mysql_native_password BY '$app_password';
ALTER USER 'metabase_app'@'%'
  IDENTIFIED WITH mysql_native_password BY '$app_password';
GRANT ALL PRIVILEGES ON metabase_app.* TO 'metabase_app'@'%';
CREATE USER IF NOT EXISTS 'metabase_readonly'@'%'
  IDENTIFIED WITH mysql_native_password BY '$reporting_password';
ALTER USER 'metabase_readonly'@'%'
  IDENTIFIED WITH mysql_native_password BY '$reporting_password';
GRANT SELECT, SHOW VIEW ON espocrm.* TO 'metabase_readonly'@'%';
FLUSH PRIVILEGES;
SQL

install -m 644 "$candidate" docker-compose.override.yml
rm -f "$candidate"

docker compose config --quiet
docker compose pull metabase
docker compose up -d metabase

echo "Metabase service installed. Secrets were written to $STACK_PATH/.env."
