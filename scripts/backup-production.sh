#!/usr/bin/env bash
set -euo pipefail

stack_path="${STACK_PATH:-/opt/app}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$stack_path/backups/benchteq-implementation-$timestamp"

cd "$stack_path"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

admin_password="$(
  sed -n 's/^ADMIN_PASSWORD=//p' .env |
    tail -n 1 |
    tr -d '\r'
)"
test -n "$admin_password"

docker compose exec -T -e MYSQL_PWD="$admin_password" mysql \
  mysqldump --user=root --single-transaction --routines --events espocrm |
  gzip -9 > "$backup_dir/espocrm.sql.gz"

tar -C "$stack_path" -czf "$backup_dir/espocrm-custom.tgz" \
  espocrm/custom espocrm/client-custom

unset admin_password

du -sh "$backup_dir"
echo "$backup_dir"
