# Running Telegram Bots on Raspberry Pi

Run the Telegram bots directly on your Pi so they stay running 24/7, even if your PC reboots.

## Quick Setup (Automated)

### Step 1: SSH to Your Pi

```bash
ssh pi@your-pi-address
cd /path/to/adsb-logger
```

### Step 2: Run Setup Script

```bash
chmod +x setup_pi_bots.sh
sudo ./setup_pi_bots.sh
```

The script will:
- Ask which bots you want (flight, callsign, or both)
- Install them as systemd services
- Configure auto-start on boot
- Optionally start them immediately

That's it! Your bots are now running as services.

The script will also optionally set up **health monitoring** to alert you via Telegram if a bot goes down.

---

## Managing the Bots

### Start/Stop/Restart

```bash
# ADSB Flight Extraction Bot
sudo systemctl start adsb-flight-bot
sudo systemctl stop adsb-flight-bot
sudo systemctl restart adsb-flight-bot

# Callsign Tracker Bot
sudo systemctl start callsign-tracker-bot
sudo systemctl stop callsign-tracker-bot
sudo systemctl restart callsign-tracker-bot
```

### Enable/Disable Auto-Start on Boot

```bash
# Enable (start automatically on boot)
sudo systemctl enable adsb-flight-bot
sudo systemctl enable callsign-tracker-bot

# Disable (don't start on boot)
sudo systemctl disable adsb-flight-bot
sudo systemctl disable callsign-tracker-bot
```

### Check Status

```bash
# Quick status check
sudo systemctl status adsb-flight-bot
sudo systemctl status callsign-tracker-bot

# View live logs
sudo journalctl -u adsb-flight-bot -f
sudo journalctl -u callsign-tracker-bot -f

# View recent logs
sudo journalctl -u adsb-flight-bot -n 50
sudo journalctl -u callsign-tracker-bot -n 50
```

---

## Manual Setup (Alternative)

If you prefer to set up manually:

### 1. Install Dependencies

```bash
pip3 install python-telegram-bot numpy pandas matplotlib plotly simplekml
```

### 2. Create Service Files

**Flight Bot:** `/etc/systemd/system/adsb-flight-bot.service`
```ini
[Unit]
Description=ADSB Flight Extraction Telegram Bot
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/adsb-logger
Environment="TELEGRAM_BOT_TOKEN=[REDACTED-FLIGHT-BOT-TOKEN]"
Environment="TELEGRAM_ALLOWED_USERS=[REDACTED-USER-ID]"
Environment="ADSB_LOG_DIR=/opt/adsb-logs"
Environment="ADSB_OUTPUT_DIR=/opt/adsb-logs/analyses"
ExecStart=/usr/bin/python3 -m telegram_bot.flight_bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Callsign Bot:** `/etc/systemd/system/callsign-tracker-bot.service`
```ini
[Unit]
Description=Emirates/Flydubai Callsign Tracker Telegram Bot
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/adsb-logger
Environment="TELEGRAM_BOT_TOKEN=[REDACTED-CALLSIGN-BOT-TOKEN]"
Environment="TELEGRAM_ALLOWED_USERS=[REDACTED-USER-ID]"
Environment="CALLSIGN_DB_PATH=/opt/adsb-logs/callsigns.db"
ExecStart=/usr/bin/python3 -m telegram_bot.callsign_bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable adsb-flight-bot
sudo systemctl enable callsign-tracker-bot
sudo systemctl start adsb-flight-bot
sudo systemctl start callsign-tracker-bot
```

---

## Configuration

### Change Tokens or User IDs

Edit the service file:
```bash
sudo nano /etc/systemd/system/adsb-flight-bot.service
```

Then reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart adsb-flight-bot
```

### Change Data Paths

Edit the `Environment=` lines in the service files:
- `ADSB_LOG_DIR` - Where ADSB logs are stored
- `ADSB_OUTPUT_DIR` - Where flight analyses are saved
- `CALLSIGN_DB_PATH` - Callsign database location

---

## Health Monitoring & Alerts

### Automated Health Checks

The bots include an automated health monitoring system that:
- Checks if bots are running every 5 minutes
- Sends you Telegram alerts if they go down
- Automatically attempts to restart failed bots
- Notifies you when bots recover

### Setup Health Monitoring

```bash
cd /path/to/adsb-logger
chmod +x setup_health_check.sh
./setup_health_check.sh
```

The script will:
1. Ask for your Telegram user ID
2. Configure the health check script
3. Set up a cron job to run every 5 minutes
4. Create a log file at `/var/log/bot-health.log`

### What You'll Receive

**When a bot goes down:**
```
🚨 Bot Alert - 2026-01-01 14:30:00

ADSB Flight Extraction Bot is DOWN!

Attempting automatic restart...
```

**When it recovers:**
```
✅ Bot Recovered - 2026-01-01 14:31:00

ADSB Flight Extraction Bot is back online
```

**If auto-restart succeeds:**
```
✅ Bot Recovered - 2026-01-01 14:30:15

ADSB Flight Extraction Bot was down but
automatically restarted successfully
```

### View Health Check Logs

```bash
# Live monitoring
tail -f /var/log/bot-health.log

# Recent checks
tail -50 /var/log/bot-health.log

# Search for issues
grep "DOWN" /var/log/bot-health.log
grep "FAILED" /var/log/bot-health.log
```

