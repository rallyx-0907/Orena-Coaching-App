<#
Health check for the :8000 runtime (deploy audit B3, 2026-10-18). Read-only: it asks two readiness URLs, reads
container State fields, and looks at the backup folder and its log. It starts, stops and changes nothing, uses no
external account and reads no secret.

    powershell -ExecutionPolicy Bypass -File scripts\health_check_8000.ps1

Checks (each one a PASS or FAIL line):
  local-readiness   GET http://127.0.0.1:8000/api/readiness answers 200 with ready=true
  public-readiness  GET https://orena.chillpickle.org/api/readiness answers 200 with ready=true (the tunnel path)
  container:<name>  `docker inspect --format` State.Status is running, and RestartCount has not grown since the last run
                    (ai-writing-coach-writing-coach-1, ai-writing-coach-reading-worker-1)
  backup-age        the newest orena-8000-*.dump in %USERPROFILE%\.orena\backups is younger than -MaxBackupAgeHours (26)
  backup-log        the last "exit N:" line of backup.log has N = 0
  ai-spend          (notice only, never a failure) today's container log holds the daily AI spend warning or threshold
                    line; raises the alert once per UTC day and level. Since D-250 the system figure is a monitor: AI
                    keeps running for every learner, and each learner has a per-plan cap instead
  providers         (PR BZ) provider health from the recorded AI operations: `docker exec` runs
                    `python -m writing_coach.ai.health_signal` in the app container (one read-only SELECT on audit_logs;
                    no key, prompt or learner text is read or printed). FAIL when a provider alerts: 3 failures in a row
                    or in 10 minutes (policies ai.health_*), and AT ONCE for a spending cap or a rejected key (severity
                    high), which also raises the notification at once, without waiting for -AlertAfter. Unreadable
                    telemetry is a WARN line, not a failure.

What Hermes reads (one JSON shape, version 1; docs/operations/PROVIDER_HEALTH.md):
  health.log         `PASS providers ...` or `FAIL providers ...`, then `JSON providers {...}`: the whole report on one
                     line (status, severity, alerts, down providers with reason / since / on_backup, recent switches).
  health.state.json  `providers`: { status, severity, checked_at, line, alerts, down } from the last run.

Writes %USERPROFILE%\.orena\health\health.log (one line per check, UTC) and health.state.json (the consecutive
failure count and the restart counts). After -AlertAfter (2) consecutive failing runs it raises a Windows toast
(BurntToast, only when -NoToast is not given and the module is installed; no other popup path), and again every 12th consecutive failure (hourly at a 5 minute
schedule); a recovered run resets the count.

Quiet mode: -NoToast (the scheduled task passes it) raises no popup at all; the alert is the state file, which Hermes
reads (failures >= 2). health.state.json also carries `paused` and `last_status` (ok, unhealthy, paused).
Before the first backup exists, backup-age is skipped (status no_backup_yet, not a failure). Creating the file
%USERPROFILE%\.orena\health\maintenance.flag pauses the whole check (status paused, nothing counted, exit 0);
delete the file to resume.

Exit codes: 0 healthy; 1 a check failed (no alert yet); 2 a check failed and an alert was raised.
#>
param(
    [string]$LocalUrl = 'http://127.0.0.1:8000/api/readiness',
    [string]$PublicUrl = 'https://orena.chillpickle.org/api/readiness',
    [string[]]$Containers = @('ai-writing-coach-writing-coach-1', 'ai-writing-coach-reading-worker-1'),
    [string]$BackupDir = (Join-Path $env:USERPROFILE '.orena\backups'),
    [string]$HealthDir = (Join-Path $env:USERPROFILE '.orena\health'),
    [int]$MaxBackupAgeHours = 26,
    [int]$AlertAfter = 2,
    [int]$TimeoutSec = 8,
    [switch]$NoToast
)

$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $HealthDir | Out-Null
$LogFile = Join-Path $HealthDir 'health.log'
$StateFile = Join-Path $HealthDir 'health.state.json'
$failures = New-Object System.Collections.ArrayList

