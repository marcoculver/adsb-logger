# Setting Up ADSB Logger on Raspberry Pi - Complete Guide

This guide walks you through setting up the entire ADSB logger system on your Raspberry Pi from scratch.

## Prerequisites

- Raspberry Pi with Raspbian/Raspberry Pi OS
- Internet connection
- SSH access to your Pi
- Your ADSB data already being collected (tar1090/readsb running)

## Step 1: Connect to Your Pi

```bash
# From your PC
ssh pi@your-pi-ip-address
# Default password is usually 'raspberry' (change it!)
```

## Step 2: Install Required System Packages

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3 and pip (usually already installed)
sudo apt-get install -y python3 python3-pip git

# Install system dependencies for matplotlib/numpy
sudo apt-get install -y python3-numpy python3-matplotlib python3-pandas

# Or install all Python packages via pip (slower but gets latest versions)
pip3 install python-telegram-bot numpy pandas matplotlib plotly simplekml
```

## Step 3: Create Directory Structure

```bash
# Create main data directory
sudo mkdir -p /opt/adsb-logs
sudo chown $USER:$USER /opt/adsb-logs

# Create subdirectories
mkdir -p /opt/adsb-logs/analyses
mkdir -p /opt/adsb-logs/raw

# Clone the project
cd ~
git clone https://github.com/marcoculver/adsb-logger.git
cd adsb-logger

# Or if you prefer a different location:
# cd /opt
# sudo git clone https://github.com/marcoculver/adsb-logger.git
# sudo chown -R $USER:$USER adsb-logger
# cd adsb-logger
```

## Step 4: Verify Your ADSB Data Location

Find where your ADSB data is being written:

```bash
# Common locations:
ls -la /run/readsb/
ls -la /run/dump1090-fa/
ls -la /var/run/dump1090-mutability/

# Or check your readsb/dump1090 config
cat /etc/default/readsb
cat /etc/default/dump1090-fa
```

**Note the directory** - you'll need it for configuration.

## Step 5: Link or Configure ADSB Log Path

### Option A: Create a Symlink (Recommended)

If your ADSB data is at `/run/readsb/`:
```bash
sudo ln -s /run/readsb /opt/adsb-logs/raw
```

### Option B: Configure Monitor to Read From Your Location

Edit the service files later to point to your actual ADSB data directory.

## Step 6: Test Python Dependencies

```bash
cd ~/adsb-logger

# Test imports
python3 -c "
from callsign_logger import CallsignDatabase, FlightRadar24API
from flight_extractor import FlightExtractor
print('✓ All imports successful')
"
```

If you get errors, install missing packages:
```bash
pip3 install -r requirements.txt
```

## Step 7: Test Database Creation

```bash
# Test database can be created
python3 -c "
from callsign_logger import CallsignDatabase
db = CallsignDatabase()
print(f'✓ Database created at: {db.db_path}')
"

# Should show: /opt/adsb-logs/callsigns.db
```

## Step 8: Test FR24 API Connection

```bash
python3 -c "
from callsign_logger.fr24_api import FlightRadar24API
api = FlightRadar24API()
if api.test_connection():
    print('✓ FR24 API connection successful')
else:
    print('✗ FR24 API connection failed')
"
```

## Step 9: Install Telegram Bots as Services

```bash
cd ~/adsb-logger
chmod +x setup_pi_bots.sh
sudo ./setup_pi_bots.sh
```

The script will ask:
1. **Which bots?** → Choose 3 (Both bots)
2. **Start now?** → Yes
3. **Setup health monitoring?** → Yes
4. **Your Telegram user ID?** → Enter your ID from @userinfobot

## Step 10: Install Callsign Monitor (Optional)

If you want to continuously track Emirates/Flydubai callsigns:

```bash
# Create systemd service for monitor
sudo nano /etc/systemd/system/callsign-monitor.service
```

Paste this (adjust paths if needed):
```ini
[Unit]
Description=Emirates/Flydubai Callsign Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/adsb-logger
Environment="ADSB_LOG_DIR=/opt/adsb-logs/raw"
Environment="CALLSIGN_DB_PATH=/opt/adsb-logs/callsigns.db"
ExecStart=/usr/bin/python3 -m callsign_logger.monitor
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable callsign-monitor
sudo systemctl start callsign-monitor
```

## Step 11: Verify Everything is Running

```bash
# Check bot status
sudo systemctl status adsb-flight-bot
sudo systemctl status callsign-tracker-bot
sudo systemctl status callsign-monitor  # if installed

