$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
Write-Host "Starting development mode with Docker Compose Watch..." -ForegroundColor Cyan
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
# Host-side assertion of Docker's REAL published address (issue #140): refuse and stop unless the app port is loopback.
$optIn = @()
if ($env:ORENA_INSECURE_DEV_LAN_BIND_HOST) { $optIn = @('--lan-opt-in', '--probe-url', 'http://127.0.0.1:8000/api/me') }
$webId = (docker compose -f compose.yaml -f compose.dev.yaml ps -q writing-coach | Out-String).Trim()
if (-not $webId) { Write-Host "The app container was not found; cannot verify its published address." -ForegroundColor Red; exit 1 }
python scripts/assert_published_loopback.py --container $webId --port 8000 @optIn
if ($LASTEXITCODE -ne 0) { Write-Host "The published address is not loopback; the app container was stopped." -ForegroundColor Red; exit 1 }
docker compose -f compose.yaml -f compose.dev.yaml watch
