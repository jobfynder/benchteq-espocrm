$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    throw "Missing .env. Run scripts/initialize.ps1 first."
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path "backups" $timestamp
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$settings = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        $settings[$matches[1].Trim()] = $matches[2].Trim()
    }
}

$databaseName = if ($settings["ESPOCRM_DATABASE_NAME"]) { $settings["ESPOCRM_DATABASE_NAME"] } else { "espocrm" }
$projectName = if ($settings["COMPOSE_PROJECT_NAME"]) { $settings["COMPOSE_PROJECT_NAME"] } else { "benchteq-crm" }
$rootPassword = $settings["MARIADB_ROOT_PASSWORD"]
if (-not $rootPassword) {
    throw "MARIADB_ROOT_PASSWORD is missing from .env."
}

docker compose exec -T database mariadb-dump `
    --user=root `
    "--password=$rootPassword" `
    --single-transaction `
    --routines `
    --events `
    $databaseName | Set-Content (Join-Path $backupDir "database.sql")

docker run --rm `
    -v "${projectName}_espocrm-data:/source:ro" `
    -v "${PWD}/${backupDir}:/backup" `
    alpine tar czf /backup/espocrm-data.tgz -C /source .

docker run --rm `
    -v "${projectName}_espocrm-custom:/source:ro" `
    -v "${PWD}/${backupDir}:/backup" `
    alpine tar czf /backup/espocrm-custom.tgz -C /source .

docker run --rm `
    -v "${projectName}_espocrm-custom-client:/source:ro" `
    -v "${PWD}/${backupDir}:/backup" `
    alpine tar czf /backup/espocrm-custom-client.tgz -C /source .

Write-Host "Backup created at $backupDir"
