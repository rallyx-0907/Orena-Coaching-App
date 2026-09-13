<#
Bring the Orena review sandbox back up after a reboot.

Docker Desktop's Start button cannot do this on its own, and the reason is not
a fault: the sandbox PostgreSQL keeps PGDATA on tmpfs, so every machine restart
gives it an empty database, and the application refuses to start against a
schema it does not recognise. Two things therefore have to happen between the
two containers - wait for the database, then create the schema - and a button
that only flips container state has nowhere to put them.

So the order matters and is not optional:

  1. start orena-foundation-postgres and WAIT until it actually accepts
     connections (a container reporting "Up" is not yet listening);
  2. create the schema if the database came back empty;
  3. start orena-foundation-web, which verifies the schema and refuses if it
     is missing or at the wrong revision.

Starting the web container first - which is what clicking Start does - fails
with "failed to resolve host 'orena-foundation-postgres'", because a stopped
container has no DNS name on the network.

This script only ever calls `docker start`. It never recreates a container and
never removes a volume: recreating the database container is what would throw
away its contents. Production (8000) and preview (8010) are not touched.

    powershell -ExecutionPolicy Bypass -File scripts\start_orena_sandbox.ps1
#>

# Deliberately NOT 'Stop'. Windows PowerShell 5.1 turns a native program's
# stderr into ErrorRecords, and Alembic writes its INFO lines there - under
# 'Stop' a perfectly successful migration aborts the script. Every step below
# therefore checks its own outcome explicitly, which is the honest way to do it
# with native commands anyway.
$ErrorActionPreference = 'Continue'

$Postgres = 'orena-foundation-postgres'
$Web      = 'orena-foundation-web'
$Network  = 'orena-foundation-review'
$Image    = 'ai-writing-coach:local'
$Url      = 'http://127.0.0.1:8011'
$RuntimeUrl = "postgresql+psycopg://postgres@$Postgres`:5432/postgres"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "  $text" -ForegroundColor Green }
function Note($text) { Write-Host "  $text" -ForegroundColor Yellow }
function Die($text)  { Write-Host "`n  $text" -ForegroundColor Red; exit 1 }

function Invoke-Bootstrap($extraArg) {
    # stdout only; Alembic's stderr goes straight to the console where it is
    # readable, instead of being merged and mangled into ErrorRecords.
    $cmd = @(
        'run', '--rm', '--network', $Network,
        '-e', 'PERSISTENCE_BACKEND=postgresql',
        '-e', "POSTGRES_RUNTIME_URL=$RuntimeUrl",
        '-v', "${RepoRoot}:/workspace:ro", '-w', '/workspace', $Image,
        'python', 'scripts/bootstrap_runtime_schema.py'
    )
    if ($extraArg) { $cmd += $extraArg }
    return (& docker @cmd | Out-String)
}

# A container that exists but is stopped is what we expect after a reboot. One
# that does not exist at all is a different situation, and not one a start
# script should paper over by inventing a `docker run` whose flags it is
# guessing at.
foreach ($name in @($Postgres, $Web)) {
    $found = & docker ps -a --filter "name=$name" --format '{{.Names}}'
    if ($found -notcontains $name) {
        Die "Container '$name' does not exist. This script starts the existing sandbox; it does not create it. See docs/project/CURRENT_HANDOFF.md."
    }
}

Step "1. PostgreSQL"
& docker start $Postgres | Out-Null
$ready = $false
foreach ($i in 1..60) {
    & docker exec $Postgres pg_isready -U postgres | Out-Null
    if ($LASTEXITCODE -eq 0) { Ok "accepting connections after ${i}s"; $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { Die "$Postgres did not accept connections within 60s. Check: docker logs $Postgres" }

Step "2. Schema"
# Report before changing anything, so an unexpected state is visible rather
# than migrated over.
$report = Invoke-Bootstrap $null
$state = (($report -split "`r?`n") | Where-Object { $_ -match 'runtime schema:' }) -join ''
if (-not $state) { Die "Could not read the schema state. Check: docker logs $Postgres" }
Note $state.Trim()

if ($state -match 'empty') {
    Note "tmpfs database came back empty, as it does after every reboot - creating the schema"
    $created = Invoke-Bootstrap '--confirm'
    if ($LASTEXITCODE -ne 0) { Die "Schema creation failed." }
    $line = (($created -split "`r?`n") | Where-Object { $_ -match 'after creation:' }) -join ''
    if ($line -notmatch 'ready') { Die "Schema creation did not report ready: $line" }
    Ok $line.Trim()
}
elseif ($state -match 'mismatch') {
    # A revision the build does not expect is exactly when not to migrate
    # automatically. The operator states the revision they believe it is at.
    Die "Schema revision does not match this build. Do not migrate blindly - see docs/project/I2_ACTIVATION_RUNBOOK.md section 3."
}
elseif ($state -match 'ready') { Ok "already at the expected revision" }

Step "3. Application"
& docker start $Web | Out-Null
$serving = $false
foreach ($i in 1..60) {
    try {
        if ((Invoke-WebRequest -Uri "$Url/" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) {
            Ok "serving after ${i}s"; $serving = $true; break
        }
    } catch { }
    Start-Sleep -Seconds 1
}
if (-not $serving) { Die "$Web did not serve within 60s. Check: docker logs $Web" }

Step "Ready"
foreach ($route in @('/', '/api/learner-profile', '/api/dashboard')) {
    try {
        $code = (Invoke-WebRequest -Uri "$Url$route" -UseBasicParsing -TimeoutSec 5).StatusCode
    } catch {
        if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode } else { $code = 'ERR' }
    }
    Write-Host ("  {0,-24} {1}" -f $route, $code)
}
$revision = & docker exec $Postgres psql -U postgres -qAt -c 'SELECT version_num FROM alembic_version;'
Write-Host ("  {0,-24} {1}" -f 'schema revision', ($revision | Out-String).Trim())
Write-Host "`n  Open $Url" -ForegroundColor Green
Write-Host "  The database is temporary by design; learner rows do not survive a reboot." -ForegroundColor DarkGray
