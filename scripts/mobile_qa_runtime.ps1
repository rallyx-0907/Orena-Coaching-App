<#
.SYNOPSIS
Start an isolated Orena runtime for native mobile QA.

.DESCRIPTION
Device/emulator QA needs a backend the app can actually sign in to. The shared
development runtime on port 8000 runs with APP_ENV=production and Google
authentication enabled, so /api/session/bootstrap answers 401 and only
signed-out states are reachable; completing real OAuth would require changing
the Google console redirect list, which is an explicit human gate (AGENTS.md
sec.15).

This script therefore starts a SEPARATE, throwaway instance:

  * APP_ENV=development with no Google credentials, so auth_enabled is false and
    the development harness is usable without touching OAuth configuration;
  * PERSISTENCE_BACKEND=sqlite with every database path redirected under
    /tmp/orena-qa inside the container, so the frozen SQLite archive on the
    shared ai-writing-coach-data volume is never written;
  * POSTGRES_RUNTIME_URL cleared and --no-deps, so authoritative PostgreSQL is
    neither used nor started;
  * a different published port, so the runtime on 8000 keeps running untouched.

Nothing here mutates production data, activates a provider, or changes release
state. The container is removed on exit (--rm).

.PARAMETER Port
Host port to publish. Defaults to 8010. The Android emulator reaches it at
http://10.0.2.2:<Port>.

.EXAMPLE
pwsh scripts/mobile_qa_runtime.ps1
#>
[CmdletBinding()]
param(
  [int]$Port = 8010
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
  Write-Host "Starting isolated Orena QA runtime on http://127.0.0.1:$Port" -ForegroundColor Cyan
  Write-Host "Android emulator reaches it at http://10.0.2.2:$Port" -ForegroundColor Cyan
  Write-Host "PostgreSQL, the shared SQLite archive, and the runtime on 8000 are untouched." -ForegroundColor DarkGray

  $env:MSYS_NO_PATHCONV = '1'
  $qaName = "orena-mobile-qa-$Port"
  & { $ErrorActionPreference = 'Continue'; docker rm -f $qaName 2>&1 | Out-Null }
  docker compose run -d --name $qaName --no-deps `
    --publish "127.0.0.1:${Port}:8000" `
    --env APP_ENV=development `
    --env ORENA_PUBLISHED_BIND_HOST=127.0.0.1 `
    --env ORENA_TRUST_DOCKER_PUBLISHED_PORT=1 `
    --env GOOGLE_CLIENT_ID= `
    --env GOOGLE_CLIENT_SECRET= `
    --env PERSISTENCE_BACKEND=sqlite `
    --env POSTGRES_RUNTIME_URL= `
    --env POSTGRES_SHADOW_URL= `
    --env WRITING_DB=/tmp/orena-qa/writing.db `
    --env AUTH_DB=/tmp/orena-qa/auth.db `
    --env PLATFORM_DB=/tmp/orena-qa/platform.db `
    --env PRODUCT_DB=/tmp/orena-qa/product.db `
    --env USER_DATA_ROOT=/tmp/orena-qa/users `
    --env PLATFORM_ADMIN_EMAILS= `
    --env BOOTSTRAP_OWNER_EMAIL= `
    writing-coach `
    sh -lc 'mkdir -p /tmp/orena-qa/users && exec python -m uvicorn app:app --host 0.0.0.0 --port 8000' | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "the QA runtime did not start" }

  # Host-side assertion of Docker's REAL published address (issue #140): refuse and stop unless loopback.
  python scripts/assert_published_loopback.py --container $qaName --port 8000
  if ($LASTEXITCODE -ne 0) { & { $ErrorActionPreference = 'Continue'; docker rm -f $qaName 2>&1 | Out-Null }; throw "the QA runtime is not published on loopback; it was stopped" }

  docker logs -f $qaName
}
finally {
  # Detached run, so the former --rm is done here.
  if ($qaName) { & { $ErrorActionPreference = 'Continue'; docker rm -f $qaName 2>&1 | Out-Null } }
  Pop-Location
}
