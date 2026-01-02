#!/bin/bash
# Emirates/Flydubai Callsign Tracker Bot Launcher
#
# This bot tracks Emirates/Flydubai flights only (schedule patterns, lookups)
# For extracting ANY flight data, use run_bot.sh instead
#
# Usage:
#   1. Make executable: chmod +x run_callsign_bot.sh
#   2. Run: ./run_callsign_bot.sh

# --- Configuration ---
# Bot: @callsignloggerbot
# Set TELEGRAM_BOT_TOKEN environment variable before running
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN environment variable not set"
    echo "Get your token from @BotFather and set it:"
    echo "  export TELEGRAM_BOT_TOKEN='your-token-here'"
    exit 1
fi

# Your Telegram user ID (get it by messaging @userinfobot)
# Multiple users: comma-separated, e.g., 123456789,987654321
export TELEGRAM_ALLOWED_USERS="${TELEGRAM_ALLOWED_USERS:-1269568755}"

# Database path
export CALLSIGN_DB_PATH="${CALLSIGN_DB_PATH:-/opt/adsb-logs/callsigns.db}"

# --- End Configuration ---

echo "============================================================"
echo "   Emirates/Flydubai Callsign Tracker Bot"
echo "   Bot: @callsignloggerbot"
echo "============================================================"
echo ""
echo "Database: $CALLSIGN_DB_PATH"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Please install Python 3.9+"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "telegram_bot/callsign_bot.py" ]; then
    echo "ERROR: callsign_bot.py not found. Make sure you're in the adsb-logger directory."
    exit 1
fi

# Check dependencies
echo "Checking dependencies..."
python3 -c "import telegram" 2>/dev/null
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: python-telegram-bot not installed"
    echo "Install with: pip install python-telegram-bot"
    exit 1
fi

echo "Starting Callsign Tracker Bot..."
echo "Press Ctrl+C to stop"
echo ""

python3 -m telegram_bot.callsign_bot
