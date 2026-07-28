# Metabase production deployment

## Deployment record

- Deployment date: 2026-07-28
- Pre-deployment Elestio backup: `75M` at `2026-07-28 12:27:36`
- Public URL: `https://reports.jobfynder.com`
- Image: `metabase/metabase:v0.63.1.8`
- Container: `app-metabase-1`
- Internal endpoint: `172.17.0.1:8787`
- Metabase application schema: `metabase_app`
- EspoCRM analytics account: `metabase_readonly`
- Nginx TLS allowlist: includes `reports.jobfynder.com`

## Security state

- The EspoCRM analytics account has only `SELECT` and `SHOW VIEW` on
  `espocrm.*`.
- Metabase application data uses a separate writable `metabase_app` schema.
- Metabase database credentials are encrypted at rest with
  `MB_ENCRYPTION_SECRET_KEY`.
- Public sharing and embedding are disabled.
- AI features and anonymous telemetry are disabled.
- Metabase listens only on the Docker host's loopback bridge address; public
  access passes through Elestio Nginx and TLS.
- The Java heap is capped at 768 MiB and the container at 1.5 GiB.

## Verification

- Internal `/api/health`: OK
- Public `/api/health`: HTTP 200 with valid TLS
- Public setup page: HTTP 200 with valid TLS
- EspoCRM after installation: HTTP 200 with valid TLS
- Metabase container: running, no OOM kill, zero restarts
- MySQL accounts use `mysql_native_password`, required by Metabase's current
  MySQL/MariaDB connector behavior.

## Remaining application setup

1. Create the first Metabase administrator through the public setup page.
2. Add the EspoCRM database using the `metabase_readonly` credentials stored in
   `/opt/app/.env`.
3. Restrict access to approved reporting users and groups.
4. Configure metadata visibility and hide technical/sensitive tables.
5. Schedule metadata syncs outside peak CRM hours.
6. Build and verify Benchteq dashboards.
