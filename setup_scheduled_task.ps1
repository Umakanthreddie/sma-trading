# setup_scheduled_task.ps1 - one-time setup for the ongoing paper-trading test.
# Installs dependencies and registers a Windows scheduled task that runs
# the auto-trader every 15 minutes, weekdays, during market hours, indefinitely.
# auto_trade_runner.py's assert_paper_mode() hard-refuses to run unless
# BROKER is "paper" (or "webull" with WEBULL_PAPER=True), so this can be left
# running indefinitely without any real-money risk. Run
# Unregister-ScheduledTask -TaskName SMA-Trader-AutoTrade any time to stop it.

$ErrorActionPreference = "Stop"
$projectDir = $PSScriptRoot
Set-Location $projectDir

Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt

$taskName = "SMA-Trader-AutoTrade"
$batPath  = Join-Path $projectDir "run_auto_trader.bat"

# Remove any existing task with this name so re-running this script is safe
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory $projectDir

$trigger = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "9:35AM"
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "9:35AM" `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Hours 6 -Minutes 25)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "SMA-trader paper-trading test - runs indefinitely (paper mode only)" | Out-Null

Write-Host ""
Write-Host "Done. Scheduled task '$taskName' created." -ForegroundColor Green
Write-Host "It will run every 15 minutes, weekdays, 9:35 AM - ~4:00 PM ET, indefinitely."
Write-Host "It only ever trades in paper mode - auto_trade_runner.py refuses to run otherwise."
Write-Host "To stop it later: Unregister-ScheduledTask -TaskName $taskName"
Write-Host "Output logs to: $projectDir\scheduler_output.log and auto_trade_log.jsonl"
Write-Host ""
Write-Host "To test it right now instead of waiting for the next scheduled hour, run:"
Write-Host "  python auto_trade_runner.py --force"
