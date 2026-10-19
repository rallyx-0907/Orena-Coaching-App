<#
Registers the daily :8000 backup as a Windows scheduled task (03:30 local, every day).

    powershell -ExecutionPolicy Bypass -File scripts\register_daily_backup_8000.ps1          # prints the command only
    powershell -ExecutionPolicy Bypass -File scripts\register_daily_backup_8000.ps1 -Apply   # registers it

Without -Apply nothing is changed: the script prints the exact Register-ScheduledTask command. Registering
a task is the human's step (D-127). The task runs as the current user, only while that user is logged on,
and runs `scripts\daily_backup_8000.ps1` from this checkout. Remove it with
`Unregister-ScheduledTask -TaskName OrenaDailyBackup8000 -Confirm:$false`.
#>
param(
    [switch]$Apply,
    [string]$Time = '03:30',
    [string]$TaskName = 'OrenaDailyBackup8000',
    [string]$BackupScript = (Join-Path $PSScriptRoot 'daily_backup_8000.ps1'),
    [int]$BuildNumber = [Environment]::OSVersion.Version.Build
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $BackupScript)) { Write-Host "  $BackupScript not found." -ForegroundColor Red; exit 1 }
$BackupScript = (Resolve-Path -LiteralPath $BackupScript).Path

# Quiet by default: Windows 11 (build 22000 and later) has conhost --headless, which starts the task with no console
# window at all. Decided by the OS build alone; no probe is run, so registering flashes nothing. Older builds keep the
# hidden-window action.
$headless = ($BuildNumber -ge 22000)
$psArgs = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $BackupScript
if ($headless) { $execute = 'conhost.exe'; $arguments = '--headless powershell.exe ' + $psArgs }
else { $execute = 'powershell.exe'; $arguments = '-WindowStyle Hidden ' + $psArgs }

$action = New-ScheduledTaskAction -Execute $execute -Argument $arguments

Write-Host "The task would be registered with:`n"
Write-Host "`$action   = New-ScheduledTaskAction -Execute '$($action.Execute)' -Argument '$($action.Arguments)'"
Write-Host "`$trigger  = New-ScheduledTaskTrigger -Daily -At '$Time'"
Write-Host "`$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew"
Write-Host "Register-ScheduledTask -TaskName '$TaskName' -Action `$action -Trigger `$trigger -Settings `$settings -Description 'Orena :8000 daily backup' -Force"

if (-not $Apply) {
    Write-Host "`nNothing was registered. Re-run with -Apply to register it." -ForegroundColor Yellow
    exit 0
}

$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Orena :8000 daily backup' -Force | Out-Null
Write-Host "`nRegistered '$TaskName' for $Time daily." -ForegroundColor Green
