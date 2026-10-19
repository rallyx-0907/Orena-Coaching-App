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
    [switch]$Toast
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $HealthScript)) { Write-Host "  $HealthScript not found." -ForegroundColor Red; exit 1 }
$HealthScript = (Resolve-Path -LiteralPath $HealthScript).Path

# Quiet by default: no console window (conhost --headless where available).
function Test-HeadlessConhost {
    try {
        if ([Environment]::OSVersion.Version.Build -lt 22000) { return $false }
        & conhost.exe --headless cmd /c exit 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}
# No toast unless -Toast is given at registration.
$toastArg = if ($Toast) { '' } else { ' -NoToast' }
$psArgs = '-NoProfile -ExecutionPolicy Bypass -File "{0}"{1}' -f $HealthScript, $toastArg
if (Test-HeadlessConhost) { $execute = 'conhost.exe'; $arguments = '--headless powershell.exe ' + $psArgs }
else { $execute = 'powershell.exe'; $arguments = '-WindowStyle Hidden ' + $psArgs }
$interval = "(New-TimeSpan -Minutes $EveryMinutes)"

Write-Host "The task would be registered with:`n"
Write-Host "`$action   = New-ScheduledTaskAction -Execute '$execute' -Argument '$arguments'"
Write-Host "`$trigger  = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval $interval"
Write-Host "`$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew"
Write-Host "Register-ScheduledTask -TaskName '$TaskName' -Action `$action -Trigger `$trigger -Settings `$settings -Description 'Orena :8000 health check' -Force"

if (-not $Apply) {
    Write-Host "`nNothing was registered. Re-run with -Apply to register it." -ForegroundColor Yellow
    exit 0
}

$action = New-ScheduledTaskAction -Execute '$execute' -Argument $arguments
# Windows PowerShell 5.1 needs a finite duration on a repeating trigger to register on every build.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Orena :8000 health check' -Force | Out-Null
Write-Host "`nRegistered '$TaskName' every $EveryMinutes minutes." -ForegroundColor Green
