@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo Setting up Windows Task Scheduler for Apple Music Scanner
echo ===================================================

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Python is not found in PATH!
    pause
    exit /b 1
)

set SCRIPT_PATH=%~dp0scanner.py
set VBS_RUNNER=%~dp0run_silent.vbs

:: Create silent runner VBScript so no black window flashes every 30 minutes
echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_RUNNER%"
echo WshShell.Run "python """ ^& "%SCRIPT_PATH%" ^& """ --check", 0, False >> "%VBS_RUNNER%"

echo Registering task to run every 30 minutes silently...
schtasks /create /tn "AppleMusicPlaylistScanner" /tr "wscript.exe \"%VBS_RUNNER%\"" /sc MINUTE /mo 30 /f

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCCESS] Scheduled task 'AppleMusicPlaylistScanner' created successfully!
    echo It will now run every 30 minutes in the background automatically.
    echo.
    echo To delete the task anytime, run:
    echo   schtasks /delete /tn "AppleMusicPlaylistScanner" /f
) else (
    echo.
    echo [ERROR] Failed to register task. Try running this script as Administrator.
)

pause