# View logs
sudo journalctl -u adsb-flight-bot -n 50
sudo journalctl -u callsign-tracker-bot -n 50

# Check health monitoring
tail -f /var/log/bot-health.log
```

## Step 12: Test Telegram Bots

Open Telegram and test your bots:

**Callsign Tracker Bot (@callsignloggerbot):**
- `/start`
- `/stats`
- `/callsigns`

**Flight Extraction Bot:**
- Send message to your bot
- `/start`
- `/status`

## Troubleshooting

### "No such file or directory" for ADSB logs

Your ADSB data location is different. Find it:
```bash
# Find where aircraft.json is written
sudo find /run /var/run /tmp -name "aircraft.json" 2>/dev/null

# Update service files with correct path
sudo nano /etc/systemd/system/callsign-monitor.service
# Change ADSB_LOG_DIR to your path

sudo systemctl daemon-reload
sudo systemctl restart callsign-monitor
```

### "Permission denied" for /opt/adsb-logs

```bash
sudo chown -R $USER:$USER /opt/adsb-logs
```

### "Database is locked"

Only one monitor can run at a time:
```bash
# Check for multiple monitors
ps aux | grep callsign_logger

# Kill old ones
killall python3
sudo systemctl restart callsign-monitor
```

### Bots not responding in Telegram

1. Check they're running:
   ```bash
   sudo systemctl status callsign-tracker-bot
   ```

2. Check logs for errors:
   ```bash
   sudo journalctl -u callsign-tracker-bot -n 100
   ```

3. Verify your user ID is correct in service files:
   ```bash
   sudo nano /etc/systemd/system/callsign-tracker-bot.service
   # Check TELEGRAM_ALLOWED_USERS line
   ```

### Import errors

```bash
# Install missing packages
pip3 install python-telegram-bot numpy pandas matplotlib plotly simplekml

# Or use system packages (faster on Pi)
sudo apt-get install python3-numpy python3-matplotlib python3-pandas
pip3 install python-telegram-bot plotly simplekml
```

## Configuration Files

### ADSB Data Path
Default: `/opt/adsb-logs/raw`

Your actual path might be:
- `/run/readsb/` (readsb)
- `/run/dump1090-fa/` (dump1090-fa)
- `/var/run/dump1090-mutability/` (dump1090-mutability)

### Database Path
Default: `/opt/adsb-logs/callsigns.db`

### Output Path
Default: `/opt/adsb-logs/analyses`

## Updating the Code

```bash
cd ~/adsb-logger
git pull

# Restart services to use new code
sudo systemctl restart adsb-flight-bot
sudo systemctl restart callsign-tracker-bot
sudo systemctl restart callsign-monitor  # if running
```

## Uninstalling

```bash
# Stop services
sudo systemctl stop adsb-flight-bot callsign-tracker-bot callsign-monitor
sudo systemctl disable adsb-flight-bot callsign-tracker-bot callsign-monitor

# Remove service files
sudo rm /etc/systemd/system/adsb-flight-bot.service
sudo rm /etc/systemd/system/callsign-tracker-bot.service
sudo rm /etc/systemd/system/callsign-monitor.service

# Remove cron job
crontab -e  # Delete health check line

# Remove data (optional)
sudo rm -rf /opt/adsb-logs

# Remove code (optional)
rm -rf ~/adsb-logger
```

## Summary - Quick Setup

```bash
# 1. Connect and install
ssh pi@your-pi-address
sudo apt-get update && sudo apt-get install -y python3-pip git
pip3 install python-telegram-bot numpy pandas matplotlib plotly simplekml

# 2. Clone repo
cd ~
git clone https://github.com/marcoculver/adsb-logger.git
cd adsb-logger

# 3. Create directories
sudo mkdir -p /opt/adsb-logs/raw /opt/adsb-logs/analyses
sudo chown -R $USER:$USER /opt/adsb-logs

# 4. Install bots
chmod +x setup_pi_bots.sh
sudo ./setup_pi_bots.sh

# 5. Test in Telegram
# Send /start to @callsignloggerbot
```

Done! Your bots are now running 24/7 on your Pi.
