# Registers a Windows Task Scheduler job that starts the Anibis Telegram bot
# when you log in, and re-checks every 15 minutes that it's still running
# (a second copy exits straight away). Run via install_schedule.bat.
param(
    [string]$Script = "main.py",   # entry script, in this same folder (older copies used sada.py)
    [int]$Minutes = 15             # watchdog interval
)
$ErrorActionPreference = "Stop"
$TaskName = "Anibis Alarm"
$Folder = $PSScriptRoot
$ScriptPath = Join-Path $Folder $Script
if (-not (Test-Path $ScriptPath) -and (Test-Path (Join-Path $Folder "sada.py"))) { $ScriptPath = Join-Path $Folder "sada.py" }
if (-not (Test-Path $ScriptPath)) { throw "Can't find $ScriptPath" }

# pythonw runs Python without a console window.
$Pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $Pythonw) {
    $Python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $Python) { throw "Python isn't on PATH. Install it from python.org and tick 'Add to PATH'." }
    $Pythonw = Join-Path (Split-Path $Python) "pythonw.exe"
}

$Action   = New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$ScriptPath`"" -WorkingDirectory $Folder
$Triggers = @(
    New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    # Watchdog: restarts the bot if it crashed; does nothing while it's running.
    New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $Minutes)
)
# Zero time limit = run indefinitely (the bot is a long-running process).
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Triggers -Settings $Settings `
    -Description "Anibis Telegram bot: searches Anibis and sends new listings to Telegram" -Force | Out-Null

Write-Host "Scheduled '$TaskName': starts $Script at logon and checks every $Minutes minutes that it's running."
Write-Host "The bot starts in about a minute. To stop it, double-click remove_schedule.bat."
