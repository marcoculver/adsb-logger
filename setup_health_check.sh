#!/bin/bash
# Setup health check monitoring for Telegram bots
#
# This will:
# 1. Install the health check script
# 2. Set up cron job to run every 5 minutes
# 3. Configure Telegram alerts
#
# Usage:
#   chmod +x setup_health_check.sh
#   sudo ./setup_health_check.sh

set -e

echo "========================================"
echo "  Bot Health Check Setup"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Don't run this with sudo"
    echo "Usage: ./setup_health_check.sh"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
HEALTH_CHECK_SCRIPT="$SCRIPT_DIR/health_check.sh"

# Check if health check script exists
if [ ! -f "$HEALTH_CHECK_SCRIPT" ]; then
    echo "ERROR: health_check.sh not found"
    exit 1
fi

# Make executable
chmod +x "$HEALTH_CHECK_SCRIPT"

echo "Health check script: $HEALTH_CHECK_SCRIPT"
echo ""

# Ask for Telegram user ID
echo "Enter your Telegram User ID for alerts:"
echo "(Message @userinfobot on Telegram to get your ID)"
read -p "User ID: " user_id

if [ -z "$user_id" ]; then
    echo "ERROR: User ID required"
    exit 1
fi

# Update the health check script with user ID
sed -i "s/ALERT_CHAT_ID=\"[^\"]*\"/ALERT_CHAT_ID=\"$user_id\"/" "$HEALTH_CHECK_SCRIPT"

echo ""
echo "Updated health check script with your user ID"
echo ""

# Test the health check
echo "Testing health check..."
"$HEALTH_CHECK_SCRIPT"

echo ""
echo "Test complete. Check if you received a Telegram message."
echo ""

# Add to crontab
echo "Setting up cron job (runs every 5 minutes)..."

# Create cron job entry
CRON_JOB="*/5 * * * * $HEALTH_CHECK_SCRIPT >> /var/log/bot-health.log 2>&1"

# Check if cron job already exists
(crontab -l 2>/dev/null | grep -F "$HEALTH_CHECK_SCRIPT") && {
    echo "Cron job already exists, updating..."
    crontab -l | grep -v "$HEALTH_CHECK_SCRIPT" | crontab -
}

# Add cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Cron job installed!"
echo ""

# Create log file
sudo touch /var/log/bot-health.log
sudo chown $USER:$USER /var/log/bot-health.log

echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Health checks will run every 5 minutes"
echo ""
echo "You will receive Telegram alerts if:"
echo "  - A bot goes down"
echo "  - A bot recovers"
echo "  - Auto-restart succeeds or fails"
echo ""
echo "View logs:"
echo "  tail -f /var/log/bot-health.log"
echo ""
echo "Manual test:"
echo "  $HEALTH_CHECK_SCRIPT"
echo ""
echo "Remove monitoring:"
echo "  crontab -e  # Delete the health check line"
echo ""
