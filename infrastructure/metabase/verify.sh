#!/usr/bin/env bash
set -euo pipefail

STACK_PATH="${STACK_PATH:-/opt/app}"
cd "$STACK_PATH"

admin_password="$(sed -n 's/^ADMIN_PASSWORD=//p' .env | tail -n 1 | tr -d '\r')"
test -n "$admin_password"

curl --fail --silent --show-error http://172.17.0.1:8787/api/health
echo

docker compose exec -T -e MYSQL_PWD="$admin_password" mysql \
  mysql --user=root --batch --skip-column-names <<'SQL'
SELECT user, host, plugin
FROM mysql.user
WHERE user IN ('metabase_app', 'metabase_readonly')
ORDER BY user;
SHOW GRANTS FOR 'metabase_app'@'%';
SHOW GRANTS FOR 'metabase_readonly'@'%';
SQL

docker inspect app-metabase-1 --format \
  'Metabase status={{.State.Status}} OOMKilled={{.State.OOMKilled}} RestartCount={{.RestartCount}} MemoryLimit={{.HostConfig.Memory}}'
