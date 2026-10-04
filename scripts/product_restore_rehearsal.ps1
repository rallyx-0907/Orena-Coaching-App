<#
Rehearse moving a runtime to a NEW environment: restore a backup into fresh containers and boot Orena on it
(completion plan item 6; docs/operations/VPS_RUNBOOK.md).

    powershell -ExecutionPolicy Bypass -File scripts\product_restore_rehearsal.ps1 -Backup <folder from product_backup.ps1>

Everything is throwaway and nothing touches the runtime the backup came from: an ephemeral PostgreSQL
(`--rm`, anonymous volume) and an ephemeral web container (an anonymous /data volume, removed with the container at the end) on their own
network, published on 127.0.0.1:<Port> only. No named volume is created or removed.

1. checks the backup against its manifest (sizes, SHA-256);
2. restores the dump into the new PostgreSQL and checks every table's row count and the schema revision;
3. starts the web container from this checkout (code mounted read-only, as compose does), unpacks the files
   archive into its /data first, and waits for /api/health;
4. checks the restored service answers: health, Admin > Overview, the Reading library and the media library,
   and that the files on /data match the archive;
5. checks the app did not migrate or change the restored schema on start (startup never migrates, D-002);
6. stops both containers (they remove themselves) and the network; writes restore.json beside the backup.
Exit code 0 only when every check passes; the last line is RESTORE=PASS|FAIL.
#>
param(
    [Parameter(Mandatory = $true)][string]$Backup,
    [string]$AppImage = 'ai-writing-coach:local',
    [string]$ToolImage = 'postgres:17-alpine',
    [int]$Port = 8031,
    [string]$Repository = ''
)
if (-not $Repository) { $Repository = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..')).Path }

$ErrorActionPreference = 'Continue'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ').ToLower()
$network = "orena-restore-$stamp"
$pg = "orena-restore-pg-$stamp"
$web = "orena-restore-web-$stamp"
$report = [ordered]@{ backup = $Backup; port = $Port; started_at = (Get-Date).ToUniversalTime().ToString('o'); checks = @() }

function Note([string]$name, [bool]$passed, [string]$detail) {
    $script:report.checks += [ordered]@{ check = $name; passed = $passed; detail = $detail }
    Write-Host ("[{0}] {1}: {2}" -f ($(if ($passed) { 'PASS' } else { 'FAIL' }), $name, $detail))
}
function Invoke-Docker([string[]]$arguments) {
    $output = & docker.exe @arguments 2>&1
    return @{ ok = ($LASTEXITCODE -eq 0); out = $output }
}
function Finish([int]$code) {
    if ($code -ne 0) { Write-Host ((Invoke-Docker @('logs', '--tail', '40', $web)).out | Out-String) }
    # The web container is not --rm, so its log survives a crash; removing it also removes its own anonymous /data.
    Invoke-Docker @('rm', '-f', '-v', $web) | Out-Null
    Invoke-Docker @('stop', $pg) | Out-Null
    Invoke-Docker @('network', 'rm', $network) | Out-Null
    $script:report.finished_at = (Get-Date).ToUniversalTime().ToString('o')
    $script:report.passed = ($code -eq 0)
    $script:report | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 (Join-Path $Backup 'restore.json')
    Write-Host ("RESTORE={0}" -f $(if ($code -eq 0) { 'PASS' } else { 'FAIL' }))
    exit $code
}
function Get-Json([string]$path) {
    try {
        $answer = Invoke-WebRequest -UseBasicParsing -TimeoutSec 20 -Uri "http://127.0.0.1:$Port$path"
        return @{ status = [int]$answer.StatusCode; body = ($answer.Content | ConvertFrom-Json) }
    } catch {
        $status = 0
        if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
        return @{ status = $status; body = $null }
    }
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
    foreach ($line in (Invoke-Docker @('exec', $pg, 'psql', '-U', 'orena', '-d', 'orena', '-At', '-c', $countSql)).out) {
        $parts = "$line".Split('=')
        if ($parts.Count -eq 2) { $result[$parts[0]] = [int64]$parts[1] }
    }
    return $result
}
function Revision() {
    return ((Invoke-Docker @('exec', $pg, 'psql', '-U', 'orena', '-d', 'orena', '-At', '-c', 'select version_num from alembic_version')).out | Out-String).Trim()
}

(Invoke-Docker @('network', 'create', $network)).ok | Out-Null
$started = Invoke-Docker @('run', '-d', '--rm', '--name', $pg, '--network', $network, '-e', 'POSTGRES_USER=orena', '-e', 'POSTGRES_PASSWORD=orena-restore', '-e', 'POSTGRES_DB=orena', '-v', "${Backup}:/backup:ro", $ToolImage)
if (-not $started.ok) { Note 'new postgres' $false ($started.out | Out-String); Finish 1 }
$ready = $false
for ($i = 0; $i -lt 60 -and -not $ready; $i++) { Start-Sleep -Seconds 1; $ready = (Invoke-Docker @('exec', $pg, 'pg_isready', '-U', 'orena', '-d', 'orena')).ok }
Note 'new postgres' $ready $pg
if (-not $ready) { Finish 1 }

Invoke-Docker @('exec', $pg, 'pg_restore', '-U', 'orena', '-d', 'orena', '--no-owner', '--no-acl', '/backup/database.dump') | Out-Null
$restored = Counts
$revision = Revision
$mismatch = @()
foreach ($table in $manifest.table_counts.PSObject.Properties) {
    if ($restored[$table.Name] -ne [int64]$table.Value) { $mismatch += "$($table.Name): backup $($table.Value), restored $($restored[$table.Name])" }
}
Note 'database restored exactly' (($mismatch.Count -eq 0) -and ($revision -eq $manifest.schema_revision)) $(if ($mismatch.Count) { $mismatch -join '; ' } else { "revision $revision, $($restored.Count) tables" })
if ($mismatch.Count -or $revision -ne $manifest.schema_revision) { Finish 1 }

$mounts = @()
foreach ($item in 'app.py', 'auth_support.py', 'grammar_course.py', 'writing_coach', 'migrations', 'alembic.ini', 'VERSION', 'static', 'templates') {
    $mounts += @('-v', "$(Join-Path $Repository $item):/app/${item}:ro")
}
$environment = @(
    '-e', 'APP_ENV=development', '-e', "PUBLIC_BASE_URL=http://localhost:$Port",
    '-e', 'PERSISTENCE_BACKEND=postgresql', '-e', "POSTGRES_RUNTIME_URL=postgresql+psycopg://orena:orena-restore@${pg}:5432/orena",
    '-e', 'GOOGLE_CLIENT_ID=', '-e', 'GOOGLE_CLIENT_SECRET=', '-e', 'GOOGLE_REDIRECT_URI=',
    '-e', 'WRITING_DB=/data/writing.db', '-e', 'AUTH_DB=/data/auth.db', '-e', 'USER_DATA_ROOT=/data/users',
    '-e', 'PLATFORM_DB=/data/platform.db', '-e', 'PRODUCT_DB=/data/product.db',
    '-e', 'MEDIA_LIBRARY_ROOT=/data/media_library', '-e', 'MEDIA_LIBRARY_ASSET_ROOT=/data/media_library_assets',
    '-e', 'READING_LIBRARY_ASSET_ROOT=/data/reading_library_assets', '-e', 'WORD_AUDIO_ASSET_ROOT=/data/word_audio',
    '-e', 'WORD_DEEP_ASSET_ROOT=/data/word_deep'
)
$boot = 'tar xzf /backup/files.tar.gz -C /data && exec python -m uvicorn app:app --host 0.0.0.0 --port 8000'
$arguments = @('run', '-d', '--name', $web, '--network', $network, '-p', "127.0.0.1:${Port}:8000", '-v', '/data', '-v', "${Backup}:/backup:ro") + $mounts + $environment + @($AppImage, 'sh', '-c', $boot)
$webStarted = Invoke-Docker $arguments
if (-not $webStarted.ok) { Note 'new web container' $false ($webStarted.out | Out-String); Finish 1 }
$health = @{ status = 0 }
for ($i = 0; $i -lt 90 -and $health.status -ne 200; $i++) { Start-Sleep -Seconds 1; $health = Get-Json '/api/health' }
Note 'web answers /api/health' ($health.status -eq 200) "http://127.0.0.1:$Port"
if ($health.status -ne 200) { Finish 1 }

$overview = Get-Json '/api/admin/console/overview'
Note 'Admin > Overview reads the restored data' ($overview.status -eq 200) "status $($overview.status)"
$reading = Get-Json '/api/reading/articles?language=en'
$readingCount = $(if ($reading.body -and $reading.body.items) { @($reading.body.items).Count } else { 0 })
$expectedTexts = $(if ($manifest.table_counts.PSObject.Properties['reading_articles']) { [int64]$manifest.table_counts.reading_articles } else { 0 })
Note 'Reading library lists restored texts' ($reading.status -eq 200 -and ($expectedTexts -eq 0 -or $readingCount -gt 0)) "status $($reading.status), $readingCount listed ($expectedTexts texts in the backup)"
$media = Get-Json '/api/media/admin/library'
$mediaCount = $(if ($media.body -and $media.body.items) { @($media.body.items).Count } else { 0 })
Note 'media library lists restored items' ($media.status -eq 200) "status $($media.status), $mediaCount items"
$onDisk = (Invoke-Docker @('exec', $web, 'sh', '-c', 'cd /data && find . | wc -l')).out | Out-String
Note 'files on /data match the archive' ([int]$onDisk.Trim() -eq [int]$manifest.archived_files) "$($onDisk.Trim()) entries (archive $($manifest.archived_files))"
Note 'startup left the schema as restored' ((Revision) -eq $revision) "revision $(Revision)"

$failed = @($report.checks | Where-Object { -not $_.passed }).Count
Finish $(if ($failed) { 1 } else { 0 })
