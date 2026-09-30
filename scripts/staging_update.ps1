<#
Update the :8011 staging to the latest codex/work (D-101 A). Run by the human:
migrations are the human's gate, so this script stops and asks before it
changes the database.

    powershell -ExecutionPolicy Bypass -File scripts\staging_update.ps1
    powershell -ExecutionPolicy Bypass -File scripts\staging_update.ps1 -PlanOnly

It fails closed, in this order:

  1. the working tree is not clean, the branch is not codex/work, or the pull
     from origin is not a fast-forward          -> stop, nothing changed
  2. the release export or the image build fails -> stop, nothing changed
  3. the migration state cannot be read           -> stop, nothing changed
  4. it prints the current revision and every pending one, and waits for the
     operator to type MIGRATE (anything else     -> stop, nothing changed)
  5. it backs up with staging_backup.ps1; a failed backup -> stop, nothing
     migrated
  6. it migrates with the repository's own commands:
       bootstrap_runtime_schema.py --upgrade --from X --to Y --confirm
       reading_canonical_cutover.py apply ...   (the gated 20260924_0016)
  7. it starts the web container on the new release, checks health, and prints
     the running SHA, the database head and the URL.

What runs where:

  release   a `git archive` of the exact commit under
            %LOCALAPPDATA%\orena-staging\releases\<sha>, mounted read-only at
            /app. Staging never runs this checkout's working tree, so an edit
            in progress never reaches it.
  image     orena-staging:<short sha>, built from that release (dependencies)
  env       %LOCALAPPDATA%\orena-staging\staging.env, outside the repository.
            On the first run it is derived from the existing sandbox web
            container; values are never printed.
  database  orena-foundation-postgres on the named volume
            orena-foundation-sandbox-data (staging's own, not production's
            or preview's). Never `down -v`; no volume is ever removed here.
  files     named volumes orena-staging-appdata (/app/data; the release's
            tracked data is copied in on every update, runtime files stay) and
            orena-staging-data (/data).

The previous web container is renamed, never removed, so it can be started
again by hand. If the new one does not become healthy the script says so and
names the backup taken before the migration.
#>
param(
    [switch]$PlanOnly
)

$ErrorActionPreference = 'Continue'

$Branch     = 'codex/work'
$Postgres   = 'orena-foundation-postgres'
$Web        = 'orena-foundation-web'
$Network    = 'orena-foundation-review'
$Database   = 'postgres'
$Port       = 8011
$Url        = "http://127.0.0.1:$Port"
$Gated      = '20260924_0016'
$StagingDir = Join-Path $env:LOCALAPPDATA 'orena-staging'
$EnvFile    = Join-Path $StagingDir 'staging.env'
$LogDir     = Join-Path $StagingDir 'logs'
$Repo       = Split-Path -Parent $PSScriptRoot

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "  $text" -ForegroundColor Green }
function Note($text) { Write-Host "  $text" -ForegroundColor Yellow }
function Die($text)  { Write-Host "`n  STOPPED: $text" -ForegroundColor Red; exit 1 }

New-Item -ItemType Directory -Force -Path $StagingDir, $LogDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
Set-Location $Repo

