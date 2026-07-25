# Elestio and GitHub setup

## Information to collect from Elestio

- EspoCRM public URL and version.
- SSH host, port, username and application directory.
- Whether EspoCRM runs directly on the host or inside a container.
- Elestio backup/snapshot procedure and retention.
- Staging service availability.
- PHP command/path and ownership requirements for deployed files.

Do not guess the application path. Confirm it over SSH with read-only commands before enabling deployment.

## GitHub repository settings

- Keep the repository private.
- Default branch: `main`.
- Enable secret scanning and push protection when available.
- Create a protected `production` environment with required reviewers.
- Protect `main`: require pull requests, one approval, passing `Validate`, resolved conversations, and no force pushes.
- Limit Actions permissions to read repository contents by default.
- Store Elestio connection values only as Actions secrets.
- Store the public production hostname as the environment variable `ESPOCRM_PRODUCTION_HOSTNAME`.

## First deployment checklist

1. Export or snapshot the current Elestio service.
2. Inventory existing `custom/` and `client/custom/` files.
3. Import those files into this repository before deploying with `--delete`.
4. Confirm no credentials or customer data are present.
5. Test rebuild and application check commands manually.
6. After importing and reviewing the live customizations, create an empty
   `.benchteq-managed` marker in the confirmed application root. The deployment
   workflow refuses to run without it.
7. Run the workflow against staging.
8. Approve production deployment and complete smoke tests.
