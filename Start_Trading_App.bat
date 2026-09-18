@echo off
title AI Stock Trading App
echo.
echo  ==========================================
echo   AI Stock Trading Dashboard
echo   Starting... please wait
echo  ==========================================
echo.
cd /d C:\Users\umaka\.gemini\antigravity\scratch\sma-trader
set PYTHONIOENCODING=utf-8
echo  Opening browser at http://localhost:8501
echo  Press Ctrl+C in this window to stop the app.
echo.
streamlit run dashboard.py --server.port 8501
pause
