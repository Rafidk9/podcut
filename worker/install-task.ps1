<#
.SYNOPSIS
  Register the PodCut render worker as a Windows scheduled task so it starts at
  logon and restarts itself if it dies.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File worker\install-task.ps1
  powershell -ExecutionPolicy Bypass -File worker\install-task.ps1 -Uninstall

.NOTES
  Run as your normal user, not elevated -- the task must run in your session so
  it inherits your PATH (ffmpeg, node) and can spawn headless Chromium.
#>
param(
    [switch]$Uninstall,
    [string]$TaskName = "PodCut Render Worker"
)

$ErrorActionPreference = "Stop"

$workerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script    = Join-Path $workerDir "podcut_worker.py"

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task '$TaskName'."
    } else {
        Write-Host "No scheduled task named '$TaskName'."
    }
    return
}

if (-not (Test-Path $script)) { throw "Cannot find $script" }
if (-not (Test-Path (Join-Path $workerDir ".env"))) {
    throw "worker\.env is missing. Copy worker\.env.example to worker\.env and fill in SUPABASE_URL and SUPABASE_SERVICE_KEY first."
}

# Prefer the engine venv, same default the worker itself uses.
$venvPython = Join-Path (Split-Path -Parent $workerDir) "engine\.venv\Scripts\python.exe"
if (Test-Path $venvPython) { $python = $venvPython }
else {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $python) { throw "No python found on PATH and no engine\.venv." }
}

# pythonw.exe runs without a console window; fall back to python.exe if absent.
$pythonw = $python -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $python }

$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "`"$script`"" -WorkingDirectory $workerDir

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# RestartCount/-Interval bring it back if the process dies; ExecutionTimeLimit 0
# means never kill it, since a long render must not be interrupted.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Runs podcut reel renders queued from the cloud UI." `
    -Force | Out-Null

Write-Host "Registered '$TaskName'."
Write-Host "  python : $pythonw"
Write-Host "  script : $script"
Write-Host ""
Write-Host "Start it now with:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Check on it with :  Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host ""
Write-Host "The worker only renders while this machine is awake. Consider:"
Write-Host "  powercfg /change standby-timeout-ac 0"
