<#
Registers the :8000 health check as a Windows scheduled task (every 5 minutes).

    powershell -ExecutionPolicy Bypass -File scripts\register_health_check_8000.ps1          # prints the command only
    powershell -ExecutionPolicy Bypass -File scripts\register_health_check_8000.ps1 -Apply   # registers it

Without -Apply nothing is changed: the script prints the exact Register-ScheduledTask command. Registering a task is
the human's step (D-127). The task runs as the current user, only while that user is logged on (a toast needs the
desktop), and runs `scripts\health_check_8000.ps1` from this checkout. Remove it with
`Unregister-ScheduledTask -TaskName OrenaHealthCheck8000 -Confirm:$false`.
#>
param(
    [switch]$Apply,
    [int]$EveryMinutes = 5,
    [string]$TaskName = 'OrenaHealthCheck8000',
    [string]$HealthScript = (Join-Path $PSScriptRoot 'health_check_8000.ps1'),
    [switch]$Toast,
    [int]$BuildNumber = [Environment]::OSVersion.Version.Build
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $HealthScript)) { Write-Host "  $HealthScript not found." -ForegroundColor Red; exit 1 }
$HealthScript = (Resolve-Path -LiteralPath $HealthScript).Path

# Quiet by default: Windows 11 (build 22000 and later) has conhost --headless, which starts the task with no console
# window at all. Decided by the OS build alone; no probe is run, so registering flashes nothing. Older builds keep the
# hidden-window action.
$headless = ($BuildNumber -ge 22000)
# No toast unless -Toast is given at registration.
$toastArg = if ($Toast) { '' } else { ' -NoToast' }
$psArgs = '-NoProfile -ExecutionPolicy Bypass -File "{0}"{1}' -f $HealthScript, $toastArg
if ($headless) { $execute = 'conhost.exe'; $arguments = '--headless powershell.exe ' + $psArgs }
else { $execute = 'powershell.exe'; $arguments = '-WindowStyle Hidden ' + $psArgs }
$interval = "(New-TimeSpan -Minutes $EveryMinutes)"

$action = New-ScheduledTaskAction -Execute $execute -Argument $arguments

Write-Host "The task would be registered with:`n"
Write-Host "`$action   = New-ScheduledTaskAction -Execute '$($action.Execute)' -Argument '$($action.Arguments)'"
Write-Host "`$trigger  = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval $interval"
Write-Host "`$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew"
Write-Host "Register-ScheduledTask -TaskName '$TaskName' -Action `$action -Trigger `$trigger -Settings `$settings -Description 'Orena :8000 health check' -Force"

if (-not $Apply) {
    Write-Host "`nNothing was registered. Re-run with -Apply to register it." -ForegroundColor Yellow
    exit 0
}

# Windows PowerShell 5.1 needs a finite duration on a repeating trigger to register on every build.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Orena :8000 health check' -Force | Out-Null
Write-Host "`nRegistered '$TaskName' every $EveryMinutes minutes." -ForegroundColor Green
