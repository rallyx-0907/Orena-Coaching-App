<#
Daily backup of the :8000 runtime (public staging, D-146): a PostgreSQL dump plus a copy of the data volume.

    powershell -ExecutionPolicy Bypass -File scripts\daily_backup_8000.ps1
    powershell -ExecutionPolicy Bypass -File scripts\daily_backup_8000.ps1 -KeepCount 21 -MinFreeRamGB 2

Written for the human operator (D-127): only the human runs it, or registers it with
`scripts\register_daily_backup_8000.ps1`. It is READ-ONLY toward :8000:

  1. `pg_dump --format=custom` runs inside `ai-writing-coach-postgres-1` (database and role `becoming`,
     the names `product_backup.ps1` and `staging_8000_deploy.ps1` use; local socket, no password is read
     or printed) into a temp file in the container.
  2. `docker cp` brings it to `%USERPROFILE%\.orena\backups\orena-8000-<UTC stamp>.dump`.
  3. `pg_restore --list` must be able to read it. A dump that cannot be listed is not a backup: the file
     is deleted and the script exits 1.
  4. The temp file in the container is removed.
  5. A short-lived helper container (the already-local, pinned `postgres:17-alpine` the stack runs;
     nothing is pulled, exit 3 if it is missing) mounts `ai-writing-coach-data` READ-ONLY and writes
     `orena-8000-data-<UTC stamp>.tar.gz` next to the dump. No container is stopped, recreated or
     removed; no volume is written, removed or pruned. The volume is live: tar exit 1 ("file changed as
     we read it") is logged as a warning and the archive is kept; any other tar failure exits 1. A
     data-step failure NEVER deletes the verified dump.
  6. Retention keeps the newest -KeepCount (default 14) dumps and data archives named `orena-8000-*`
     (one run per day = 14 days); it never touches other files (the :8021 dumps have other names).

The dump and the tar are taken one after the other, so they are NOT point-in-time consistent with each
other. Backups are unencrypted and stay on this machine; an off-machine copy is the owner's decision.

Before anything it checks free RAM (default at least 2 GB) and free disk on the backup drive (default at
least 5 GB). If either is short it logs one line and exits 2 WITHOUT touching Docker: a low-memory run once
crashed the engine and restarted :8000.

Exit codes: 0 done; 1 a step failed (a dump failure removes partial files; a data-volume failure keeps the verified dump); 2 skipped for RAM or disk;
3 prerequisite missing (docker, container not running, no RAM reading).

Log: `%USERPROFILE%\.orena\backups\backup.log`. The backup folder holds learner data: keep it
access-controlled and outside the repository.
#>
param(
    [string]$BackupDir = (Join-Path $env:USERPROFILE '.orena\backups'),
    [string]$Postgres = 'ai-writing-coach-postgres-1',
    [string]$DbUser = 'becoming',
    [string]$DbName = 'becoming',
    [string]$DataVolume = 'ai-writing-coach-data',
    [int]$KeepCount = 14,
    [double]$MinFreeRamGB = 2,
    [double]$MinFreeDiskGB = 5,
    [string]$HelperImage = 'postgres:17-alpine'
)

# Native commands write progress to stderr; outcomes are checked explicitly.
$ErrorActionPreference = 'Continue'

if (-not (Test-Path -LiteralPath $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir | Out-Null }
$LogFile = Join-Path $BackupDir 'backup.log'

function Log([string]$text) {
    $line = '{0} {1}' -f (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'), $text
    Write-Host $line
    try { Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8 } catch { }
}

function Finish([int]$code, [string]$text) {
    Log ("exit {0}: {1}" -f $code, $text)
    exit $code
}

# --- guard rails: resources first, Docker untouched when short ---------------------------------------
$os = Get-CimInstance Win32_OperatingSystem
if ($null -eq $os) { Finish 3 'could not read free RAM; nothing was backed up' }
$freeRamGB = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
if ($freeRamGB -lt $MinFreeRamGB) {
    Finish 2 ("skipped: free RAM {0} GB is below {1} GB; Docker was not touched" -f $freeRamGB, $MinFreeRamGB)
}
$root = [System.IO.Path]::GetPathRoot((Resolve-Path -LiteralPath $BackupDir).Path)
$drive = New-Object System.IO.DriveInfo($root)
$freeDiskGB = [math]::Round($drive.AvailableFreeSpace / 1GB, 1)
if ($freeDiskGB -lt $MinFreeDiskGB) {
    Finish 2 ("skipped: free disk {0} GB on {1} is below {2} GB; Docker was not touched" -f $freeDiskGB, $root, $MinFreeDiskGB)
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Finish 3 'docker is not on PATH' }
$running = & docker inspect $Postgres --format '{{.State.Running}}' 2>$null
if ($running -ne 'true') { Finish 3 "$Postgres is not running; nothing was backed up" }
& docker image inspect $HelperImage 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Finish 3 "helper image $HelperImage is not present locally; nothing is pulled and nothing was backed up" }

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$dumpName = "orena-8000-$stamp.dump"
$dumpFile = Join-Path $BackupDir $dumpName
$dataName = "orena-8000-data-$stamp.tar.gz"
$dataFile = Join-Path $BackupDir $dataName
$tmpInContainer = "/tmp/$dumpName"
Log ("start: ram {0} GB free, disk {1} GB free, stamp {2}" -f $freeRamGB, $freeDiskGB, $stamp)

function Cleanup-Partial {
    & docker exec $Postgres rm -f $tmpInContainer 2>$null | Out-Null
    foreach ($f in @($dumpFile, $dataFile)) {
        if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue }
    }
}

# --- 1-2. dump and copy out -----------------------------------------------------------------------------
& docker exec $Postgres pg_dump -U $DbUser -d $DbName --format=custom --file $tmpInContainer
if ($LASTEXITCODE -ne 0) { Cleanup-Partial; Finish 1 'pg_dump failed' }
& docker cp "${Postgres}:$tmpInContainer" $dumpFile
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $dumpFile)) { Cleanup-Partial; Finish 1 'docker cp of the dump failed' }