# ---------------------------------------------------------------- 1. source --
Step "1. Source: $Branch, clean, fast-forward"
$current = (& git rev-parse --abbrev-ref HEAD).Trim()
if ($current -ne $Branch) { Die "this checkout is on '$current', not $Branch." }
$dirty = & git status --porcelain
if ($dirty) { Die "the working tree is not clean:`n$($dirty -join "`n")" }
& git fetch origin $Branch 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Die "git fetch origin $Branch failed." }
& git merge --ff-only "origin/$Branch" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Die "origin/$Branch cannot be fast-forwarded into this checkout." }
$Sha = (& git rev-parse HEAD).Trim()
$Short = $Sha.Substring(0, 12)
Ok "$Branch at $Sha"

# --------------------------------------------------------- 2. release, image --
Step "2. Release and image"
$Release = Join-Path $StagingDir "releases\$Sha"
if (-not (Test-Path (Join-Path $Release 'app.py'))) {
    $zip = Join-Path $StagingDir "releases\$Sha.zip"
    New-Item -ItemType Directory -Force -Path (Split-Path $zip) | Out-Null
    & git archive --format=zip -o $zip $Sha
    if ($LASTEXITCODE -ne 0) { Die "git archive failed." }
    Expand-Archive -Path $zip -DestinationPath $Release -Force
    Remove-Item $zip
    if (-not (Test-Path (Join-Path $Release 'app.py'))) { Die "the release export is incomplete." }
}
Ok "release $Release"
$Image = "orena-staging:$Short"
$buildLog = Join-Path $LogDir "build-$stamp.log"
& docker build -t $Image --label "org.opencontainers.image.revision=$Sha" $Release *> $buildLog
if ($LASTEXITCODE -ne 0) { Die "docker build failed; see $buildLog" }
Ok "image $Image (log $buildLog)"

# ----------------------------------------------------------------- env file --
if (-not (Test-Path $EnvFile)) {
    $json = & docker inspect $Web --format '{{json .Config.Env}}' 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json) {
        Die "$EnvFile does not exist and there is no $Web container to derive it from. Create it from .env.example."
    }
    $image_own = @('PATH', 'LANG', 'GPG_KEY', 'PYTHON_VERSION', 'PYTHON_SHA256',
                   'PYTHONDONTWRITEBYTECODE', 'PYTHONUNBUFFERED', 'HOME', 'HOSTNAME')
    $lines = @(($json | ConvertFrom-Json) | Where-Object { $image_own -notcontains (($_ -split '=', 2)[0]) })
    [IO.File]::WriteAllLines($EnvFile, $lines, (New-Object Text.UTF8Encoding $false))
    Note "created $EnvFile from $Web with $($lines.Count) variables (values not shown)"
}
foreach ($name in @('PERSISTENCE_BACKEND', 'POSTGRES_RUNTIME_URL')) {
    if (-not (Select-String -Path $EnvFile -Pattern "^$name=." -Quiet)) { Die "$EnvFile has no $name." }
}

function Invoke-InRelease([string[]]$command) {
    $args_ = @('run', '--rm', '--network', $Network, '--env-file', $EnvFile,
               '-v', "${Release}:/app:ro", '-w', '/app', $Image) + $command
    return (& docker @args_ 2>&1 | Out-String)
}

# ------------------------------------------------------------ 3. migrations --
Step "3. Database and migration plan"
& docker start $Postgres | Out-Null
$ready = $false
foreach ($i in 1..60) {
    & docker exec $Postgres pg_isready -U postgres | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { Die "$Postgres did not accept connections within 60s." }

function Read-Plan {
    $text = Invoke-InRelease @('python', 'scripts/bootstrap_runtime_schema.py', '--plan')
    $lines = $text -split "`r?`n"
    $plan = @{ current = ''; head = ''; pending = @(); status = '' }
    foreach ($line in $lines) {
        if ($line -match '^current: (\S+)') { $plan.current = $Matches[1] }
        elseif ($line -match '^head: (\S+)') { $plan.head = $Matches[1] }
        elseif ($line -match '^pending: (\S+)( gated)?') { $plan.pending += , @($Matches[1], [bool]$Matches[2]) }
        elseif ($line -match '^plan: (.+)$') { $plan.status = $Matches[1] }
    }
    return $plan
}
$plan = Read-Plan
if (-not $plan.status -or $plan.status -in @('unavailable', 'empty') -or -not $plan.head) {
    Die "the migration state could not be read (plan: '$($plan.status)')."
}
Ok "current $($plan.current)"
Ok "head    $($plan.head)"
foreach ($p in $plan.pending) { Note ("pending {0}{1}" -f $p[0], $(if ($p[1]) { '  (gated: reading_canonical_cutover.py apply)' } else { '' })) }
foreach ($p in $plan.pending) {
    if ($p[1] -and $p[0] -ne $Gated) { Die "pending gated revision $($p[0]) has no step in this script." }
}
if ($PlanOnly) { Note "-PlanOnly: nothing was changed."; exit 0 }

$backup = ''
if ($plan.pending.Count -gt 0) {
    $answer = Read-Host "`n  Type MIGRATE to back up the database and apply $($plan.pending.Count) migration(s)"
    if ($answer -ne 'MIGRATE') { Die "not confirmed; nothing was changed." }

    Step "4. Backup"
    $out = & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'staging_backup.ps1')
    $out | ForEach-Object { Write-Host $_ }
    $backup = (($out | Where-Object { $_ -match '^BACKUP=' }) -replace '^BACKUP=', '') | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0 -or -not $backup) { Die "the backup failed; nothing was migrated." }

    Step "5. Migrate"
    $at = $plan.current
    $i = 0
    while ($i -lt $plan.pending.Count) {
        $rev = $plan.pending[$i][0]
        if ($plan.pending[$i][1]) {
            $target = Invoke-InRelease @('python', 'scripts/reading_canonical_cutover.py', 'target',
                                         '--confirm-sandbox', $Database, '--app-url', $Url)
            if ($target -notmatch 'cluster (\d+)') { Die "the cutover target could not be read:`n$target" }
            $cluster = $Matches[1]
            $out = Invoke-InRelease @('python', 'scripts/reading_canonical_cutover.py', 'apply',
                                      '--confirm-sandbox', $Database, '--expect-cluster', $cluster,
                                      '--from', $at, '--app-url', $Url)
            Write-Host $out
            if ($out -notmatch "applied: database \S+ is at $rev") { Die "$rev was not applied. Backup: $backup" }
            $at = $rev; $i++
        } else {
            $j = $i
            while ($j + 1 -lt $plan.pending.Count -and -not $plan.pending[$j + 1][1]) { $j++ }
            $to = $plan.pending[$j][0]
            $out = Invoke-InRelease @('python', 'scripts/bootstrap_runtime_schema.py', '--upgrade',
                                      '--from', $at, '--to', $to, '--confirm')
            Write-Host $out
            $check = Read-Plan
            if ($check.current -ne $to) { Die "the upgrade to $to did not land (database at $($check.current)). Backup: $backup" }
            $at = $to; $i = $j + 1
        }
        Ok "database at $at"
    }
}

