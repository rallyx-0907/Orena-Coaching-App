<#
Rehearse a runtime update on a COPY of its data before the real run (D-127, completion plan item 1).

    powershell -ExecutionPolicy Bypass -File scripts\product_migration_rehearsal.ps1 -Backup <folder from product_backup.ps1>

What it does, all on throwaway resources, never on the runtime the backup came from:
1. checks the backup against its manifest (sizes and SHA-256 of database.dump and files.tar.gz);
2. starts an ephemeral PostgreSQL container (`--rm`, an anonymous volume: no named volume is created or
   removed) on its own network, and restores the dump into it;
3. reads the schema revision and an exact row count for every table, and compares them with the manifest:
   the restore must reproduce the backup exactly;
4. runs this checkout's migration chain against the copy with `scripts/product_migration_pack.py rehearse`
   (application image, repository mounted read-only): one revision per step, 20260924_0016 by the reviewed
   Reading cutover, each step timed - the same steps `product_migration_pack.py apply` runs on :8000 (D-143);
5. checks the result: the head, ready, every backed-up row where its table now lives (0016 renames the old
   Reading tables into the read-only archive), and the archive frozen;
6. lists the files archive end to end (a corrupt archive fails here);
7. stops the ephemeral container (it removes itself) and its network, and writes rehearsal.json beside
   the backup. Exit code 0 only when every check passes.
