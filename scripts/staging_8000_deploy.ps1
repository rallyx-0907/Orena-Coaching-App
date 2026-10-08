<#
Deploy the public, product-like staging runtime on :8000 (D-146) from an immutable release image. Run by the operator.

    powershell -ExecutionPolicy Bypass -File scripts\staging_8000_deploy.ps1 -Image orena:main-<sha>

What it runs, all from the same image and the same operator env file:

  web     ai-writing-coach-writing-coach-1   127.0.0.1:8000, network alias `writing-coach` (the tunnel's target)
  worker  ai-writing-coach-reading-worker-1  python -m writing_coach.reading_worker (Admin Reading jobs)

  env     %LOCALAPPDATA%\orena-product\staging-8000\runtime.env, operator-owned, outside Git, holds secrets.
          This script checks names and flags in it and never prints a value. Recreating either container from the
          same file gives the same runtime configuration.
  data    the named volume ai-writing-coach-data at /data; PostgreSQL is ai-writing-coach-postgres-1 on the compose
          network. No source is mounted. No volume is created or removed here.

It applies no migration: the image must be at the database's schema revision, or it stops. A schema change goes
through scripts/product_migration_pack.py (backup, rehearsal, authorized apply) first.

The containers it replaces are renamed <name>-before-<UTC stamp>, stopped, and set to restart=no; they are kept for
inspection, never started again by this script.
#>
param(
    [Parameter(Mandatory = $true)][string]$Image,
    [string]$EnvFile = (Join-Path $env:LOCALAPPDATA 'orena-product\staging-8000\runtime.env'),
    [string]$Network = 'ai-writing-coach_default',
    [string]$Volume = 'ai-writing-coach-data',
    [string]$Postgres = 'ai-writing-coach-postgres-1'
)

$ErrorActionPreference = 'Continue'
$Web = 'ai-writing-coach-writing-coach-1'
$Worker = 'ai-writing-coach-reading-worker-1'
function Fail([string]$message) { Write-Host "FAILED: $message"; exit 1 }

# 1. The env file: names and flags only.
if (-not (Test-Path $EnvFile)) { Fail "no env file at $EnvFile" }
$names = @{}
foreach ($line in [IO.File]::ReadAllLines($EnvFile)) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $i = $line.IndexOf('='); $names[$line.Substring(0, $i).Trim()] = $line.Substring($i + 1)
}
$required = 'APP_ENV', 'PUBLIC_BASE_URL', 'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'SESSION_SECRET', 'POSTGRES_RUNTIME_URL',
    'PERSISTENCE_BACKEND', 'AI_PROVIDER_SECRETS_KEY'
foreach ($name in $required) { if (-not $names[$name]) { Fail "$name is missing or empty in the env file" } }
if ($names['APP_ENV'] -ne 'staging') { Fail 'APP_ENV must be staging for :8000 (D-146)' }
if ($names['PRONUNCIATION_PROVIDER'] -match '^(demo|synthetic)') { Fail 'PRONUNCIATION_PROVIDER must not be a synthetic provider' }
$flags = 'APP_ENV', 'ORENA_ACCOUNT_BACKBONE', 'ORENA_PRACTICE_SESSION', 'AGENT_ENABLED', 'AGENT_VOICE_ENABLED',
    'AGENT_DAILY_SPEND_CAP_USD', 'AI_RUNTIME_MODE', 'PRONUNCIATION_PROVIDER', 'BILLING_ENABLED', 'ALLOW_LOCAL_ADMIN'
Write-Host ('flags: ' + (($flags | ForEach-Object { "$_=$(if ($names.ContainsKey($_)) { $names[$_] } else { '<unset>' })" }) -join ' '))

# 2. The image is at the database's schema revision.
$revision = (& docker.exe exec $Postgres psql -U becoming -d becoming -At -c 'select version_num from alembic_version' 2>$null | Out-String).Trim()
$head = (& docker.exe run --rm -w /app -e PERSISTENCE_BACKEND=sqlite $Image python scripts/product_migration_pack.py digest 2>$null |
    Where-Object { "$_" -like 'HEAD=*' }) -replace 'HEAD=', ''
if (-not $revision -or "$head".Trim() -ne $revision) { Fail "database is at '$revision', image head is '$head': migrate first" }
# Windows PowerShell drops the inner quotes of a Go template, so the label is read from the JSON instead.
$sha = "$(((& docker.exe image inspect $Image | ConvertFrom-Json)[0].Config.Labels).'org.opencontainers.image.revision')"
if (-not $sha) { Fail "$Image carries no org.opencontainers.image.revision label: build it from an exact commit" }
Write-Host "image $Image ($sha), schema $revision"

# 3. Replace web and worker.
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
foreach ($name in $Web, $Worker) {
    if (& docker.exe ps -a --format '{{.Names}}' | Where-Object { $_ -eq $name }) {
        & docker.exe update --restart=no $name | Out-Null
        & docker.exe stop $name | Out-Null
        & docker.exe rename $name "$name-before-$stamp"
        Write-Host "kept previous $name as $name-before-$stamp (stopped, restart=no)"
    }
}
$common = @('--restart', 'unless-stopped', '--network', $Network, '--env-file', $EnvFile, '-v', "${Volume}:/data",
    '--add-host', 'host.docker.internal:host-gateway', '--label', "orena.release=$sha", '--label', 'orena.runtime=staging-8000')
$webId = & docker.exe run -d --name $Web --network-alias writing-coach -p 127.0.0.1:8000:8000 @common $Image
if ($LASTEXITCODE -ne 0) { Fail 'the web container did not start' }
$workerId = & docker.exe run -d --name $Worker @common $Image python -m writing_coach.reading_worker
if ($LASTEXITCODE -ne 0) { Fail 'the reading worker did not start' }
Write-Host "web $("$webId".Substring(0, 12)), worker $("$workerId".Substring(0, 12))"

# 4. Readiness.
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    try { $ready = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/readiness' -TimeoutSec 3 } catch { continue }
    if ($ready.ready -and $ready.environment -eq 'staging') { break }
}
if (-not $ready.ready -or $ready.environment -ne 'staging') { Fail 'readiness did not report ready staging' }
Write-Host "readiness: ready=$($ready.ready) environment=$($ready.environment)"
Write-Host "worker: $(& docker.exe inspect $Worker --format '{{.State.Status}} restarts={{.RestartCount}}')"
