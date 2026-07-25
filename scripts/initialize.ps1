$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is not installed or docker is not on PATH. Install Docker Desktop, restart the terminal, and run this script again."
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"

    function New-RandomSecret {
        $bytes = New-Object byte[] 36
        [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        return [Convert]::ToBase64String($bytes).Replace("+", "A").Replace("/", "B").Replace("=", "")
    }

    $content = Get-Content ".env" -Raw
    $content = $content.Replace("CHANGE_ME_STRONG_ADMIN_PASSWORD", (New-RandomSecret))
    $content = $content.Replace("CHANGE_ME_STRONG_DATABASE_PASSWORD", (New-RandomSecret))
    $content = $content.Replace("CHANGE_ME_STRONG_ROOT_PASSWORD", (New-RandomSecret))
    Set-Content ".env" $content -NoNewline
    Write-Host "Created .env with generated passwords. Store the admin password in Benchteq's password manager."
}

docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps

