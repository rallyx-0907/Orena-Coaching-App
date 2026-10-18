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
    [string]$BackupScript = (Join-Path $PSScriptRoot 'daily_backup_8000.ps1')
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $BackupScript)) { Write-Host "  $BackupScript not found." -ForegroundColor Red; exit 1 }
$BackupScript = (Resolve-Path -LiteralPath $BackupScript).Path

$arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $BackupScript
$command = @"
`$action  = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '$arguments'
`$trigger = New-ScheduledTaskTrigger -Daily -At '$Time'
`$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName '$TaskName' -Action `$action -Trigger `$trigger -Settings `$settings -Description 'Orena :8000 daily pg_dump and data volume copy' -Force
"@

Write-Host "The task would be registered with:`n"
Write-Host $command

if (-not $Apply) {
    Write-Host "`nNothing was registered. Re-run with -Apply to register it." -ForegroundColor Yellow
    exit 0
}

Invoke-Expression $command | Out-Null
Write-Host "`nRegistered '$TaskName' for $Time daily." -ForegroundColor Green
