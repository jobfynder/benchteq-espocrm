$ErrorActionPreference = "Stop"
docker compose ps
docker compose exec -T espocrm bin/command app-check
docker compose exec -T database healthcheck.sh --connect --innodb_initialized

