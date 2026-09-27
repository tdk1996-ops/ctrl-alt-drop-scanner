@echo off
cd /d "%~dp0"
echo Running Apple Music Playlist Scanner check...
python scanner.py --check
pause