# --------------------------------------------------------------- 6. web ------
Step "6. Web container on $Sha"
$existing = & docker ps -a --filter "name=^$Web$" --format '{{.Names}}'
if ($existing -eq $Web) {
    & docker stop $Web | Out-Null
    & docker rename $Web "$Web-before-$stamp" | Out-Null
    if ($LASTEXITCODE -ne 0) { Die "could not set the previous $Web aside." }
    Note "previous container kept as $Web-before-$stamp"
}
& docker run --rm -v 'orena-staging-appdata:/dst' -v "${Release}\data:/src:ro" $Image sh -c 'cp -a /src/. /dst/' | Out-Null
if ($LASTEXITCODE -ne 0) { Die "could not copy the release's data into orena-staging-appdata." }
$run = @('run', '-d', '--name', $Web, '--label', 'orena.staging=1', '--label', "orena.staging.sha=$Sha",
         '--network', $Network, '-p', "${Port}:8000", '--env-file', $EnvFile, '--restart', 'unless-stopped',
         '-v', "${Release}:/app:ro", '-v', 'orena-staging-appdata:/app/data', '-v', 'orena-staging-data:/data',
         $Image)
& docker @run | Out-Null
if ($LASTEXITCODE -ne 0) { Die "the web container did not start. Previous container: $Web-before-$stamp" }

Step "7. Health"
$healthy = $true
foreach ($route in @('/', '/next', '/api/me')) {
    $code = 'ERR'
    foreach ($i in 1..90) {
        try { $code = (Invoke-WebRequest -Uri "$Url$route" -UseBasicParsing -TimeoutSec 3).StatusCode } catch {
            if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
        }
        if ($code -eq 200) { break }
        Start-Sleep -Seconds 1
    }
    Write-Host ("  {0,-10} {1}" -f $route, $code)
    if ($code -ne 200) { $healthy = $false }
}
$head = (& docker exec $Postgres psql -U postgres -d $Database -qAt -c 'SELECT version_num FROM alembic_version;' | Out-String).Trim()
$runningSha = (& docker inspect $Web --format '{{index .Config.Labels "orena.staging.sha"}}' | Out-String).Trim()
Write-Host ""
Write-Host "  running sha  $runningSha"
Write-Host "  db head      $head"
if ($backup) { Write-Host "  backup       $backup" }
if (-not $healthy) {
    & docker logs --tail 40 $Web
    Die "staging is not healthy. The previous container is kept (docker ps -a); the backup above was taken before any migration."
}
Write-Host "`n  Open $Url/next" -ForegroundColor Green
exit 0
