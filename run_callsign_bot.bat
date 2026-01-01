@echo off
REM Emirates/Flydubai Callsign Tracker Bot Launcher
REM
REM This bot tracks Emirates/Flydubai flights only (schedule patterns, lookups)
REM For extracting ANY flight data, use run_bot.bat instead
REM
REM Usage:
REM   1. Set your Telegram bot token below or as environment variable
REM   2. Set your Telegram user ID below for whitelist
REM   3. Double-click this file or run from command prompt

REM --- Configuration ---
REM Get your bot token from @BotFather on Telegram
REM Bot: @callsignloggerbot
if not defined TELEGRAM_BOT_TOKEN (
    set TELEGRAM_BOT_TOKEN=8380442252:AAHhJd8vHDGEDHZK0-F7k7LY3fwmnINqGbw
)

REM Your Telegram user ID (get it by messaging @userinfobot)
REM Multiple users: comma-separated, e.g., 123456789,987654321
if not defined TELEGRAM_ALLOWED_USERS (
    set TELEGRAM_ALLOWED_USERS=1269568755
)

REM Database path
if not defined CALLSIGN_DB_PATH (
    set CALLSIGN_DB_PATH=M:\Dropbox\ADSBPi-Base\callsigns.db
)

REM --- End Configuration ---

echo ============================================================
echo   Emirates/Flydubai Callsign Tracker Bot
echo   Bot: @callsignloggerbot
echo ============================================================
echo.
echo Database: %CALLSIGN_DB_PATH%
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "%~dp0telegram_bot\callsign_bot.py" (
    echo ERROR: callsign_bot.py not found. Make sure you're in the adsb-logger directory.
    pause
    exit /b 1
)

REM Change to script directory
cd /d "%~dp0"

echo Starting Callsign Tracker Bot...
echo Press Ctrl+C to stop
echo.

python -m telegram_bot.callsign_bot

if errorlevel 1 (
    echo.
    echo Bot exited with error. Check the output above.
    pause
)