function Log([string]$text) {
    $line = '{0} {1}' -f (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'), $text
    Write-Host $line
    try { Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8 } catch { }
}

function Check([string]$name, [bool]$ok, [string]$detail) {
    if ($ok) { Log "PASS $name $detail" } else { Log "FAIL $name $detail"; [void]$failures.Add($name) }
}

# One notification path for every alert: BurntToast only, never when -NoToast.
function Raise-Alert([string]$message) {
    $raised = $false
    if ($NoToast) { return $false }
    try {
        if (Get-Module -ListAvailable -Name BurntToast) {
            Import-Module BurntToast -ErrorAction Stop
            New-BurntToastNotification -Text 'Orena :8000', $message
            $raised = $true
        }
    } catch { }
    return $raised
}

# Keep the log from growing without bound: past 1 MB the older half is dropped.
try {
    if ((Test-Path -LiteralPath $LogFile) -and (Get-Item -LiteralPath $LogFile).Length -gt 1MB) {
        $keep = Get-Content -LiteralPath $LogFile -Tail 2000
        Set-Content -LiteralPath $LogFile -Value $keep -Encoding UTF8
    }
} catch { }

# Maintenance pause: the flag file turns the whole run into a no-op that records status "paused".
$MaintenanceFlag = Join-Path $HealthDir 'maintenance.flag'
$state = @{ failures = 0; restarts = @{}; spendDay = ''; spendLevel = ''; paused = $false; last_status = ''; providersAlert = ''; providers = $null }
try {
    if (Test-Path -LiteralPath $StateFile) {
        $saved = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
        if ($saved.failures) { $state.failures = [int]$saved.failures }
        if ($saved.spendDay) { $state.spendDay = [string]$saved.spendDay; $state.spendLevel = [string]$saved.spendLevel }
        if ($saved.providersAlert) { $state.providersAlert = [string]$saved.providersAlert }
        if ($saved.restarts) { $saved.restarts.PSObject.Properties | ForEach-Object { $state.restarts[$_.Name] = [int]$_.Value } }
    }
} catch { }

if (Test-Path -LiteralPath $MaintenanceFlag) {
    $state.paused = $true
    $state.last_status = 'paused'
    Log 'PAUSED maintenance.flag present; no checks run, no failures counted'
    try { ($state | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath $StateFile -Encoding UTF8 } catch { }
    exit 0
}
$state.paused = $false

# 1-2. Readiness, locally and through the public tunnel. Only the status and the ready flag are read.
foreach ($probe in @(@('local-readiness', $LocalUrl), @('public-readiness', $PublicUrl))) {
    $name = $probe[0]
    try {
        $response = Invoke-WebRequest -Uri $probe[1] -UseBasicParsing -TimeoutSec $TimeoutSec
        $ready = ($response.Content | ConvertFrom-Json).ready
        Check $name (($response.StatusCode -eq 200) -and ($ready -eq $true)) ("status={0} ready={1}" -f $response.StatusCode, $ready)
    } catch {
        $status = ''
        if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
        Check $name $false ("unreachable or not ready status=$status")
    }
}

# 3. Containers: State fields only (never the environment or the config).
foreach ($container in $Containers) {
    $text = ''
    try { $text = "$(& docker.exe inspect $container --format '{{.State.Status}} {{.RestartCount}}' 2>$null)".Trim() } catch { }
    if ($text -notmatch '^(\w+) (\d+)$') { Check "container:$container" $false 'not found or docker unavailable'; continue }
    $status = $Matches[1]; $restarts = [int]$Matches[2]
    $before = $state.restarts[$container]
    $grew = ($null -ne $before) -and ($restarts -gt $before)
    $state.restarts[$container] = $restarts
    Check "container:$container" (($status -eq 'running') -and (-not $grew)) ("state=$status restarts=$restarts" + $(if ($grew) { " (was $before)" } else { '' }))
}

# 4-5. Backup freshness and the last backup result.
$newest = $null
if (Test-Path -LiteralPath $BackupDir) {
    $newest = Get-ChildItem -LiteralPath $BackupDir -Filter 'orena-8000-*.dump' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
}
$backupStatus = ''
if ($null -eq $newest) {
    $backupStatus = 'no_backup_yet'
    Log 'SKIP backup-age status=no_backup_yet (no orena-8000-*.dump yet; not a failure)'
} else {
    $age = [math]::Round(((Get-Date).ToUniversalTime() - $newest.LastWriteTimeUtc).TotalHours, 1)
    Check 'backup-age' ($age -le $MaxBackupAgeHours) ("newest={0} age_hours={1}" -f $newest.Name, $age)
}
$backupLog = Join-Path $BackupDir 'backup.log'
$last = $null
if (Test-Path -LiteralPath $backupLog) {
    $last = Get-Content -LiteralPath $backupLog -Tail 200 | Where-Object { $_ -match '^\S+ exit \d+: ' } | Select-Object -Last 1
}
if ($null -eq $last) {
    if ($backupStatus -eq 'no_backup_yet') { Log 'SKIP backup-log status=no_backup_yet' }
    else { Check 'backup-log' $false 'no exit line in backup.log' }
}
else { Check 'backup-log' ($last -match '^\S+ exit 0: ') ("last=" + ($last -replace '^\S+\s', '')) }

# 6. The daily AI spend ceiling (Intelligence #298/#312). The app logs one line a day when the guard crosses its warning
# ratio ("system daily spend near cap: ...") and one when the cap is reached ("... daily spend cap reached: ..."); the
# admin endpoint needs a sign-in, so the container log is read instead (read-only, today's UTC lines only). Not a health
# failure and not in the exit code: it raises the same notification once per UTC day and level, so the owner sees it
# even without opening the Admin overview.
$spendContainer = $Containers[0]
$spendLevel = ''
try {
    $sinceUtc = (Get-Date).ToUniversalTime().Date.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $logText = (& docker.exe logs $spendContainer --since $sinceUtc --tail 5000 2>&1 | Out-String)
    if ($logText -match 'daily spend cap reached:') { $spendLevel = 'reached' }
    elseif ($logText -match 'daily spend near cap:') { $spendLevel = 'near' }
} catch { }
$today = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd')
if ($spendLevel) {
    $already = ($state.spendDay -eq $today) -and (($state.spendLevel -eq $spendLevel) -or ($state.spendLevel -eq 'reached'))
    Log ("WARN ai-spend level={0} (container log, UTC day {1})" -f $spendLevel, $today)
    if (-not $already) {
        $spendMessage = if ($spendLevel -eq 'reached') { 'Orena :8000 AI daily spend reached its alert threshold (monitor only, D-250: AI keeps running; per-learner caps apply)' } else { 'Orena :8000 AI spend is at its warning level for today' }
        $spendRaised = Raise-Alert $spendMessage
        Log ("ALERT ai-spend {0}" -f $(if ($spendRaised) { 'raised' } else { 'not shown (-NoToast or no BurntToast); see the state file' }))
        $state.spendDay = $today
        $state.spendLevel = $spendLevel
    }
} else {
    Log "PASS ai-spend no ceiling warning in today's container log"
}

# 7. Provider health (PR BZ, owner rule 2026-10-20: Hermes is alerted before learners notice). Read-only: the module
# runs one SELECT on the AI operation rows and prints one JSON line; nothing is written in the container.
$providersReport = $null
try {
    $raw = (& docker.exe exec $spendContainer python -m writing_coach.ai.health_signal 2>$null | Select-Object -Last 1)
    if ($raw) { $providersReport = "$raw" | ConvertFrom-Json }
} catch { }
$providersHigh = $false
if ($null -eq $providersReport) {
    Log 'WARN providers status=unknown health signal unreadable (docker exec failed)'
} elseif (-not $providersReport.available) {
    Log ('WARN providers ' + $providersReport.line)
} else {
    Check 'providers' ($providersReport.status -ne 'alert') $providersReport.line
    $providersHigh = ($providersReport.severity -eq 'high')
}
if ($null -ne $providersReport) {
    Log ('JSON providers ' + ($providersReport | ConvertTo-Json -Depth 8 -Compress))
    $state.providers = @{ status = $providersReport.status; severity = $providersReport.severity; checked_at = $providersReport.checked_at; line = $providersReport.line; alerts = @($providersReport.alerts); down = @($providersReport.down) }
} else {
    $state.providers = @{ status = 'unknown'; severity = $null; checked_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'); line = 'health signal unreadable'; alerts = @(); down = @() }
}
# A spending cap or a rejected key does not wait for -AlertAfter: it is raised at once, and again when it changes.
$providersKey = ''
if ($providersHigh) { $providersKey = ((@($providersReport.alerts) | Where-Object { $_.severity -eq 'high' } | ForEach-Object { '{0}:{1}' -f $_.provider, $_.failure_class }) -join ',') }
# D-250: the system's daily spend at its alert threshold is a high-severity alert too (a monitor: nothing is refused).
if ($providersHigh -and $providersReport.spend -and ($providersReport.spend.severity -eq 'high')) { $providersKey = (@($providersKey, 'system:spend_threshold') | Where-Object { $_ }) -join ',' }
if ($providersHigh -and ($state.providersAlert -ne $providersKey)) {
    $providersRaised = Raise-Alert ('Orena :8000 AI provider down: ' + $providersKey)
    Log ("ALERT providers {0} {1}" -f $providersKey, $(if ($providersRaised) { 'raised' } else { 'not shown (-NoToast or no BurntToast); see the state file' }))
}
$state.providersAlert = $providersKey

# Alerting: after $AlertAfter consecutive failing runs, then hourly while it persists.
$code = 0
if ($failures.Count -eq 0) {
    $state.failures = 0
    $state.last_status = 'ok'
    Log 'HEALTHY all checks passed'
} else {
    $state.failures = [int]$state.failures + 1
    $code = 1
    $state.last_status = 'unhealthy'
    Log ("UNHEALTHY run {0} failing: {1}" -f $state.failures, ($failures -join ','))
    if (($state.failures -eq $AlertAfter) -or (($state.failures -gt $AlertAfter) -and ((($state.failures - $AlertAfter) % 12) -eq 0))) {
        $message = 'Orena :8000 health check failing: ' + ($failures -join ', ')
        $raised = Raise-Alert $message
        Log ("ALERT {0}" -f $(if ($raised) { 'raised' } else { 'not shown (-NoToast or no BurntToast); see the state file' }))
        $code = 2
    }
}
if ($providersHigh) { $code = 2 }

try { ($state | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath $StateFile -Encoding UTF8 } catch { }
exit $code