### Manual Health Check

Run the health check manually anytime:
```bash
/path/to/adsb-logger/health_check.sh
```

### Disable Health Monitoring

```bash
# Remove from cron
crontab -e
# Delete the line with health_check.sh

# Or remove all cron jobs
crontab -r
```

---

## Monitoring & Logs

### Check if Bots are Running

```bash
# Simple check
systemctl is-active adsb-flight-bot
systemctl is-active callsign-tracker-bot

# Detailed status
sudo systemctl status adsb-flight-bot
sudo systemctl status callsign-tracker-bot
```

### View Logs

```bash
# Live logs (follow mode)
sudo journalctl -u adsb-flight-bot -f
sudo journalctl -u callsign-tracker-bot -f

# Last 100 lines
sudo journalctl -u adsb-flight-bot -n 100

# Logs since yesterday
sudo journalctl -u adsb-flight-bot --since yesterday

# Logs with errors only
sudo journalctl -u adsb-flight-bot -p err

# Both bots together
sudo journalctl -u adsb-flight-bot -u callsign-tracker-bot -f
```

### Set Up Alerts (Optional)

Create a script to notify you if a bot stops:

```bash
#!/bin/bash
# /home/pi/check_bots.sh

if ! systemctl is-active --quiet adsb-flight-bot; then
    echo "ADSB Flight Bot is DOWN!"
    # Add notification here (email, SMS, etc.)
fi

if ! systemctl is-active --quiet callsign-tracker-bot; then
    echo "Callsign Tracker Bot is DOWN!"
    # Add notification here
fi
```

Add to crontab:
```bash
crontab -e
# Add: */5 * * * * /home/pi/check_bots.sh
```

---

## Troubleshooting

### Bot Won't Start

**Check logs:**
```bash
sudo journalctl -u adsb-flight-bot -n 50
```

**Common issues:**
1. **Import errors** - Missing dependencies
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Permission errors** - Wrong user in service file
   ```bash
   # Edit service file, change User= line
   sudo nano /etc/systemd/system/adsb-flight-bot.service
   ```

3. **Path errors** - Wrong WorkingDirectory
   ```bash
   # Check your actual path
   pwd
   # Update service file
   ```

### Bot Keeps Restarting

**Check for errors:**
```bash
sudo journalctl -u adsb-flight-bot -n 100 | grep -i error
```

**Common causes:**
- Invalid bot token
- Network connectivity issues
- Database permissions
- Missing data directories

### Bot Not Responding to Commands

1. **Check bot is running:**
   ```bash
   sudo systemctl status adsb-flight-bot
   ```

2. **Check user ID is correct:**
   - Message `@userinfobot` on Telegram to get your ID
   - Update service file with correct user ID
   - Reload and restart

3. **Test bot token:**
   ```bash
   # Test with curl
   TOKEN="[REDACTED-FLIGHT-BOT-TOKEN]"
   curl -s "https://api.telegram.org/bot$TOKEN/getMe" | jq
   ```

---

## Performance Tips

### Resource Usage

Bots are lightweight but chart generation can use CPU:
- Flight bot: ~50-100MB RAM (more during chart generation)
- Callsign bot: ~30-50MB RAM

### Reduce Resource Usage

1. **Use haiku model for charts** (if available)
2. **Limit concurrent extractions** (flight bot)
3. **Monitor Pi temperature:**
   ```bash
   vcgencmd measure_temp
   ```

---

## Backup & Recovery

### Backup Service Configs

```bash
sudo cp /etc/systemd/system/adsb-flight-bot.service ~/backup/
sudo cp /etc/systemd/system/callsign-tracker-bot.service ~/backup/
```

### Restore After Pi Reinstall

1. Copy service files back to `/etc/systemd/system/`
2. Run:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable adsb-flight-bot callsign-tracker-bot
   sudo systemctl start adsb-flight-bot callsign-tracker-bot
   ```

---

## Running with Callsign Monitor

Run both the callsign monitor and tracker bot together:

```bash
# The monitor collects data
sudo systemctl start callsign-monitor

# The bot provides Telegram interface
sudo systemctl start callsign-tracker-bot
```

See `run_callsign_monitor.sh` for monitor setup.

---

## Uninstall

```bash
# Stop and disable services
sudo systemctl stop adsb-flight-bot callsign-tracker-bot
sudo systemctl disable adsb-flight-bot callsign-tracker-bot

# Remove service files
sudo rm /etc/systemd/system/adsb-flight-bot.service
sudo rm /etc/systemd/system/callsign-tracker-bot.service

# Reload systemd
sudo systemctl daemon-reload
```

---

## Summary

**Initial Setup:**
```bash
sudo ./setup_pi_bots.sh
```

**Daily Use:**
```bash
# Check status
sudo systemctl status adsb-flight-bot callsign-tracker-bot

# View logs
sudo journalctl -u adsb-flight-bot -u callsign-tracker-bot -f

# Restart if needed
sudo systemctl restart adsb-flight-bot
```

**After Updating Code:**
```bash
cd /path/to/adsb-logger
git pull
sudo systemctl restart adsb-flight-bot callsign-tracker-bot
```

Your bots will now run 24/7 on your Pi!
