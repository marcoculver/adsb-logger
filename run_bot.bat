@echo off
REM ADS-B Flight Extractor Telegram Bot Launcher
REM
REM Usage:
REM   1. Set your Telegram bot token below or as environment variable
REM   2. Set your Telegram user ID below for whitelist
REM   3. Double-click this file or run from command prompt

REM --- Configuration ---
REM Get your bot token from @BotFather on Telegram
if not defined TELEGRAM_BOT_TOKEN (
    set TELEGRAM_BOT_TOKEN=8230471568:AAHuAf9uYkd9S5ZngkZ7PBo2aXEd4QrttsA
)

REM Your Telegram user ID (get it by messaging @userinfobot)
REM Multiple users: comma-separated, e.g., 123456789,987654321
if not defined TELEGRAM_ALLOWED_USERS (
    set TELEGRAM_ALLOWED_USERS=1269568755
)

REM Log directory (Dropbox synced logs)
if not defined ADSB_LOG_DIR (
    set ADSB_LOG_DIR=M:\Dropbox\ADSBPi-Base\raw
)

REM Output directory for analyses
if not defined ADSB_OUTPUT_DIR (
    set ADSB_OUTPUT_DIR=M:\Dropbox\ADSBPi-Base\analyses
)

REM --- End Configuration ---

echo ============================================================
echo   ADS-B Flight Extractor - Telegram Bot
echo ============================================================
echo.
echo Log Directory: %ADSB_LOG_DIR%
echo Output Directory: %ADSB_OUTPUT_DIR%
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "%~dp0telegram_bot\bot.py" (
    echo ERROR: bot.py not found. Make sure you're in the adsb-logger directory.
    pause
    exit /b 1
)

REM Change to script directory
cd /d "%~dp0"

echo Starting bot...
echo Press Ctrl+C to stop
echo.

python -m telegram_bot.bot

if errorlevel 1 (
    echo.
    echo Bot exited with error. Check the output above.
    pause
)
