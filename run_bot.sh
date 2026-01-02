#!/bin/bash
# ADS-B Flight Extractor Telegram Bot Launcher
#
# This bot extracts ANY flight from ADSB logs (not just Emirates/Flydubai)
# For callsign tracking, use run_callsign_bot.sh instead
#
# Usage:
#   1. Make executable: chmod +x run_bot.sh
#   2. Run: ./run_bot.sh

# --- Configuration ---
# Set TELEGRAM_BOT_TOKEN environment variable before running
# Get your bot token from @BotFather on Telegram
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN environment variable not set"
    echo "Get your token from @BotFather and set it:"
    echo "  export TELEGRAM_BOT_TOKEN='your-token-here'"
    exit 1
fi

# Your Telegram user ID (get it by messaging @userinfobot)
# Multiple users: comma-separated, e.g., 123456789,987654321
export TELEGRAM_ALLOWED_USERS="${TELEGRAM_ALLOWED_USERS:-1269568755}"

# Database and log paths (Linux defaults)
export ADSB_LOG_DIR="${ADSB_LOG_DIR:-/opt/adsb-logs}"
export ADSB_OUTPUT_DIR="${ADSB_OUTPUT_DIR:-/opt/adsb-logs/analyses}"
export CALLSIGN_DB_PATH="${CALLSIGN_DB_PATH:-/opt/adsb-logs/callsigns.db}"

# --- End Configuration ---

echo "============================================================"
echo "   ADS-B Flight Extractor - Telegram Bot"
echo "============================================================"
echo ""
echo "Log Directory: $ADSB_LOG_DIR"
echo "Output Directory: $ADSB_OUTPUT_DIR"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Please install Python 3.9+"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "telegram_bot/bot.py" ]; then
    echo "ERROR: bot.py not found. Make sure you're in the adsb-logger directory."
    exit 1
fi

# Check dependencies
echo "Checking dependencies..."
python3 -c "import telegram" 2>/dev/null
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: python-telegram-bot not installed"
    echo "Install with: pip install -r requirements.txt"
    echo "Or: pip install python-telegram-bot numpy pandas matplotlib plotly simplekml"
    exit 1
fi

echo "Starting Flight Extraction Bot..."
echo "Press Ctrl+C to stop"
echo ""

python3 -m telegram_bot.flight_bot
