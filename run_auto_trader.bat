@echo off
REM run_auto_trader.bat — wrapper invoked by Windows Task Scheduler.
REM Installs/updates dependencies (fast no-op once installed) then runs
REM the headless paper-trading auto-trader. All output is appended to
REM scheduler_output.log for review.

cd /d "%~dp0"
echo. >> scheduler_output.log
echo ==== Run started %date% %time% ==== >> scheduler_output.log
pip install -r requirements.txt >> scheduler_output.log 2>&1
python auto_trade_runner.py >> scheduler_output.log 2>&1
echo ==== Run finished %date% %time% ==== >> scheduler_output.log
