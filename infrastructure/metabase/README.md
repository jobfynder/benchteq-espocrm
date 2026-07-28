# Metabase reporting service

This directory defines a production Metabase service alongside the Elestio
EspoCRM stack. Metabase is not installed inside the EspoCRM container.

## Architecture

- Public URL: `https://reports.jobfynder.com`
- Nginx origin: `172.17.0.1:8787`
- Container port: `3000`
- Image: `metabase/metabase:v0.63.1.8`
- Application database: MySQL schema `metabase_app`
- Analytics source: EspoCRM schema `espocrm`
- Analytics account: `metabase_readonly` with `SELECT` and `SHOW VIEW` only

Metabase's application database is writable because it stores users,
dashboards, questions, and settings. Its EspoCRM reporting connection is
strictly read-only.

## DNS

Create a CNAME record:

```text
Name: reports
Target: espocrm-wsnus-u14612.vm.elestio.app
```

Use DNS-only mode until Elestio obtains and serves the certificate, then enable
the DNS provider's proxy if desired and verify end-to-end TLS again.

## Production procedure

1. Create a fresh Elestio backup and record its identifier.
2. Generate independent random passwords for `metabase_app` and
   `metabase_readonly`.
3. Create the `metabase_app` schema and both database accounts.
4. Add `METABASE_DB_PASSWORD` and `METABASE_REPORTING_PASSWORD` to
   `/opt/app/.env`; never commit them.
   Generate and store `METABASE_ENCRYPTION_SECRET_KEY` before adding database
   credentials through Metabase.
5. Merge `compose.override.yml` into `/opt/app/docker-compose.override.yml`.
6. Validate with `docker compose config --quiet`.
7. Start only Metabase with `docker compose up -d metabase`.
8. Confirm `http://172.17.0.1:8787/api/health` returns healthy.
9. Install the Nginx configuration and reload only after `nginx -t` succeeds.
10. Complete the Metabase administrator setup at the reporting subdomain.
11. Add the EspoCRM database in Metabase using:
    - host: `mysql`
    - port: `3306`
    - database: `espocrm`
    - user: `metabase_readonly`
    - password: the reporting password from the server secret store
12. Disable public sharing, embedding, actions, uploads, and model persistence.
    AI features and anonymous telemetry are disabled by the Compose environment.

## Rollback

Remove the Nginx subdomain configuration and reload Nginx, then run:

```bash
cd /opt/app
docker compose stop metabase
docker compose rm -f metabase
```

Do not remove the `metabase_app` schema until dashboards and settings have been
exported or the rollback retention period has ended.

