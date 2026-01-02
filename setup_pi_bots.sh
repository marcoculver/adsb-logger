#!/bin/bash
# Setup Telegram bots as systemd services on Raspberry Pi
#
# This script will:
# 1. Install the bots as systemd services
# 2. Configure them to auto-start on boot
# 3. Set up logging
#
# Usage:
#   chmod +x setup_pi_bots.sh
#   sudo ./setup_pi_bots.sh

set -e

echo "========================================"
echo "  ADSB Telegram Bots - Pi Setup"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run with sudo"
    echo "Usage: sudo ./setup_pi_bots.sh"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)

echo "Installing as user: $ACTUAL_USER"
echo "Home directory: $ACTUAL_HOME"
echo ""

# Detect project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Project directory: $SCRIPT_DIR"
echo ""

# Ask user which bots to install
echo "Which bots do you want to install?"
echo "  1) ADSB Flight Extractor only"
echo "  2) Callsign Tracker only"
echo "  3) Both bots"
echo ""
read -p "Enter choice [1-3]: " choice

install_flight_bot=false
install_callsign_bot=false

case $choice in
    1) install_flight_bot=true ;;
    2) install_callsign_bot=true ;;
    3) install_flight_bot=true; install_callsign_bot=true ;;
    *) echo "Invalid choice"; exit 1 ;;
esac

echo ""

# Create systemd service for Flight Bot
if [ "$install_flight_bot" = true ]; then
    echo "Creating Flight Extraction Bot service..."

    # Check if .env file exists
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        echo "ERROR: .env file not found at $SCRIPT_DIR/.env"
        echo "Please create it with your bot tokens:"
        echo "  TELEGRAM_BOT_TOKEN=your-flight-bot-token"
        echo "  TELEGRAM_ALLOWED_USERS=your-telegram-user-id"
        exit 1
    fi

    # Read flight bot token from .env
    FLIGHT_TOKEN=$(grep "^FLIGHT_BOT_TOKEN=" "$SCRIPT_DIR/.env" | cut -d= -f2-)
    ALLOWED_USERS=$(grep "^TELEGRAM_ALLOWED_USERS=" "$SCRIPT_DIR/.env" | cut -d= -f2-)

    if [ -z "$FLIGHT_TOKEN" ] || [ -z "$ALLOWED_USERS" ]; then
        echo "ERROR: Missing FLIGHT_BOT_TOKEN or TELEGRAM_ALLOWED_USERS in .env file"
        exit 1
    fi

    cat > /etc/systemd/system/adsb-flight-bot.service <<EOF
[Unit]
Description=ADSB Flight Extraction Telegram Bot
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$SCRIPT_DIR
Environment="TELEGRAM_BOT_TOKEN=$FLIGHT_TOKEN"
Environment="TELEGRAM_ALLOWED_USERS=$ALLOWED_USERS"
Environment="ADSB_LOG_DIR=/opt/adsb-logs"
Environment="ADSB_OUTPUT_DIR=/opt/adsb-logs/analyses"
ExecStart=/usr/bin/python3 -m telegram_bot.flight_bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    echo "  Created: /etc/systemd/system/adsb-flight-bot.service"
fi

# Create systemd service for Callsign Bot
if [ "$install_callsign_bot" = true ]; then
    echo "Creating Callsign Tracker Bot service..."

    # Read callsign bot token from .env
    CALLSIGN_TOKEN=$(grep "^CALLSIGN_BOT_TOKEN=" "$SCRIPT_DIR/.env" | cut -d= -f2-)

    if [ -z "$CALLSIGN_TOKEN" ]; then
        echo "ERROR: Missing CALLSIGN_BOT_TOKEN in .env file"
        exit 1
    fi

    cat > /etc/systemd/system/callsign-tracker-bot.service <<EOF
[Unit]
Description=Emirates/Flydubai Callsign Tracker Telegram Bot
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$SCRIPT_DIR
Environment="TELEGRAM_BOT_TOKEN=$CALLSIGN_TOKEN"
Environment="TELEGRAM_ALLOWED_USERS=$ALLOWED_USERS"
Environment="CALLSIGN_DB_PATH=/opt/adsb-logs/callsigns.db"
ExecStart=/usr/bin/python3 -m telegram_bot.callsign_bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    echo "  Created: /etc/systemd/system/callsign-tracker-bot.service"
fi

echo ""

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""

# Show commands to manage services
echo "To manage the bots:"
echo ""

if [ "$install_flight_bot" = true ]; then
    echo "ADSB Flight Extraction Bot:"
    echo "  sudo systemctl start adsb-flight-bot      # Start now"
    echo "  sudo systemctl stop adsb-flight-bot       # Stop"
    echo "  sudo systemctl enable adsb-flight-bot     # Auto-start on boot"
    echo "  sudo systemctl status adsb-flight-bot     # Check status"
    echo "  sudo journalctl -u adsb-flight-bot -f     # View logs"
    echo ""
fi

if [ "$install_callsign_bot" = true ]; then
    echo "Callsign Tracker Bot:"
    echo "  sudo systemctl start callsign-tracker-bot      # Start now"
    echo "  sudo systemctl stop callsign-tracker-bot       # Stop"
    echo "  sudo systemctl enable callsign-tracker-bot     # Auto-start on boot"
    echo "  sudo systemctl status callsign-tracker-bot     # Check status"
    echo "  sudo journalctl -u callsign-tracker-bot -f     # View logs"
    echo ""
fi

echo "========================================"
echo ""

# Ask if user wants to start now
read -p "Start the bots now? [y/N]: " start_now

if [[ "$start_now" =~ ^[Yy]$ ]]; then
    echo ""

    if [ "$install_flight_bot" = true ]; then
        echo "Starting ADSB Flight Bot..."
        systemctl start adsb-flight-bot
        systemctl enable adsb-flight-bot
        echo "  ✓ Started and enabled"
    fi

    if [ "$install_callsign_bot" = true ]; then
        echo "Starting Callsign Tracker Bot..."
        systemctl start callsign-tracker-bot
        systemctl enable callsign-tracker-bot
        echo "  ✓ Started and enabled"
    fi

    echo ""
    echo "Bots are now running!"
    echo ""

    # Show status
    sleep 2
    if [ "$install_flight_bot" = true ]; then
        echo "ADSB Flight Bot status:"
        systemctl status adsb-flight-bot --no-pager | head -10
        echo ""
    fi

    if [ "$install_callsign_bot" = true ]; then
        echo "Callsign Tracker Bot status:"
        systemctl status callsign-tracker-bot --no-pager | head -10
        echo ""
    fi
fi

echo "Setup complete!"
echo ""

# Ask about health monitoring
echo "========================================"
echo "  Optional: Health Monitoring"
echo "========================================"
echo ""
echo "Would you like to set up automatic health checks?"
echo "This will:"
echo "  - Check bots every 5 minutes"
echo "  - Send you Telegram alerts if they go down"
echo "  - Automatically try to restart failed bots"
echo ""
read -p "Setup health monitoring? [y/N]: " setup_health

if [[ "$setup_health" =~ ^[Yy]$ ]]; then
    echo ""
    echo "Switching to regular user for health check setup..."
    sudo -u $ACTUAL_USER bash <<HEALTH_SETUP
cd "$SCRIPT_DIR"
chmod +x setup_health_check.sh
./setup_health_check.sh
HEALTH_SETUP
fi
