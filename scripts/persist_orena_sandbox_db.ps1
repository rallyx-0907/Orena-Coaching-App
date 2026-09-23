<#
Give the :8011 sandbox database a home that survives Docker restarting.

`orena-foundation-postgres` keeps PGDATA on **tmpfs**. That was deliberate once
- "the database is temporary by design" - but it means the container's contents
are gone whenever Docker Desktop recreates it, which it does on its own after a
crash or an update. On 2026-09-23 that quietly emptied a seeded test learner of
3 012 words mid-session, and the emptiness looked exactly like an application
fault until the container was inspected.

This script moves PGDATA onto a named volume, `orena-foundation-sandbox-data`,
keeping what is in the database now.

It is written to be run by a person, once, and it is idempotent: run against a
container that already has the volume, it changes nothing and says so.

    powershell -ExecutionPolicy Bypass -File scripts\persist_orena_sandbox_db.ps1

What it touches, and what it does not:

- it recreates **one** container, `orena-foundation-postgres`, the :8011
  sandbox's database, and restarts `orena-foundation-web` after it;
- it creates **one new** volume, `orena-foundation-sandbox-data`. It never
  removes a volume, and it never goes near `ai-writing-coach-data` or
  `ai-writing-coach-postgres-data`, which belong to production and preview;
- production (8000), preview (8010) and every other lane's containers are not
  touched. Confirm no other lane is operating the sandbox before running it.

The dump it takes first is written beside the repository in a timestamped file
and is **not** deleted, so a failed restore is recoverable by hand.
#>

# Native stderr becomes ErrorRecords under 'Stop' in Windows PowerShell 5.1,
# and pg_dumpall and docker both write progress there. Every step checks its
# own outcome instead.
$ErrorActionPreference = 'Continue'

$Postgres = 'orena-foundation-postgres'
$Web      = 'orena-foundation-web'
$Network  = 'orena-foundation-review'
$Volume   = 'orena-foundation-sandbox-data'
$Image    = 'postgres:17-alpine'
$Url      = 'http://127.0.0.1:8011'

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "  $text" -ForegroundColor Green }
function Note($text) { Write-Host "  $text" -ForegroundColor Yellow }
function Die($text)  { Write-Host "`n  $text" -ForegroundColor Red; exit 1 }

Step "0. What is there now"
$found = & docker ps -a --filter "name=$Postgres" --format '{{.Names}}'
if ($found -notcontains $Postgres) {
    Die "Container '$Postgres' does not exist. This script moves an existing sandbox database onto a volume; it does not create a sandbox."
}
$mounted = & docker inspect $Postgres --format '{{range .Mounts}}{{.Name}} {{end}}'
if ($mounted -match [regex]::Escape($Volume)) {
    Ok "already on '$Volume' - nothing to do."
    exit 0
}
$running = & docker ps --filter "name=$Postgres" --format '{{.Names}}'
if ($running -notcontains $Postgres) {
    Die "'$Postgres' is not running, so there is nothing to dump. Start the sandbox first (scripts\start_orena_sandbox.ps1), then run this."
}
Note "PGDATA is on tmpfs; moving it to the named volume '$Volume'."

Step "1. Dump what is in there"
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$dump  = Join-Path (Split-Path -Parent $PSScriptRoot) "..\orena-sandbox-dump-$stamp.sql"
$dump  = [System.IO.Path]::GetFullPath($dump)
& docker exec $Postgres pg_dumpall -U postgres > $dump
if ($LASTEXITCODE -ne 0) { Die "pg_dumpall failed; nothing has been changed." }
$size = (Get-Item $dump).Length
if ($size -lt 1024) { Die "The dump is only $size bytes, which is not a database. Nothing has been changed. See $dump" }
Ok "$([math]::Round($size / 1KB)) KB -> $dump"

Step "2. Recreate the database container on the volume"
& docker stop $Web      | Out-Null
& docker stop $Postgres | Out-Null
& docker volume create $Volume | Out-Null
# The only destructive step, and it is the container, never a volume: the
# contents it is about to lose are in the dump taken above.
& docker rm $Postgres | Out-Null
if ($LASTEXITCODE -ne 0) { Die "Could not remove '$Postgres'. The dump is at $dump and the old container is still there." }
& docker run -d --name $Postgres --network $Network `
    -e POSTGRES_HOST_AUTH_METHOD=trust `
    -v "${Volume}:/var/lib/postgresql/data" $Image | Out-Null
if ($LASTEXITCODE -ne 0) { Die "Could not start '$Postgres' on the volume. The dump is at $dump." }

$ready = $false
foreach ($i in 1..60) {
    & docker exec $Postgres pg_isready -U postgres | Out-Null
    if ($LASTEXITCODE -eq 0) { Ok "accepting connections after ${i}s"; $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { Die "'$Postgres' did not accept connections within 60s. The dump is at $dump. Check: docker logs $Postgres" }

Step "3. Restore"
Get-Content -Raw $dump | & docker exec -i $Postgres psql -U postgres -q -v ON_ERROR_STOP=1 -d postgres | Out-Null
if ($LASTEXITCODE -ne 0) { Die "Restore failed. The dump is at $dump and can be replayed by hand: docker exec -i $Postgres psql -U postgres < <dump>" }
$revision = (& docker exec $Postgres psql -U postgres -qAt -c 'SELECT version_num FROM alembic_version;' | Out-String).Trim()
$words = (& docker exec $Postgres psql -U postgres -qAt -c 'SELECT COUNT(*) FROM saved_words;' | Out-String).Trim()
if (-not $revision) { Die "Restored, but the schema revision is missing. The dump is at $dump." }
Ok "schema revision $revision, $words saved words"

Step "4. Application"
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
if (-not $serving) { Die "'$Web' did not serve within 60s. Check: docker logs $Web" }

Step "Done"
Write-Host "  The sandbox database is on the named volume '$Volume'." -ForegroundColor Green
Write-Host "  A Docker Desktop restart no longer empties it; only removing that volume does." -ForegroundColor Green
Write-Host "  The dump is kept at $dump - delete it yourself when you no longer want it." -ForegroundColor DarkGray
