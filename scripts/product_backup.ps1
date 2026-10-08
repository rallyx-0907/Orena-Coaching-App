<#
Back up a runtime - its PostgreSQL database AND its data directory - in one command (D-127, completion plan item 1).

    powershell -ExecutionPolicy Bypass -File scripts\product_backup.ps1 `
        -Postgres orena-next-verify-pg -DbUser postgres -DbName postgres -DataVolume orena-next-verify-media

For the product on :8000 the human runs it with its own names (only the human operates :8000, D-127):

    ... -Postgres ai-writing-coach-postgres-1 -DbUser becoming -DbName becoming -DataVolume ai-writing-coach-data

It only reads. It never stops, recreates or removes a container and never writes to a volume:
- the database: a custom-format `pg_dump` taken inside the PostgreSQL container (the application image ships
  no PostgreSQL client; the postgres image does), copied out, then listed with `pg_restore --list` - a dump
  that cannot be listed is not a backup and the script fails;
- the files: the data volume mounted READ-ONLY into a throwaway container and archived with tar;
- the facts a restore is checked against: the schema revision and an exact row count for every table.

Output folder: <OutDir>\<UTC stamp>-<Postgres>\ with database.dump, files.tar.gz and manifest.json (sizes,
SHA-256, revision, counts). The last line is BACKUP=<folder> for product_migration_rehearsal.ps1. Nothing in
the output is a secret; keep the folder access-controlled anyway: it holds learners' data.
#>
param(
    [Parameter(Mandatory = $true)][string]$Postgres,
    [Parameter(Mandatory = $true)][string]$DataVolume,
    [string]$DbUser = 'becoming',
    [string]$DbName = 'becoming',
    [string]$OutDir = (Join-Path $env:LOCALAPPDATA 'orena-product\backups'),
    [string]$ToolImage = 'postgres:17-alpine'
)

$ErrorActionPreference = 'Continue'
function Fail([string]$message) { Write-Host "FAILED: $message"; exit 1 }
function Invoke-Docker([string[]]$arguments) {
    $output = & docker.exe @arguments 2>&1
    if ($LASTEXITCODE -ne 0) { Fail ("docker " + ($arguments -join ' ') + "`n" + ($output | Out-String)) }
    return $output
}

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$folder = Join-Path $OutDir "$stamp-$Postgres"
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$inside = "/tmp/orena-backup-$stamp.dump"

