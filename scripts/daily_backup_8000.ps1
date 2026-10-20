<#
Daily backup of the :8000 runtime (public staging, D-146): a PostgreSQL dump plus a copy of the data volume, and an
encrypted off-machine copy of both (PRE-504).

    powershell -ExecutionPolicy Bypass -File scripts\daily_backup_8000.ps1
    powershell -ExecutionPolicy Bypass -File scripts\daily_backup_8000.ps1 -VerifyOffsite
    powershell -ExecutionPolicy Bypass -File scripts\daily_backup_8000.ps1 -DryRun          # decides, touches nothing

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
     `orena-8000-data-<UTC stamp>.tar.gz` next to the dump. No container is stopped, paused, recreated or
     removed; no volume is written, removed or pruned. Stopping the app is not needed: the volume holds
     files the app writes whole (media, covers, indexes), the database is backed up by step 1, and tar
     exit 1 ("file changed as we read it") is logged as a warning and the archive is kept. Any other tar
     failure exits 1. A data-step failure NEVER deletes the verified dump.
  6. Retention keeps the newest -KeepCount (default 14) dumps and data archives named `orena-8000-*`
     (one run per day = 14 days); it never touches other files (the :8021 dumps have other names).
  7. Off-machine copy (unless -NoOffsite): every artefact this run produced is encrypted with
     `gpg --symmetric --cipher-algo AES256 --passphrase-file <-OffsiteKeyFile>` (the key file's PATH is
     passed to gpg; this script never reads, prints, logs or copies its contents), copied into -OffsiteDir
     as `<name>.gpg`, its SHA-256 checked after the copy and recorded in `SHA256SUMS.txt` there. The newest
     -OffsiteKeepCount (default 14) sets (one stamp = one set) are kept offsite; older `orena-8000-<stamp>`
     sets there are pruned. Local files are never removed by this step. -VerifyOffsite decrypts each copy
     into the backup folder, compares its SHA-256 with the original and deletes the decrypted file.

The dump and the tar are taken one after the other, so they are NOT point-in-time consistent with each other.

Resource floors. Free disk on the backup drive must be at least -MinFreeDiskGB (default 5), else exit 2 at
once. Free RAM must be at least -MinFreeRamGBDump (default 0.8 GB) for the dump (a ~3 MB pg_dump inside the
running Postgres) and at least -MinFreeRamGB (default 2 GB) for the volume tar (a new helper container). A
low-memory run once crashed the engine and restarted :8000, so Docker is not touched while RAM is short.
When RAM is short the script waits and re-checks every -RetryEveryMinutes (default 30) until -RetryUntil
(local HH:mm, default 06:00; '' = no retry). Started after the cut-off it tries once. If the dump RAM never
comes, nothing is backed up (exit 2); if only the tar RAM never comes, the verified dump is kept and copied
offsite, and the run still exits 2.

Exit codes (every exit writes exactly one `exit N: <reason>` line to the log; the health check reads it):
  0 done (dump, data archive and, unless -NoOffsite, the offsite copy);
  1 a step failed (a dump failure removes partial files; a data-volume failure keeps the verified dump);
  2 skipped for RAM or disk (whole run, or the data step only);
  3 prerequisite missing (docker, container not running, helper image, no RAM reading, bad parameter);
  4 the local backup is complete but the offsite copy failed (key file or gpg missing, encrypt, copy or
    verify failed).
Precedence when several apply: 1, then 4, then 2.

-DryRun: checks the floors and prerequisites, prints what it would do and exits with the code the run would
have reached on that evidence. It touches no Docker, writes no file, sleeps for no retry and writes nothing to
backup.log. -SimulateFreeRamGB (only with -DryRun) replaces the RAM reading, for tests.

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
    [double]$MinFreeRamGBDump = 0.8,
    [double]$MinFreeDiskGB = 5,
    [string]$RetryUntil = '06:00',
    [int]$RetryEveryMinutes = 30,
    [string]$HelperImage = 'postgres:17-alpine',
    [string]$OffsiteDir = (Join-Path $env:USERPROFILE 'OneDrive\Orena-Backups'),
    [string]$OffsiteKeyFile = (Join-Path $env:LOCALAPPDATA 'orena-product\offsite-backup.key'),
    [int]$OffsiteKeepCount = 14,
    [string]$Gpg = 'gpg',
    [switch]$NoOffsite,
    [switch]$VerifyOffsite,
    [switch]$DryRun,
    [double]$SimulateFreeRamGB = -1
)

# Native commands write progress to stderr; outcomes are checked explicitly.
$ErrorActionPreference = 'Continue'

