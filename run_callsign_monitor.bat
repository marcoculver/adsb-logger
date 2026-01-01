@echo off
REM Callsign Monitor - Track Emirates and Flydubai flights
REM
REM This runs the background monitor that continuously scans
REM ADS-B logs for UAE and FDB callsigns.

REM --- Configuration ---
if not defined FR24_API_TOKEN (
    set FR24_API_TOKEN=019b78ac-9271-7363-a509-d40935899ac5^|VdqpeiWbwaeUlsowb4eOV2Utrm481SWbyNpvI1bYf0bb4efd
)

REM Log and database directories
if not defined ADSB_LOG_DIR (
    set ADSB_LOG_DIR=M:\Dropbox\ADSBPi-Base\raw
)

echo ============================================================
echo   Callsign Monitor - Emirates ^& Flydubai
echo ============================================================
echo.
echo Log Directory: %ADSB_LOG_DIR%
echo Database: M:\Dropbox\ADSBPi-Base\callsigns.db
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)

cd /d "%~dp0"

echo Starting monitor...
echo Press Ctrl+C to stop
echo.

python callsign_cli.py monitor

pause
