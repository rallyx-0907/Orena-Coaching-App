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
# Runtime safety keys (pre-deploy hardening): presence and format only; a value is never printed.
# AI_DAILY_SPEND_WARN_RATIO may be absent (BQ): Admin > Policies then holds it (`ai.daily_spend_warn_ratio`); when it
# is set it pins the policy and must be valid.
$runtimeKeys = 'AI_DAILY_SPEND_CEILING_USD', 'LEGAL_EFFECTIVE_DATE', 'AGENT_MEMORY_HMAC_KEYS',
    'AGENT_MEMORY_RETENTION_SWEEP'
foreach ($name in $runtimeKeys) { if (-not "$($names[$name])".Trim()) { Fail "$name is missing or empty in the env file" } }
$num = [double]0
$ci = [Globalization.CultureInfo]::InvariantCulture
if (-not [double]::TryParse("$($names['AI_DAILY_SPEND_CEILING_USD'])".Trim(), 'Float', $ci, [ref]$num) -or $num -le 0) { Fail 'AI_DAILY_SPEND_CEILING_USD must be a number above 0' }
if ("$($names['AI_DAILY_SPEND_WARN_RATIO'])".Trim() -and (-not [double]::TryParse("$($names['AI_DAILY_SPEND_WARN_RATIO'])".Trim(), 'Float', $ci, [ref]$num) -or $num -le 0 -or $num -gt 1)) { Fail 'AI_DAILY_SPEND_WARN_RATIO must be a number above 0 and at most 1' }
# A real calendar date, read the way the app reads it (consent.legal_effective_date): 2026-02-30 is refused.
$legalDay = [datetime]::MinValue
if ("$($names['LEGAL_EFFECTIVE_DATE'])".Trim() -notmatch '^\d{4}-\d{2}-\d{2}$' -or -not [datetime]::TryParseExact("$($names['LEGAL_EFFECTIVE_DATE'])".Trim(), 'yyyy-MM-dd', $ci, [Globalization.DateTimeStyles]::None, [ref]$legalDay)) { Fail 'LEGAL_EFFECTIVE_DATE must be a real calendar date, YYYY-MM-DD' }
# The app's own rules (writing_coach/agent/memory_keys.py): v<1-9999>:<secret without whitespace, 32+ characters>, each version once.
$seenVersions = @{}
foreach ($entry in ("$($names['AGENT_MEMORY_HMAC_KEYS'])" -split ',')) {
    $entry = $entry.Trim()
    if (-not $entry) { continue }
    if ($entry -notmatch '^v(?<version>[1-9][0-9]{0,3}):(?<secret>\S+)$') { Fail 'AGENT_MEMORY_HMAC_KEYS entries are v<version>:<secret>' }
    if ($seenVersions.ContainsKey($Matches['version'])) { Fail "AGENT_MEMORY_HMAC_KEYS names v$($Matches['version']) twice" }
    if ($Matches['secret'].Length -lt 32) { Fail "AGENT_MEMORY_HMAC_KEYS v$($Matches['version']) is shorter than 32 characters" }
    $seenVersions[$Matches['version']] = $true
}
if ($seenVersions.Count -eq 0) { Fail 'AGENT_MEMORY_HMAC_KEYS lists no key' }
if ("$($names['AGENT_MEMORY_RETENTION_SWEEP'])".Trim() -cnotmatch '^(on|off)$') { Fail 'AGENT_MEMORY_RETENTION_SWEEP must be exactly on or off' }
# Deletion sweeps are off until switched on; say so, never fail on it.
foreach ($sweep in 'FEEDBACK_RETENTION_SWEEP', 'AGENT_TURN_RETENTION_SWEEP') {
    if ("$($names[$sweep])".Trim() -notin 'true', 'on') { Write-Warning "$sweep is not switched on: that data is kept until the sweep is enabled" }
}
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
    '--add-host', 'host.docker.internal:host-gateway', '--label', "orena.release=$sha", '--label', 'orena.runtime=staging-8000',
    '--log-opt', 'max-size=10m', '--log-opt', 'max-file=5')
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
# Host-side, READ-ONLY assertion of Docker's real published address (issue #140): fails loudly, never stops or
# changes the human-operated runtime (D-127). Rollback stays the operator's.
$global:LASTEXITCODE = 1
if (Get-Command python -ErrorAction SilentlyContinue) { & python (Join-Path $PSScriptRoot 'assert_published_loopback.py') --container $Web --port 8000 --no-stop } else { Write-Host "python was not found; the published address cannot be verified." -ForegroundColor Red }
if ($LASTEXITCODE -ne 0) { Fail "$Web is not published on loopback only; investigate before treating staging as deployed" }
Write-Host "readiness: ready=$($ready.ready) environment=$($ready.environment)"
Write-Host "worker: $(& docker.exe inspect $Worker --format '{{.State.Status}} restarts={{.RestartCount}}')"
