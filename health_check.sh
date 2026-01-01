#!/bin/bash
# Health check script for Telegram bots
#
# This script checks if the bots are running and sends Telegram alerts if they're down.
# Run via cron every 5 minutes.
#
# Setup:
#   1. Edit ALERT_CHAT_ID below (your Telegram user ID)
#   2. chmod +x health_check.sh
#   3. Test: ./health_check.sh
#   4. Add to crontab: crontab -e
#      */5 * * * * /path/to/health_check.sh >> /var/log/bot-health.log 2>&1

# Configuration
ALERT_CHAT_ID="1269568755"  # Your Telegram user ID
ALERT_BOT_TOKEN="8380442252:AAHhJd8vHDGEDHZK0-F7k7LY3fwmnINqGbw"  # Use callsign bot for alerts

# State files to track if we already alerted
STATE_DIR="/tmp/bot-health-state"
mkdir -p "$STATE_DIR"

# Timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Function to send Telegram alert
send_alert() {
    local message="$1"
    local full_message="🚨 Bot Alert - $TIMESTAMP\n\n$message"

    curl -s -X POST "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ALERT_CHAT_ID}" \
        -d "text=${full_message}" \
        -d "parse_mode=HTML" \
        > /dev/null 2>&1
}

# Function to send recovery alert
send_recovery() {
    local message="$1"
    local full_message="✅ Bot Recovered - $TIMESTAMP\n\n$message"

    curl -s -X POST "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ALERT_CHAT_ID}" \
        -d "text=${full_message}" \
        > /dev/null 2>&1
}

# Function to check a service
check_service() {
    local service_name="$1"
    local display_name="$2"
    local state_file="$STATE_DIR/${service_name}.down"

    if systemctl is-active --quiet "$service_name"; then
        # Service is running
        if [ -f "$state_file" ]; then
            # Was down before, send recovery alert
            send_recovery "$display_name is back online"
            rm "$state_file"
            echo "[$TIMESTAMP] ✅ $display_name recovered"
        fi
    else
        # Service is down
        if [ ! -f "$state_file" ]; then
            # First time detecting it's down, send alert
            send_alert "$display_name is DOWN!\n\nAttempting automatic restart..."
            touch "$state_file"
            echo "[$TIMESTAMP] 🚨 $display_name is DOWN - Alert sent"

            # Try to restart
            sudo systemctl restart "$service_name"
            sleep 3

            # Check if restart worked
            if systemctl is-active --quiet "$service_name"; then
                send_recovery "$display_name was down but automatically restarted successfully"
                rm "$state_file"
                echo "[$TIMESTAMP] ✅ $display_name auto-restarted successfully"
            else
                echo "[$TIMESTAMP] ❌ $display_name auto-restart FAILED"
            fi
        else
            # Already alerted, just log
            echo "[$TIMESTAMP] ⚠️  $display_name still down (already alerted)"
        fi
    fi
}

# Check each bot
echo "[$TIMESTAMP] Starting health check..."

# Check if services exist before checking them
if systemctl list-unit-files | grep -q "adsb-flight-bot.service"; then
    check_service "adsb-flight-bot" "ADSB Flight Extraction Bot"
fi

if systemctl list-unit-files | grep -q "callsign-tracker-bot.service"; then
    check_service "callsign-tracker-bot" "Callsign Tracker Bot"
fi

if systemctl list-unit-files | grep -q "callsign-monitor.service"; then
    check_service "callsign-monitor" "Callsign Monitor"
fi

echo "[$TIMESTAMP] Health check complete"
