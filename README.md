# Benchteq EspoCRM

Version-controlled customizations and operations for Benchteq's existing Elestio-hosted EspoCRM instance.

The repository is not a copy of production data and must never contain credentials, customer records, database exports, uploaded files, or EspoCRM's generated `data/config*.php` files.

## Repository layout

- `custom/` — server-side EspoCRM customizations deployed to `custom/`.
- `client/custom/` — browser-side customizations deployed to `client/custom/`.
- `.github/workflows/validate.yml` — checks every change.
- `.github/workflows/deploy-elestio.yml` — manually triggered Elestio deployment.
- `compose.yaml` — optional isolated local/test environment, not Elestio production.
- `BENCHTEQ_BLUEPRINT.md` — business process and integration design.
- `infrastructure/metabase/` — pinned Metabase reporting service and subdomain
  proxy specification.

## Elestio connection

Configure these GitHub Actions repository secrets:

- `ELESTIO_HOST` — SSH hostname supplied by Elestio.
- `ELESTIO_SSH_USER` — SSH user supplied by Elestio.
- `ELESTIO_SSH_PRIVATE_KEY` — dedicated deployment private key.
- `ELESTIO_STACK_PATH` — absolute directory containing Elestio's Compose file.
- `ELESTIO_SSH_PORT` — optional; defaults to `22`.

Use a dedicated deployment key and restrict it to this service where Elestio permits. Do not reuse a personal SSH key.

Deployments are intentionally manual and default to `plan`, which uses rsync
dry-run mode and changes nothing. From GitHub, open **Actions → Deploy to
Elestio → Run workflow**, supply the expected production hostname and a fresh
Elestio snapshot reference, then approve the production environment. `apply`
mode additionally requires the exact confirmation `BACKUP-CONFIRMED` and the
server-side `.benchteq-managed` marker. The job uploads only `custom/` and
`client/custom/`, preserves `www-data` ownership, rebuilds EspoCRM, and checks
the application.

Before enabling deployment:

1. Confirm the exact Elestio SSH host, user, port and Compose stack path.
2. Take an Elestio backup or snapshot.
3. Configure a protected GitHub environment named `production` with required reviewers.
4. Run the workflow in `plan` mode and review every proposed change.
5. Use `apply` only after the plan is correct and the snapshot is recoverable.

## Optional local test instance

Docker Desktop is required only for isolated local testing. Run:

```powershell
.\scripts\initialize.ps1
```

The script creates an ignored `.env` with random passwords, validates Compose, downloads images and starts a disposable test stack at `http://localhost:8080`.

Verify the deployment:

```powershell
.\scripts\healthcheck.ps1
```

Create a backup:

```powershell
.\scripts\backup.ps1
```

## Customization workflow

1. Create a branch from `main`.
2. Add only supported EspoCRM extension files under `custom/` or `client/custom/`.
3. Open a pull request and pass validation.
4. Review generated metadata carefully; avoid editing core application files.
5. Merge after approval, back up Elestio, and manually deploy.
6. Perform a rebuild and business smoke tests.

## Routine operations

```powershell
docker compose ps
docker compose logs --tail 200 espocrm daemon websocket
docker compose restart
docker compose down
```

`docker compose down` preserves data. Do not use `--volumes` unless intentionally deleting all CRM and database data.

## EspoCRM upgrade workflow

1. Read the EspoCRM release notes and verify extension compatibility.
2. Create and verify an Elestio backup/snapshot.
3. Test the target version and this repository's customizations in staging.
4. Use Elestio's supported upgrade process.
5. Run EspoCRM rebuild, health checks, integration tests, and business smoke tests.
