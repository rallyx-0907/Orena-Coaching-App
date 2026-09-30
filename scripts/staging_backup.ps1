<#
Back up the :8011 staging database in one command (D-101 A).

    powershell -ExecutionPolicy Bypass -File scripts\staging_backup.ps1

Takes a custom-format `pg_dump` inside the staging PostgreSQL container (the
application image ships no PostgreSQL client; the postgres image does), copies
it out to a folder outside the repository, and checks it by listing it with
`pg_restore --list`. A dump that cannot be listed is not a backup: the script
then exits non-zero, and `staging_update.ps1` does not migrate.

It only reads the database. It never stops, recreates or removes a container,
and never touches a volume. Production (8000) and preview (8010) are other
containers and are never named here.

Output: the backup's path, size, SHA-256 and the schema revision it holds. The
last line is `BACKUP=<path>` for `staging_update.ps1` to read.
#>
param(
    [string]$OutDir = (Join-Path $env:LOCALAPPDATA 'orena-staging\backups'),
    # Another non-production PostgreSQL container, e.g. the lane runtime's `orena-next-verify-pg`
    # before a lane migration (D-105). Production and preview are refused by name.
    [string]$Postgres = 'orena-foundation-postgres'
)

# Native commands write progress to stderr; outcomes are checked explicitly.
$ErrorActionPreference = 'Continue'

$Database = 'postgres'
if ($Postgres -match '^ai-writing-coach' -or $Postgres -match 'preview') {
    Write-Host "  $Postgres looks like production or preview; this script does not back those up." -ForegroundColor Red
    exit 1
}

function Die($text) { Write-Host "`n  $text" -ForegroundColor Red; exit 1 }
function Ok($text)  { Write-Host "  $text" -ForegroundColor Green }

$running = & docker inspect $Postgres --format '{{.State.Running}}' 2>$null
if ($running -ne 'true') { Die "$Postgres is not running; nothing was backed up." }
& docker exec $Postgres pg_isready -U postgres | Out-Null
if ($LASTEXITCODE -ne 0) { Die "$Postgres is not accepting connections; nothing was backed up." }

$revision = (& docker exec $Postgres psql -U postgres -d $Database -qAt -c 'SELECT version_num FROM alembic_version;' 2>$null | Out-String).Trim()
if (-not $revision) { $revision = 'no-revision' }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$name = "staging-$stamp-$revision.dump"
$inside = "/tmp/$name"
$outside = Join-Path $OutDir $name

& docker exec $Postgres pg_dump -U postgres -d $Database -Fc -f $inside
if ($LASTEXITCODE -ne 0) { Die "pg_dump failed; nothing was backed up." }

# Listing the dump is the check that it is readable, not just written.
$listing = & docker exec $Postgres pg_restore --list $inside
if ($LASTEXITCODE -ne 0 -or -not ($listing | Where-Object { $_ -match 'TABLE DATA' })) {
    & docker exec $Postgres rm -f $inside | Out-Null
    Die "The dump could not be listed or holds no table data; treat this backup as failed."
}

& docker cp "${Postgres}:$inside" $outside | Out-Null
$copied = $LASTEXITCODE -eq 0
& docker exec $Postgres rm -f $inside | Out-Null
if (-not $copied -or -not (Test-Path $outside) -or (Get-Item $outside).Length -eq 0) {
    Die "Copying the dump out of $Postgres failed; treat this backup as failed."
}

$size = (Get-Item $outside).Length
$hash = (Get-FileHash -Algorithm SHA256 $outside).Hash.ToLower()
$tables = ($listing | Where-Object { $_ -match 'TABLE DATA' }).Count
Ok "backup   $outside"
Ok "size     $size bytes, $tables tables with data"
Ok "sha256   $hash"
Ok "revision $revision"
Write-Host "BACKUP=$outside"
exit 0