# --- 3. verify: a dump that cannot be listed is not a backup ---------------------------------------------
$entries = & docker exec $Postgres pg_restore --list $tmpInContainer
if ($LASTEXITCODE -ne 0 -or -not $entries) { Cleanup-Partial; Finish 1 'pg_restore --list could not read the dump; the dump was deleted' }
$dumpBytes = (Get-Item -LiteralPath $dumpFile).Length
if ($dumpBytes -le 0) { Cleanup-Partial; Finish 1 'the dump is empty' }
# The host copy must equal the container's file byte for byte in size.
$inContainer = (& docker exec $Postgres sh -c "wc -c < $tmpInContainer")
if ($LASTEXITCODE -ne 0 -or ([string]$inContainer).Trim() -ne [string]$dumpBytes) { Cleanup-Partial; Finish 1 'the host copy of the dump differs in size from the container file; the dump was deleted' }
Log ("dump ok: {0} ({1} MB, {2} entries listed)" -f $dumpName, [math]::Round($dumpBytes / 1MB, 2), @($entries).Count)

# --- 4. remove the temp file in the container ------------------------------------------------------------
& docker exec $Postgres rm -f $tmpInContainer | Out-Null

# --- 5. data volume copy, mounted read-only. Its own step: a failure here never deletes the dump -----
$dataFailed = $false
& docker run --rm -v "${DataVolume}:/data:ro" -v "${BackupDir}:/out" $HelperImage tar czf "/out/$dataName" -C /data .
$tarCode = $LASTEXITCODE
if ($tarCode -eq 1 -and (Test-Path -LiteralPath $dataFile)) {
    Log 'warning: tar exit 1, files changed while the live volume was read; the archive was written and is kept'
} elseif ($tarCode -ne 0 -or -not (Test-Path -LiteralPath $dataFile)) {
    $dataFailed = $true
    if (Test-Path -LiteralPath $dataFile) { Remove-Item -LiteralPath $dataFile -Force -ErrorAction SilentlyContinue }
    Log ("data volume copy failed (tar exit {0}); the verified dump {1} is kept" -f $tarCode, $dumpName)
}
if (-not $dataFailed) {
    $dataBytes = (Get-Item -LiteralPath $dataFile).Length
    Log ("data volume ok: {0} ({1} MB)" -f $dataName, [math]::Round($dataBytes / 1MB, 2))
}

# --- 6. retention: newest $KeepCount of each kind, only files this script names ---------------------------
if ($KeepCount -ge 1) {
    foreach ($pattern in @('orena-8000-2*.dump', 'orena-8000-data-2*.tar.gz')) {
        $old = Get-ChildItem -LiteralPath $BackupDir -Filter $pattern -File | Sort-Object Name -Descending | Select-Object -Skip $KeepCount
        foreach ($f in $old) {
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
            Log ("retention: removed {0}" -f $f.Name)
        }
    }
}

if ($dataFailed) { Finish 1 ('dump kept, data volume copy failed: {0}' -f $dumpName) }
Finish 0 ("backup complete: {0}, {1}" -f $dumpName, $dataName)
