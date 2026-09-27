@echo off
cd /d "%~dp0"
echo ========================================================
echo Starting Apple Music Telegram Bot Interactive Listener
echo • Type 'scan' in your Telegram channel to trigger a scan
echo • Automatic scans continue in background every 30 mins
echo ========================================================
python -u scanner.py --listen
pause
