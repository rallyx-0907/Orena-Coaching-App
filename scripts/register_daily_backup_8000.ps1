<#
Registers the daily :8000 backup as a Windows scheduled task (03:30 local, every day).

    powershell -ExecutionPolicy Bypass -File scripts\register_daily_backup_8000.ps1                          # prints the command only
    powershell -ExecutionPolicy Bypass -File scripts\register_daily_backup_8000.ps1 -VerifyOffsite -Apply    # registers it

Without -Apply nothing is changed: the script prints the exact Register-ScheduledTask command. Registering
a task is the human's step (D-127). The task runs as the current user, only while that user is logged on,
and runs `scripts\daily_backup_8000.ps1` from this checkout. Remove it with
`Unregister-ScheduledTask -TaskName OrenaDailyBackup8000 -Confirm:$false`.

The action is `powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File <script>`, on every Windows
build. The `conhost.exe --headless` wrapper (PR AX) is NOT used for this task: on 2026-10-20 the script exited 2 (skipped
for RAM) and the task still recorded LastTaskResult 0, because the result Task Scheduler records is conhost's, not the
script's. Task Scheduler must see the script's own exit code; a console may show briefly at 03:30.

The execution limit is 4 hours, longer than the backup script's retry window (03:30 to its -RetryUntil, 06:00 by
default). The options below are passed to the backup script only when given here; otherwise its own defaults apply.
#>
param(
    [switch]$Apply,
    [string]$Time = '03:30',
    [string]$TaskName = 'OrenaDailyBackup8000',
    [string]$BackupScript = (Join-Path $PSScriptRoot 'daily_backup_8000.ps1'),
    [string]$OffsiteDir,
    [string]$OffsiteKeyFile,
    [string]$RetryUntil,
    [double]$MinFreeRamGBDump = -1,
    [double]$MinFreeRamGB = -1,
    [switch]$VerifyOffsite,
    [switch]$NoOffsite
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $BackupScript)) { Write-Host "  $BackupScript not found." -ForegroundColor Red; exit 1 }
$BackupScript = (Resolve-Path -LiteralPath $BackupScript).Path

# A trailing backslash before the closing quote would escape it on the command line.
function Quote([string]$value) { return '"{0}"' -f $value.TrimEnd('\') }

$psArgs = '-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File {0}' -f (Quote $BackupScript)
if ($OffsiteDir) { $psArgs += ' -OffsiteDir ' + (Quote $OffsiteDir) }
if ($OffsiteKeyFile) { $psArgs += ' -OffsiteKeyFile ' + (Quote $OffsiteKeyFile) }
if ($RetryUntil) { $psArgs += ' -RetryUntil ' + $RetryUntil }
if ($MinFreeRamGBDump -ge 0) { $psArgs += ' -MinFreeRamGBDump ' + $MinFreeRamGBDump.ToString([Globalization.CultureInfo]::InvariantCulture) }
if ($MinFreeRamGB -ge 0) { $psArgs += ' -MinFreeRamGB ' + $MinFreeRamGB.ToString([Globalization.CultureInfo]::InvariantCulture) }
if ($VerifyOffsite) { $psArgs += ' -VerifyOffsite' }
if ($NoOffsite) { $psArgs += ' -NoOffsite' }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $psArgs

Write-Host "The task would be registered with:`n"
Write-Host "`$action   = New-ScheduledTaskAction -Execute '$($action.Execute)' -Argument '$($action.Arguments)'"
Write-Host "`$trigger  = New-ScheduledTaskTrigger -Daily -At '$Time'"
Write-Host "`$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 4) -MultipleInstances IgnoreNew"
Write-Host "Register-ScheduledTask -TaskName '$TaskName' -Action `$action -Trigger `$trigger -Settings `$settings -Description 'Orena :8000 daily backup' -Force"

if (-not $Apply) {
    Write-Host "`nNothing was registered. Re-run with -Apply to register it." -ForegroundColor Yellow
    exit 0
}

$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 4) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Orena :8000 daily backup' -Force | Out-Null
Write-Host "`nRegistered '$TaskName' for $Time daily." -ForegroundColor Green
