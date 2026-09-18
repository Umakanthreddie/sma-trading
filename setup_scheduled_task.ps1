# setup_scheduled_task.ps1 - one-time setup for the 2-week paper-trading test.
# Installs dependencies and registers a Windows scheduled task that runs
# the auto-trader every 30 minutes, weekdays, during market hours, for 14 days.
# After 14 days the task's trigger expires automatically and stops firing.

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
    -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -RepetitionDuration (New-TimeSpan -Hours 6 -Minutes 25)).Repetition

# Auto-expire after 14 days - the task stops firing on its own after this.
$endDate = (Get-Date).AddDays(14)
$trigger.EndBoundary = $endDate.ToString("yyyy-MM-ddTHH:mm:ss")

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "SMA-trader paper-trading test - auto-expires $($endDate.ToString('yyyy-MM-dd'))" | Out-Null

Write-Host ""
Write-Host "Done. Scheduled task '$taskName' created." -ForegroundColor Green
Write-Host "It will run every 30 minutes, weekdays, 9:35 AM - ~4:00 PM ET, and auto-expire on $($endDate.ToString('yyyy-MM-dd'))."
Write-Host "Output logs to: $projectDir\scheduler_output.log and auto_trade_log.jsonl"
Write-Host ""
Write-Host "To test it right now instead of waiting for the next scheduled hour, run:"
Write-Host "  python auto_trade_runner.py --force"