#>
param(
    [Parameter(Mandatory = $true)][string]$Backup,
    [string]$AppImage = 'ai-writing-coach:local',
    [string]$ToolImage = 'postgres:17-alpine',
    [string]$Repository = ''
)
if (-not $Repository) { $Repository = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..')).Path }

$ErrorActionPreference = 'Continue'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ').ToLower()
$network = "orena-rehearsal-$stamp"
$pg = "orena-rehearsal-pg-$stamp"
$report = [ordered]@{ backup = $Backup; started_at = (Get-Date).ToUniversalTime().ToString('o'); checks = @() }

function Note([string]$name, [bool]$passed, [string]$detail) {
    $script:report.checks += [ordered]@{ check = $name; passed = $passed; detail = $detail }
    Write-Host ("[{0}] {1}: {2}" -f ($(if ($passed) { 'PASS' } else { 'FAIL' }), $name, $detail))
}
function Invoke-Docker([string[]]$arguments) {
    $output = & docker.exe @arguments 2>&1
    return @{ ok = ($LASTEXITCODE -eq 0); out = $output }
}
function Finish([int]$code) {
    Invoke-Docker @('stop', $pg) | Out-Null
    Invoke-Docker @('network', 'rm', $network) | Out-Null
    $script:report.finished_at = (Get-Date).ToUniversalTime().ToString('o')
    $script:report.passed = ($code -eq 0)
    $script:report | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 (Join-Path $Backup 'rehearsal.json')
    Write-Host ("REHEARSAL={0}" -f $(if ($code -eq 0) { 'PASS' } else { 'FAIL' }))
    exit $code
}

$manifest = Get-Content -Raw (Join-Path $Backup 'manifest.json') | ConvertFrom-Json
foreach ($file in $manifest.files) {
    $path = Join-Path $Backup $file.name
    $ok = (Test-Path $path) -and ((Get-Item $path).Length -eq $file.bytes) -and ((Get-FileHash -Algorithm SHA256 $path).Hash.ToLower() -eq $file.sha256)
    Note "integrity $($file.name)" $ok "$($file.bytes) bytes"
    if (-not $ok) { Finish 1 }
}

$countSql = "select table_name || '=' || (xpath('/row/c/text()', query_to_xml('select count(*) as c from public.' || quote_ident(table_name), false, true, '')))[1]::text from information_schema.tables where table_schema = 'public' and table_type = 'BASE TABLE' order by table_name"
function Counts() {
    $result = @{}
    foreach ($line in (Invoke-Docker @('exec', $pg, 'psql', '-U', 'rehearsal', '-d', 'rehearsal', '-At', '-c', $countSql)).out) {
        $parts = "$line".Split('=')
        if ($parts.Count -eq 2) { $result[$parts[0]] = [int64]$parts[1] }
    }
    return $result
}

(Invoke-Docker @('network', 'create', $network)).ok | Out-Null
$started = Invoke-Docker @('run', '-d', '--rm', '--name', $pg, '--network', $network, '-e', 'POSTGRES_USER=rehearsal', '-e', 'POSTGRES_PASSWORD=rehearsal', '-e', 'POSTGRES_DB=rehearsal', '-v', "${Backup}:/backup:ro", $ToolImage)
if (-not $started.ok) { Note 'ephemeral postgres' $false ($started.out | Out-String); Finish 1 }
# The image's entrypoint first runs a temporary server to initialise the database, and pg_isready already answers
# for it; a restore into that server is lost when it stops. Ready means the init process has completed and the real
# server answers.
$ready = $false
for ($i = 0; $i -lt 90 -and -not $ready; $i++) {
    Start-Sleep -Seconds 1
    $initialised = ((& docker.exe logs $pg 2>&1 | Out-String) -match 'PostgreSQL init process complete')
    $ready = $initialised -and (Invoke-Docker @('exec', $pg, 'pg_isready', '-U', 'rehearsal', '-d', 'rehearsal')).ok
}
Note 'ephemeral postgres' $ready $pg
if (-not $ready) { Finish 1 }

$restored = Invoke-Docker @('exec', $pg, 'pg_restore', '-U', 'rehearsal', '-d', 'rehearsal', '--no-owner', '--no-acl', '/backup/database.dump')
Note 'pg_restore' $restored.ok $(if ($restored.ok) { 'restored' } else { ($restored.out | Select-Object -First 5 | Out-String).Trim() })
if (-not $restored.ok) { Finish 1 }
$before = Counts
$revisionBefore = ((Invoke-Docker @('exec', $pg, 'psql', '-U', 'rehearsal', '-d', 'rehearsal', '-At', '-c', 'select version_num from alembic_version')).out | Out-String).Trim()
$mismatch = @()
foreach ($table in $manifest.table_counts.PSObject.Properties) {
    if ($before[$table.Name] -ne [int64]$table.Value) { $mismatch += "$($table.Name): backup $($table.Value), restored $($before[$table.Name])" }
}
Note 'restore reproduces the backup' (($mismatch.Count -eq 0) -and ($revisionBefore -eq $manifest.schema_revision)) $(if ($mismatch.Count) { $mismatch -join '; ' } else { "revision $revisionBefore, $($before.Count) tables" })
if ($mismatch.Count -or $revisionBefore -ne $manifest.schema_revision) { Finish 1 }

$url = "postgresql+psycopg://rehearsal:rehearsal@${pg}:5432/rehearsal"
# The chain runs through product_migration_pack.py, the same code and the same steps `apply` runs on :8000: one
# revision per step, 20260924_0016 by the reviewed Reading cutover, then the checks (head, ready, every backed-up row
# where its table now lives, the legacy Reading archive frozen). Its report becomes rehearsal.json, which `apply`
# requires.
$migrated = Invoke-Docker @('run', '--rm', '--network', $network, '-v', "${Repository}:/workspace:ro", '-v', "${Backup}:/backup:ro", '-w', '/workspace', '-e', 'PERSISTENCE_BACKEND=postgresql', '-e', "POSTGRES_RUNTIME_URL=$url", '-e', 'APP_ENV=development', $AppImage, 'python', 'scripts/product_migration_pack.py', 'rehearse', '--backup', '/backup', '--confirm-rehearsal', 'rehearsal')
foreach ($line in $migrated.out) { if ("$line" -notlike 'REPORT=*') { Write-Host "  $line" } }
$reportLine = ($migrated.out | Where-Object { "$_" -like 'REPORT=*' } | Select-Object -Last 1)
if (-not $reportLine) { Note 'migration chain to head' $false 'the pack printed no report'; Finish 1 }
$pack = ("$reportLine" -replace '^REPORT=', '') | ConvertFrom-Json
foreach ($name in 'dump_sha256', 'backup_revision', 'head', 'chain_digest', 'revision', 'ready', 'rows_kept', 'row_differences', 'new_tables', 'legacy_reading', 'legacy_frozen', 'steps', 'started_from') { $report[$name] = $pack.$name }
$report.format = 'orena-migration-rehearsal'; $report.version = 2
Note 'migration chain to head' ($pack.ready -eq $true) "from $revisionBefore to $($pack.revision) in $(@($pack.steps).Count) step(s) (head $($pack.head))"
Note 'no rows lost by the migration' ($pack.rows_kept -eq $true) $(if ($pack.rows_kept) { "new tables: $($pack.new_tables -join ', ')" } else { $pack.row_differences -join '; ' })
Note 'legacy Reading archive frozen' ($pack.legacy_frozen -eq $true) $(if ($pack.legacy_reading) { "sessions $($pack.legacy_reading.sessions), attempts $($pack.legacy_reading.attempts), triggers $($pack.legacy_reading.freeze_triggers)" } else { 'no legacy Reading tables' })
if (-not ($migrated.ok -and $pack.passed)) { Finish 1 }

$listed = Invoke-Docker @('exec', $pg, 'tar', 'tzf', '/backup/files.tar.gz')
Note 'files archive reads end to end' ($listed.ok -and $listed.out.Count -eq $manifest.archived_files) "$($listed.out.Count) entries (manifest $($manifest.archived_files))"
if (-not $listed.ok -or $listed.out.Count -ne $manifest.archived_files) { Finish 1 }
Finish 0
