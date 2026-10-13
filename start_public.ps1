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
Write-Host "Writing Coach + Cloudflare Tunnel are running." -ForegroundColor Green
docker compose --profile public ps
