#!/usr/bin/env bash
set -euo pipefail

NGINX_PATH="${NGINX_PATH:-/opt/elestio/nginx}"
DOMAIN="${DOMAIN:-reports.jobfynder.com}"
SOURCE_CONFIG="${SOURCE_CONFIG:-/tmp/reports.jobfynder.com.conf}"
TARGET_CONFIG="$NGINX_PATH/conf.d/$DOMAIN.conf"
BACKUP_PATH="$NGINX_PATH/pre-metabase-20260728"

test -f "$NGINX_PATH/.env"
test -f "$NGINX_PATH/docker-compose.yml"
test -f "$SOURCE_CONFIG"

install -d -m 700 "$BACKUP_PATH"
if [ ! -f "$BACKUP_PATH/.env" ]; then
  cp -a "$NGINX_PATH/.env" "$BACKUP_PATH/.env"
  chmod 600 "$BACKUP_PATH/.env"
fi

if [ -e "$TARGET_CONFIG" ]; then
  echo "$TARGET_CONFIG already exists; refusing to overwrite it." >&2
  exit 1
fi

install -m 644 "$SOURCE_CONFIG" "$TARGET_CONFIG"
if ! docker exec elestio-nginx openresty -t; then
  rm -f "$TARGET_CONFIG"
  exit 1
fi

allowed_domains="$(sed -n 's/^ALLOWED_DOMAINS=//p' "$NGINX_PATH/.env")"
test -n "$allowed_domains"

case "|$allowed_domains|" in
  *"|$DOMAIN|"*) ;;
  *)
    sed -i \
      "s#^ALLOWED_DOMAINS=.*#ALLOWED_DOMAINS=${allowed_domains}|${DOMAIN}#" \
      "$NGINX_PATH/.env"
    ;;
esac

cd "$NGINX_PATH"
docker compose up -d
docker exec elestio-nginx openresty -t

echo "Nginx reporting proxy configured for $DOMAIN."