if (-not $DryRun -and -not (Test-Path -LiteralPath $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir | Out-Null }
$LogFile = Join-Path $BackupDir 'backup.log'

function Log([string]$text) {
    $line = '{0} {1}' -f (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'), $text
    if ($DryRun) { Write-Host ('DRY-RUN ' + $line); return }
    Write-Host $line
    try { Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8 } catch { }
}

# The one exit path. The health check reads the last "exit N:" line of backup.log, so nothing else writes one.
function Finish([int]$code, [string]$text) {
    Log ("exit {0}: {1}" -f $code, $text)
    exit $code
}

if ($SimulateFreeRamGB -ge 0 -and -not $DryRun) { Finish 3 '-SimulateFreeRamGB is only allowed with -DryRun; nothing was backed up' }
if ($RetryEveryMinutes -lt 1) { Finish 3 '-RetryEveryMinutes must be at least 1; nothing was backed up' }

# --- retry window: wait for RAM until the cut-off (local time today) -----------------------------------------
$cutoff = $null
if ($RetryUntil) {
    try {
        $t = [datetime]::ParseExact($RetryUntil, 'HH:mm', [Globalization.CultureInfo]::InvariantCulture)
        $cutoff = (Get-Date).Date.Add($t.TimeOfDay)
    } catch { Finish 3 ("-RetryUntil '{0}' is not HH:mm; nothing was backed up" -f $RetryUntil) }
    if ((Get-Date) -ge $cutoff) { $cutoff = $null }  # started after the cut-off: one attempt, no retry
}

function Get-FreeRamGB {
    if ($SimulateFreeRamGB -ge 0) { return [double]$SimulateFreeRamGB }
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    if ($null -eq $os) { return $null }
    return [math]::Round($os.FreePhysicalMemory / 1MB, 2)
}

# True once free RAM reaches $needGB; false when the cut-off passes first (or there is no retry window).
function Wait-ForRam([double]$needGB, [string]$step) {
    while ($true) {
        $ram = Get-FreeRamGB
        if ($null -eq $ram) { Finish 3 'could not read free RAM; Docker was not touched' }
        $script:freeRamGB = $ram
        if ($ram -ge $needGB) { return $true }
        $next = (Get-Date).AddMinutes($RetryEveryMinutes)
        if ($null -eq $cutoff -or $next -gt $cutoff) {
            Log ("{0}: free RAM {1} GB is below {2} GB and no retry is left before the cut-off" -f $step, $ram, $needGB)
            return $false
        }
        if ($DryRun) {
            Log ("{0}: free RAM {1} GB is below {2} GB; a real run would re-check every {3} min until {4}" -f $step, $ram, $needGB, $RetryEveryMinutes, $cutoff.ToString('HH:mm'))
            return $false
        }
        Log ("waiting: {0} needs {1} GB, free RAM {2} GB; next check {3} (cut-off {4}); Docker was not touched" -f $step, $needGB, $ram, $next.ToString('HH:mm'), $cutoff.ToString('HH:mm'))
        Start-Sleep -Seconds ($RetryEveryMinutes * 60)
    }
}

# --- guard rails: disk, then RAM for the dump; Docker untouched when short -------------------------------------
$fullBackupDir = [System.IO.Path]::GetFullPath($BackupDir)
$root = [System.IO.Path]::GetPathRoot($fullBackupDir)
$drive = New-Object System.IO.DriveInfo($root)
$freeDiskGB = [math]::Round($drive.AvailableFreeSpace / 1GB, 1)
if ($freeDiskGB -lt $MinFreeDiskGB) {
    Finish 2 ("skipped: free disk {0} GB on {1} is below {2} GB; Docker was not touched" -f $freeDiskGB, $root, $MinFreeDiskGB)
}

# Offsite prerequisites are checked up front but never block the local backup: a missing key or gpg ends in exit 4.
$offsiteProblem = $null
# gpg is often not on the task's PATH: fall back to the usual installs (Gpg4win, then Git for Windows' gpg).
if (-not $NoOffsite -and -not (Get-Command $Gpg -ErrorAction SilentlyContinue) -and $Gpg -eq 'gpg') {
    $candidates = @()
    foreach ($base in @(${env:ProgramFiles(x86)}, $env:ProgramFiles)) { if ($base) { $candidates += (Join-Path $base 'GnuPG\bin\gpg.exe') } }
    if ($env:ProgramFiles) { $candidates += (Join-Path $env:ProgramFiles 'Git\usr\bin\gpg.exe') }
    $found = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if ($found) { $Gpg = $found }
}
if (-not $NoOffsite) {
    if (-not $OffsiteDir) { $offsiteProblem = 'no -OffsiteDir given' }
    elseif (-not $OffsiteKeyFile -or -not (Test-Path -LiteralPath $OffsiteKeyFile -PathType Leaf)) { $offsiteProblem = "the offsite key file is missing: $OffsiteKeyFile" }
    elseif (-not (Get-Command $Gpg -ErrorAction SilentlyContinue)) { $offsiteProblem = "gpg was not found ($Gpg)" }
    if ($offsiteProblem) { Log ("offsite: {0}; the local backup still runs, the run will exit 4" -f $offsiteProblem) }
}

$freeRamGB = $null
if (-not (Wait-ForRam $MinFreeRamGBDump 'dump')) {
    Finish 2 ("skipped: free RAM {0} GB stayed below {1} GB (dump floor) until the cut-off; nothing was backed up; Docker was not touched" -f $freeRamGB, $MinFreeRamGBDump)
}

if ($DryRun) {
    Log ("would dump {0}/{1} from {2} into {3} (ram {4} GB free, disk {5} GB free)" -f $DbUser, $DbName, $Postgres, $fullBackupDir, $freeRamGB, $freeDiskGB)
    $dataOk = Wait-ForRam $MinFreeRamGB 'data volume copy'
    if ($dataOk) { Log ("would tar {0} read-only with {1}" -f $DataVolume, $HelperImage) }
    if (-not $NoOffsite -and -not $offsiteProblem) {
        Log ("would encrypt (gpg AES256, key file path only) and copy to {0}, keep {1} sets{2}" -f $OffsiteDir, $OffsiteKeepCount, $(if ($VerifyOffsite) { ', verify by decrypting' } else { '' }))
    }
    if ($offsiteProblem) { Finish 4 ("local backup would run; offsite copy would fail: {0}" -f $offsiteProblem) }
    if (-not $dataOk) { Finish 2 ("dump would be kept; data volume copy would be skipped: free RAM {0} GB is below {1} GB" -f $freeRamGB, $MinFreeRamGB) }
    Finish 0 'backup would complete'
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
$dataSkipped = $false
if (-not (Wait-ForRam $MinFreeRamGB 'data volume copy')) {
    $dataSkipped = $true
    Log ("data volume copy skipped: free RAM {0} GB stayed below {1} GB; the verified dump {2} is kept" -f $freeRamGB, $MinFreeRamGB, $dumpName)
} else {
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

# --- 7. off-machine copy: encrypt, copy, checksum, prune offsite sets -------------------------------------
# Returns $null on success, else the reason. The key file is only ever passed to gpg by path.
function Get-Sha256([string]$path) { return (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant() }

function Send-Offsite([string[]]$files) {
    $staging = Join-Path $BackupDir 'offsite-staging'
    $sumsFile = Join-Path $OffsiteDir 'SHA256SUMS.txt'
    $sums = [ordered]@{}
    $problem = $null
    try {
        if (-not (Test-Path -LiteralPath $OffsiteDir)) { New-Item -ItemType Directory -Path $OffsiteDir -Force -ErrorAction Stop | Out-Null }
        if (-not (Test-Path -LiteralPath $staging)) { New-Item -ItemType Directory -Path $staging -ErrorAction Stop | Out-Null }
        if (Test-Path -LiteralPath $sumsFile) {
            foreach ($line in (Get-Content -LiteralPath $sumsFile -ErrorAction Stop)) {
                if ($line -match '^([0-9a-f]{64}) [ *](.+)$') { $sums[$Matches[2]] = $Matches[1] }
            }
        }
    } catch { return ("could not prepare {0}: {1}" -f $OffsiteDir, $_.Exception.Message) }

    foreach ($f in $files) {
        $name = (Split-Path -Leaf $f) + '.gpg'
        $enc = Join-Path $staging $name
        $dest = Join-Path $OffsiteDir $name
        $partial = $dest + '.partial'
        if (Test-Path -LiteralPath $enc) { Remove-Item -LiteralPath $enc -Force -ErrorAction SilentlyContinue }
        & $Gpg --batch --yes --quiet --pinentry-mode loopback --no-symkey-cache --symmetric --cipher-algo AES256 --passphrase-file $OffsiteKeyFile --output $enc $f
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $enc)) { $problem = ("encrypt failed for {0} (gpg exit {1})" -f (Split-Path -Leaf $f), $LASTEXITCODE); break }
        $hash = Get-Sha256 $enc
        try {
            Copy-Item -LiteralPath $enc -Destination $partial -Force -ErrorAction Stop
            Move-Item -LiteralPath $partial -Destination $dest -Force -ErrorAction Stop
        } catch {
            if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue }
            $problem = ("copy to {0} failed for {1}: {2}" -f $OffsiteDir, $name, $_.Exception.Message); break
        }
        Remove-Item -LiteralPath $enc -Force -ErrorAction SilentlyContinue
        if ((Get-Sha256 $dest) -ne $hash) { $problem = ("the offsite copy of {0} differs from the encrypted file" -f $name); break }
        $sums[$name] = $hash
        Log ("offsite ok: {0} ({1} MB, sha256 {2})" -f $name, [math]::Round((Get-Item -LiteralPath $dest).Length / 1MB, 2), $hash)

        if ($VerifyOffsite) {
            $plain = Join-Path $staging ((Split-Path -Leaf $f) + '.verify')
            try {
                & $Gpg --batch --yes --quiet --pinentry-mode loopback --no-symkey-cache --passphrase-file $OffsiteKeyFile --output $plain --decrypt $dest
                $gpgCode = $LASTEXITCODE
                if ($gpgCode -ne 0 -or -not (Test-Path -LiteralPath $plain)) { $problem = ("verify: decrypt of {0} failed (gpg exit {1})" -f $name, $gpgCode) }
                elseif ((Get-Sha256 $plain) -ne (Get-Sha256 $f)) { $problem = ("verify: {0} does not decrypt to the original" -f $name) }
                else { Log ("offsite verified: {0} decrypts to the original" -f $name) }
            } finally {
                if (Test-Path -LiteralPath $plain) { Remove-Item -LiteralPath $plain -Force -ErrorAction SilentlyContinue }
            }
            if ($problem) { break }
        }
    }

    # Prune offsite sets beyond the newest $OffsiteKeepCount, only names this script writes, and never after a
    # failure (today's set may be incomplete, so the older sets stay).
    if (-not $problem -and $OffsiteKeepCount -ge 1) {
        $pattern = '^orena-8000-(?:data-)?(\d{8}T\d{6}Z)\.(?:dump|tar\.gz)\.gpg$'
        $ours = @(Get-ChildItem -LiteralPath $OffsiteDir -Filter 'orena-8000-*.gpg' -File | Where-Object { $_.Name -match $pattern })
        $stamps = @($ours | ForEach-Object { [regex]::Match($_.Name, $pattern).Groups[1].Value } | Sort-Object -Unique -Descending)
        $keep = @($stamps | Select-Object -First $OffsiteKeepCount)
        foreach ($o in $ours) {
            if ($keep -notcontains [regex]::Match($o.Name, $pattern).Groups[1].Value) {
                Remove-Item -LiteralPath $o.FullName -Force -ErrorAction SilentlyContinue
                Log ("offsite retention: removed {0}" -f $o.Name)
            }
        }
    }

    # SHA256SUMS.txt lists exactly the .gpg files present offsite (sha256sum format: "<hash>  <name>").
    try {
        $lines = @(foreach ($k in ($sums.Keys | Sort-Object)) { if (Test-Path -LiteralPath (Join-Path $OffsiteDir $k)) { '{0}  {1}' -f $sums[$k], $k } })
        $tmpSums = $sumsFile + '.partial'
        Set-Content -LiteralPath $tmpSums -Value $lines -Encoding ASCII -ErrorAction Stop
        Move-Item -LiteralPath $tmpSums -Destination $sumsFile -Force -ErrorAction Stop
    } catch { if (-not $problem) { $problem = ("could not write {0}: {1}" -f $sumsFile, $_.Exception.Message) } }

    if ((Test-Path -LiteralPath $staging) -and -not (Get-ChildItem -LiteralPath $staging -Force)) { Remove-Item -LiteralPath $staging -Force -ErrorAction SilentlyContinue }
    return $problem
}

$artefacts = @($dumpFile)
if (-not $dataFailed -and -not $dataSkipped) { $artefacts += $dataFile }
$offsiteFailed = $false
if (-not $NoOffsite) {
    if ($offsiteProblem) { $offsiteFailed = $true }
    else {
        $offsiteProblem = Send-Offsite $artefacts
        if ($offsiteProblem) { $offsiteFailed = $true; Log ("offsite copy failed: {0}; the local backup is kept" -f $offsiteProblem) }
    }
}

if ($dataFailed) { Finish 1 ('dump kept, data volume copy failed: {0}' -f $dumpName) }
if ($offsiteFailed) { Finish 4 ('local backup kept ({0}), offsite copy failed: {1}' -f $dumpName, $offsiteProblem) }
if ($dataSkipped) { Finish 2 ('dump kept ({0}), data volume copy skipped: free RAM below {1} GB until the cut-off' -f $dumpName, $MinFreeRamGB) }
$offsiteNote = if ($NoOffsite) { 'no offsite copy (-NoOffsite)' } else { "offsite copy in $OffsiteDir" }
Finish 0 ("backup complete: {0}, {1}; {2}" -f $dumpName, $dataName, $offsiteNote)