Write-Host "Reading database $DbName in container $Postgres and volume $DataVolume (read-only)."
$revision = (Invoke-Docker @('exec', $Postgres, 'psql', '-U', $DbUser, '-d', $DbName, '-At', '-c', 'select version_num from alembic_version') | Out-String).Trim()
# The cluster's system identifier pins the production migration pack to this exact cluster (product_migration_pack.py).
$cluster = (& docker.exe exec $Postgres psql -U $DbUser -d $DbName -At -c 'select system_identifier from pg_control_system()' 2>$null | Out-String).Trim()
$countSql = "select table_name || '=' || (xpath('/row/c/text()', query_to_xml('select count(*) as c from public.' || quote_ident(table_name), false, true, '')))[1]::text from information_schema.tables where table_schema = 'public' and table_type = 'BASE TABLE' order by table_name"
$counts = [ordered]@{}
foreach ($line in (Invoke-Docker @('exec', $Postgres, 'psql', '-U', $DbUser, '-d', $DbName, '-At', '-c', $countSql))) {
    $parts = "$line".Split('=')
    if ($parts.Count -eq 2) { $counts[$parts[0]] = [int64]$parts[1] }
}
# Each table's columns and a fingerprint of its contents (md5 over the sorted md5 of each row, over those columns),
# under pinned session settings. product_migration_pack.py computes the same expression before it migrates: a row
# changed, deleted or inserted since this backup - even with the count unchanged - is refused. The rehearsal checks
# the restored copy against these too, which also proves the dump was taken at the same moment.
$columnSql = "select c.table_name || '=' || string_agg(c.column_name, ',' order by c.ordinal_position) from information_schema.columns c join information_schema.tables b on b.table_schema = c.table_schema and b.table_name = c.table_name where c.table_schema = 'public' and b.table_type = 'BASE TABLE' and c.table_name <> 'alembic_version' group by c.table_name order by c.table_name"
$columns = [ordered]@{}
foreach ($line in (Invoke-Docker @('exec', $Postgres, 'psql', '-U', $DbUser, '-d', $DbName, '-At', '-c', $columnSql))) {
    $parts = "$line".Split('=')
    if ($parts.Count -eq 2) { $columns[$parts[0]] = @($parts[1].Split(',')) }
}
$fingerprintSql = "set TimeZone = 'UTC'; set DateStyle = 'ISO, MDY'; set IntervalStyle = 'postgres'; set extra_float_digits = 1; set bytea_output = 'hex'; select x.table_name || '=' || (xpath('/row/c/text()', query_to_xml(format('select md5(coalesce(string_agg(h, %L order by h), %L)) as c from (select md5(row(%s)::text) as h from public.%I t) s', '', '', x.cols, x.table_name), false, true, '')))[1]::text from (select c.table_name, string_agg('t.' || quote_ident(c.column_name), ', ' order by c.ordinal_position) as cols from information_schema.columns c join information_schema.tables b on b.table_schema = c.table_schema and b.table_name = c.table_name where c.table_schema = 'public' and b.table_type = 'BASE TABLE' and c.table_name <> 'alembic_version' group by c.table_name) x order by x.table_name"
$fingerprints = [ordered]@{}
foreach ($line in (Invoke-Docker @('exec', $Postgres, 'psql', '-U', $DbUser, '-d', $DbName, '-At', '-c', $fingerprintSql))) {
    $parts = "$line".Split('=')
    if ($parts.Count -eq 2 -and $parts[1] -match '^[0-9a-f]{32}$') { $fingerprints[$parts[0]] = $parts[1] }
}
if ($fingerprints.Count -ne $columns.Count) { Fail "content fingerprints for $($fingerprints.Count) of $($columns.Count) tables" }

Invoke-Docker @('exec', $Postgres, 'pg_dump', '-U', $DbUser, '-d', $DbName, '-Fc', '-f', $inside) | Out-Null
Invoke-Docker @('cp', "${Postgres}:$inside", (Join-Path $folder 'database.dump')) | Out-Null
Invoke-Docker @('exec', $Postgres, 'rm', '-f', $inside) | Out-Null
$listing = Invoke-Docker @('run', '--rm', '-v', "${folder}:/backup:ro", $ToolImage, 'pg_restore', '--list', '/backup/database.dump')
$entries = ($listing | Where-Object { "$_" -match '^\d+;' }).Count
if ($entries -lt 1) { Fail 'the dump lists no entries' }

Invoke-Docker @('run', '--rm', '-v', "${DataVolume}:/data:ro", '-v', "${folder}:/backup", $ToolImage, 'tar', 'czf', '/backup/files.tar.gz', '-C', '/data', '.') | Out-Null
$fileCount = (Invoke-Docker @('run', '--rm', '-v', "${folder}:/backup:ro", $ToolImage, 'tar', 'tzf', '/backup/files.tar.gz')).Count

$manifest = [ordered]@{
    format = 'orena-runtime-backup'; version = 3; created_at = (Get-Date).ToUniversalTime().ToString('o')
    postgres_container = $Postgres; database = $DbName; cluster = $cluster; data_volume = $DataVolume
    schema_revision = $revision; table_counts = $counts; table_columns = $columns; table_fingerprints = $fingerprints
    dump_entries = $entries; archived_files = $fileCount
    files = @(
        foreach ($name in 'database.dump', 'files.tar.gz') {
            $path = Join-Path $folder $name
            [ordered]@{ name = $name; bytes = (Get-Item $path).Length; sha256 = (Get-FileHash -Algorithm SHA256 $path).Hash.ToLower() }
        }
    )
}
$manifest | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 (Join-Path $folder 'manifest.json')

Write-Host "Schema revision: $revision; cluster: $(if ($cluster) { $cluster } else { '(not readable)' }); tables: $($counts.Count); dump entries: $entries; archived files: $fileCount"
foreach ($file in $manifest.files) { Write-Host ("{0}: {1:N0} bytes, sha256 {2}" -f $file.name, $file.bytes, $file.sha256) }
Write-Host "BACKUP=$folder"
