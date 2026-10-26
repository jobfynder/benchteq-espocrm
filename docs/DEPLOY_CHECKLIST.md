# Elestio deploy checklist

How the app deploys, and what must be true before every production deploy.

## How deployment works

- Deploys are manual. Run **Actions → Deploy to Elestio** (`.github/workflows/deploy-elestio.yml`). It uses the protected `production` environment.
- The workflow syncs only `custom/` and `client/custom/` to the Elestio host with rsync over SSH. It does not touch the database, the image, or `data/`.
- `plan` mode runs `rsync --dry-run` and changes nothing. `apply` mode syncs with `--delete`, fixes ownership to `www-data`, runs `php command.php rebuild`, then `app-check`.
- Target: stack path `/opt/app` on the Elestio service `espocrm-wsnus` (see `ELESTIO_SETUP.md`). The workflow refuses to apply unless `/opt/app/.benchteq-managed` exists.
- Built-in guards in `apply`: the typed hostname must match `ESPOCRM_PRODUCTION_HOSTNAME`, a `backup_snapshot_reference` is required, and `production_confirmation` must be exactly `BACKUP-CONFIRMED`.

## Backup gate

The workflow only checks that a backup reference was typed in. It cannot check that the backup exists. A person has to confirm it.

Last backup recorded for this project: **2026-10-14 19:35:57, 794M.** This was not verified from the repo or from Elestio. Treat it as a note, not proof.

Before each `apply`, take a fresh backup, using one or both:

1. Elestio dashboard: create a snapshot/backup for `espocrm-wsnus`. Record its identifier, size and time.
2. On the host: `STACK_PATH=/opt/app bash scripts/backup-production.sh`. This writes a gzipped MySQL dump and a tarball of both customization folders to `/opt/app/backups/benchteq-implementation-<timestamp>/`.

Confirm the backup is usable: the size is plausible (about the size of the last one, 794M, or larger), the timestamp is from the same day as the deploy, and the Elestio snapshot shows as completed. A restore test is not part of each deploy, but do one after any major change.

## Checklist

Before:
- [ ] The PR is merged to `main` and `Validate` is green.
- [ ] Fresh backup taken and verified (see above). Identifier recorded: `__________`
- [ ] Run the workflow in `plan` mode and read every itemized change. Any unexpected deletion stops the deploy.
- [ ] No credentials or customer data are in the diff.

Deploy:
- [ ] Run `apply` with the hostname, the backup identifier, and `BACKUP-CONFIRMED`.
- [ ] All workflow steps pass, including the final `app-check`.

After:
- [ ] Log in at `https://crm.jobfynder.com`.
- [ ] Open and edit a record, and check the changed feature.
- [ ] Background jobs run (daemon container up), email works, WebSocket works.
- [ ] Note the result and the backup identifier in the PR.

## Rollback

Restore `custom/` and `client/custom/` from `espocrm-custom.tgz` in the backup folder (or redeploy the previous commit), then run `php command.php rebuild`. If data is damaged, restore the Elestio snapshot or the SQL dump. Restoring the database is a production change: get the owner's approval first.

## Gaps to close

- Elestio snapshot retention and restore steps are still listed as "to collect" in `ELESTIO_SETUP.md`.
- The image tag is `espocrm/espocrm:latest`. Pin a tested version before the next upgrade.
- A staging service exists but its details are not recorded here. Deploy there first once they are.
