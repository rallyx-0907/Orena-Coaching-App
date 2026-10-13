$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env. Add CLOUDFLARE_TUNNEL_TOKEN, then run this script again." -ForegroundColor Yellow
    exit 1
}

$envText = Get-Content ".env" -Raw
if ($envText -match "(?m)^CLOUDFLARE_TUNNEL_TOKEN=\s*$") {
    Write-Host "CLOUDFLARE_TUNNEL_TOKEN is empty in .env" -ForegroundColor Red
    exit 1
}

# Fail closed (issue #137): a development runtime with sign-in off must never be put behind the tunnel. The same
# preflight the staging deploy relies on refuses it, before any container starts. Stdlib only; no secret is printed.
python scripts/validate_public_staging_readiness.py --env-file .env
if ($LASTEXITCODE -ne 0) {
    Write-Host "Public readiness preflight failed; the tunnel was not started." -ForegroundColor Red
    exit 1
}

docker compose --profile public up -d --build
# Host-side assertion of Docker's REAL published address (issue #140): refuse and stop unless the app port is loopback.
$optIn = @()
if ($env:ORENA_INSECURE_DEV_LAN_BIND_HOST) { $optIn = @('--lan-opt-in', '--probe-url', 'http://127.0.0.1:8000/api/me') }
$webId = (docker compose --profile public ps -q writing-coach | Out-String).Trim()
if (-not $webId) { Write-Host "The app container was not found; cannot verify its published address." -ForegroundColor Red; exit 1 }
python scripts/assert_published_loopback.py --container $webId --port 8000 @optIn
if ($LASTEXITCODE -ne 0) { Write-Host "The published address is not loopback; the app container was stopped." -ForegroundColor Red; exit 1 }
Write-Host "Writing Coach + Cloudflare Tunnel are running." -ForegroundColor Green
docker compose --profile public ps
