@echo off
cd /d "%~dp0"
echo Starting Apple Music Playlist Scanner daemon...
python scanner.py --daemon
pause
