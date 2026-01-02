# ADS-B Logger Project - Complete Overview

## Table of Contents
1. [Project Purpose](#project-purpose)
2. [System Architecture](#system-architecture)
3. [SSH Access](#ssh-access)
4. [Core Components](#core-components)
5. [Running Services](#running-services)
6. [Systemd Timers](#systemd-timers)
7. [Docker Containers](#docker-containers)
8. [Telegram Bots](#telegram-bots)
9. [Health Monitoring](#health-monitoring)
10. [Directory Structure](#directory-structure)
11. [Database](#database)
12. [Configuration Files](#configuration-files)
13. [Troubleshooting](#troubleshooting)

---

## Project Purpose

This project provides comprehensive ADS-B (Automatic Dependent Surveillance-Broadcast) data logging and analysis for tracking aircraft. It consists of multiple integrated components:

- **High-fidelity ADS-B logging**: Captures complete aircraft state data at 1-second intervals
- **Callsign tracking**: Monitors specific airlines (Emirates, Flydubai) and enriches data with route information
- **Telegram bots**: Interactive interfaces for querying flight data
- **Health monitoring**: Automated system health checks with email and Telegram alerts
- **Data pipeline**: Automatic organization, compression, backup to Dropbox, and pruning

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Raspberry Pi (adsbpi-base)                    │
│                                                                          │
│  ┌────────────────┐     ┌──────────────────┐    ┌──────────────────┐  │
│  │ Docker         │     │ Python Services  │    │ Telegram Bots    │  │
│  │ Containers     │     │                  │    │                  │  │
│  │                │     │ adsb-logger      │    │ flight-bot       │  │
│  │ • ultrafeeder  │────▶│ callsign-monitor │◀───│ callsign-bot     │  │
│  │ • piaware      │     │ http-monitor     │    │                  │  │
│  │ • fr24feed     │     │                  │    │                  │  │
│  │ • skystats     │     └──────────────────┘    └──────────────────┘  │
│  └────────────────┘              │                                     │
│                                   ▼                                     │
│                         /opt/adsb-logs/                                 │
│                         ├── callsigns.db                                │
│                         ├── YYYY/MM/DD/*.jsonl.gz                       │
│                         └── adsb_state_*.jsonl (current)                │
│                                   │                                     │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │
                                    ▼
                          ┌─────────────────┐
                          │ Dropbox Backup  │
                          │ ADSBPi-Base/raw │
                          └─────────────────┘
```

---

## SSH Access

### Connection Details
- **Username**: `adsbpi-base`
- **Hostname**: `adsbpi-base`
- **SSH Command**: `ssh adsbpi-base@adsbpi-base`
- **SSH Key**: `~/.ssh/id_ed25519` (on local machine)

### Common SSH Commands
```bash
# Connect to Pi
ssh adsbpi-base@adsbpi-base

# Check service status
ssh adsbpi-base@adsbpi-base "systemctl status adsb-logger"

# View logs
ssh adsbpi-base@adsbpi-base "journalctl -u adsb-logger -f"

# Copy files to Pi
scp local-file.py adsbpi-base@adsbpi-base:/tmp/

# Run command as root
ssh adsbpi-base@adsbpi-base "sudo systemctl restart adsb-logger"
```

### SSH Key Setup
If SSH key needs to be re-added:
```bash
# On local machine, get public key
cat ~/.ssh/id_ed25519.pub

# On Pi, add to authorized_keys
mkdir -p ~/.ssh
echo "YOUR_PUBLIC_KEY" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

---

## Core Components

### 1. ADS-B Logger (`adsb_logger.py`)
**Purpose**: Continuously logs aircraft position data from readsb/tar1090

**Location**: `/opt/adsb-logger/adsb_logger.py`

**What it does**:
- Polls `http://127.0.0.1:8080/data/aircraft.json` every 1 second
- Extracts 40+ fields per aircraft (position, altitude, speed, heading, etc.)
- Writes to hourly JSONL files: `adsb_state_YYYY-MM-DD_HH.jsonl`
- Compresses completed hours to `.jsonl.gz`
- Runs continuously as a systemd service

**Output fields captured**:
- Position: `lat`, `lon`, `alt_baro`, `alt_geom`
- Speed: `gs`, `ias`, `tas`, `mach`
- Direction: `track`, `mag_heading`, `true_heading`
- Vertical: `baro_rate`, `geom_rate`
- Aircraft info: `hex`, `flight`, `t` (type), `r` (registration)
- Signal: `rssi`, `messages`, `seen`
- And more...

### 2. Callsign Monitor (`callsign_logger/monitor.py`)
**Purpose**: Tracks Emirates and Flydubai callsigns and enriches with route data

**Location**: `/opt/adsb-logger/callsign_logger/`

**What it does**:
- Scans ADS-B log files for UAE*/FDB* callsigns
- Stores callsigns in SQLite database (`callsigns.db`)
- Queries FlightRadar24 API for route information
- Tracks first seen, last seen, and sighting frequency
- Used for schedule pattern analysis

**Tracked airlines**:
- **Emirates**: Callsign prefix `UAE`, Flight prefix `EK`
- **Flydubai**: Callsign prefix `FDB`, Flight prefix `FZ`

### 3. HTTP Monitor (`callsign_logger/http_monitor.py`)
**Purpose**: Alternative real-time monitoring via HTTP endpoint

**What it does**:
- Connects to readsb HTTP stream at `http://127.0.0.1:8080/data/aircraft.json`
- Monitors for specific callsigns in real-time
- Updates database continuously without file scanning

### 4. Flight Extractor (`flight_extractor/`)
**Purpose**: Extract complete flight tracks from log files

**What it does**:
- Searches historical JSONL files for specific aircraft (by hex, callsign, or flight number)
- Extracts all data points for a flight
- Generates visualizations (altitude charts, speed charts, track maps)
- Exports to CSV and KML formats

**Key files**:
- `file_scanner.py`: Searches through compressed log files
- `extractor.py`: Extracts flight data
- `flight_charts/`: Visualization modules
- `flight_export/`: CSV and KML exporters

---

## Running Services

All services are managed by systemd. Check status with:
```bash
systemctl status SERVICE_NAME
```

### 1. `adsb-logger.service`
**Description**: ADS-B aircraft.json segmented logger (hourly JSONL -> JSONL.GZ)

**Command**:
```bash
/usr/bin/python3 /opt/adsb-logger/adsb_logger.py \
  --outdir /opt/adsb-logs \
  --url http://127.0.0.1:8080/data/aircraft.json \
  --tick 1.0 \
  --fsync-every 1.0
```

**User**: `adsbpi-base`
**Status**: Should always be running
**Logs**: `journalctl -u adsb-logger -f`

### 2. `adsb-callsign-monitor.service`
**Description**: ADSB Callsign Monitor for Emirates and Flydubai

**Command**: `/usr/bin/python3 -m callsign_logger.monitor`

**User**: `root`
**Working Directory**: `/root/adsb-logger`
**Status**: Should always be running
**Logs**: `journalctl -u adsb-callsign-monitor -f`

### 3. `callsign-monitor.service`
**Description**: Emirates/Flydubai Callsign Monitor (HTTP)

**Command**: `/usr/bin/python3 -m callsign_logger.http_monitor`

**User**: `root`
**Working Directory**: `/root/adsb-logger`
**Status**: Should always be running
**Logs**: `journalctl -u callsign-monitor -f`

### 4. `adsb-flight-bot.service`
**Description**: ADSB Flight Extraction Telegram Bot

**Command**: `/usr/bin/python3 -m telegram_bot.flight_bot`

**User**: `root`
**Environment**:
- `TELEGRAM_BOT_TOKEN=8380442252:AAHhJd8vHDGEDHZK0-F7k7LY3fwmnINqGbw`
- `TELEGRAM_ALLOWED_USERS=1269568755`
- `LOG_DIR=/opt/adsb-logs`

**Status**: Should always be running
**Logs**: `journalctl -u adsb-flight-bot -f`

### 5. `callsign-tracker-bot.service`
**Description**: Emirates/Flydubai Callsign Tracker Telegram Bot

**Command**: `/usr/bin/python3 -m telegram_bot.callsign_bot`

**User**: `root`
**Environment**:
- `TELEGRAM_BOT_TOKEN=8380442252:AAHhJd8vHDGEDHZK0-F7k7LY3fwmnINqGbw`
- `TELEGRAM_ALLOWED_USERS=1269568755`
- `CALLSIGN_DB_PATH=/opt/adsb-logs/callsigns.db`

**Status**: Should always be running
**Logs**: `journalctl -u callsign-tracker-bot -f`

---

## Systemd Timers

Timers run periodic tasks. Check status with:
```bash
systemctl list-timers | grep adsb
```

### 1. `adsb-health-check.timer`
**Frequency**: Every 5 minutes
**Service**: `adsb-health-check.service`
**Script**: `/usr/local/bin/adsb-health-check.sh`

**What it does**:
- Checks all 5 services are running
- Checks all 4 timers are active
- Checks all 5 Docker containers are running
- Verifies log file is being updated (< 5 min old)
- Checks for excessive fetch errors
- Monitors disk space (alerts at >90%)
- **Sends alerts**: Email + Telegram when issues detected

**Start/Stop**:
```bash
sudo systemctl start adsb-health-check.timer
sudo systemctl stop adsb-health-check.timer
```

### 2. `adsb-status-report.timer`
**Frequency**: Every 12 hours
**Service**: `adsb-status-report.service`
**Script**: `/usr/local/bin/adsb-status-report.sh`

**What it does**:
- Generates comprehensive system health report
- Lists status of all services, timers, containers
- Shows system stats (disk, memory, uptime, load)
- **Sends report via Telegram** every 12 hours

**Next run**: Check with `systemctl status adsb-status-report.timer`

### 3. `adsb-pipeline.timer`
**Frequency**: Hourly at :05 past the hour
**Service**: `adsb-pipeline.service`
**Script**: `/usr/local/bin/adsb-pipeline.sh`

**What it does**:
1. **Organize**: Moves `.jsonl.gz` files into `YYYY/MM/DD/` structure
2. **Sync**: Uploads to Dropbox via rclone
3. **Verify**: Checks files exist in Dropbox
4. **Prune**: Deletes local files older than 180 days (only if in Dropbox)
5. **Clean**: Removes empty directories

**Manual run**:
```bash
sudo /usr/local/bin/adsb-pipeline.sh
```

### 4. `adsb-dropbox-sync.timer`
**Frequency**: Every 10 minutes
**Service**: `adsb-dropbox-sync.service`
**Script**: `/usr/local/bin/adsb-dropbox-sync.sh`

**What it does**:
- Syncs `.jsonl.gz` files to Dropbox
- Uses rclone with 4 transfers, 8 checkers
- Destination: `dropbox:ADSBPi-Base/raw`

### 5. `adsb-log-organize.timer`
**Frequency**: Every 2 minutes
**Service**: `adsb-log-organize.service`
**Script**: `/usr/local/bin/adsb-log-organize.sh`

**What it does**:
- Moves completed `.jsonl.gz` files from `/opt/adsb-logs/` root
- Organizes into `YYYY/MM/DD/` directory structure
- Only moves closed/compressed files (never touches active `.jsonl`)

---

## Docker Containers

All containers run ADS-B feeder software. Check with:
```bash
docker ps
```

### 1. `ultrafeeder`
**Purpose**: Multi-protocol ADS-B aggregator and feeder

**What it does**:
- Receives ADS-B data from SDR
- Serves tar1090 web interface at `http://localhost:8080`
- Provides `aircraft.json` endpoint for logger
- Feeds data to multiple aggregators

### 2. `piaware`
**Purpose**: FlightAware feeder

**What it does**:
- Receives data from ultrafeeder
- Feeds to FlightAware network
- Provides statistics and feeder ID

### 3. `fr24feed`
**Purpose**: FlightRadar24 feeder

**What it does**:
- Receives data from ultrafeeder
- Feeds to FlightRadar24 network
- Tracks sharing statistics

### 4. `skystats`
**Purpose**: Statistics collection and visualization

**What it does**:
- Collects ADS-B statistics
- Generates graphs and reports
- Stores data in skystats-db

### 5. `skystats-db`
**Purpose**: PostgreSQL database for skystats

**What it does**:
- Stores historical statistics
- Provides data for skystats web interface

---

## Telegram Bots

The project uses three separate Telegram bots for different purposes.

### Bot Configuration

#### 1. Health Monitoring Bot
- **Bot Token**: `8279120117:AAGy7o3LdvTgB8jUTtluYbw_kxuBD_AFx9o`
- **Allowed User ID**: `1269568755`
- **Purpose**: System health alerts and status reports
- **Used by**: Health check and status report scripts

#### 2. Flight & Callsign Bots
- **Bot Token**: `8380442252:AAHhJd8vHDGEDHZK0-F7k7LY3fwmnINqGbw`
- **Allowed User ID**: `1269568755`
- **Purpose**: Flight tracking and callsign queries
- **Used by**: Flight bot and Callsign tracker bot services

### 1. Flight Extraction Bot
**Service**: `adsb-flight-bot.service`

**Commands**:
- `/start` - Welcome message and help
- `/hex A1B2C3` - Search by ICAO hex address
- `/callsign UAE123` - Search by callsign
- `/flight EK525` - Search by flight number
- `/recent` - Show recent flights

**What it does**:
- Searches historical log files for flights
- Extracts complete flight track data
- Generates visualizations (altitude, speed, track map)
- Sends charts and data to Telegram

### 2. Callsign Tracker Bot
**Service**: `callsign-tracker-bot.service`

**Commands**:
- `/start` - Welcome and help
- `/search UAE123` - Search for callsign in database
- `/recent` - Show recently seen callsigns
- `/stats` - Database statistics
- `/schedule FZ` - Show Flydubai schedule pattern

**What it does**:
- Queries callsigns database
- Shows route information from FR24 API
- Displays sighting frequency and patterns
- Provides schedule analysis

---

## Health Monitoring

### Alert System
The health monitoring system provides two types of notifications:

#### 1. Immediate Alerts (Every 5 minutes)
**Sent when**:
- Any service stops running
- Any timer becomes inactive
- Any Docker container stops
- Log file not updated in 5+ minutes
- More than 10 fetch errors in 5 minutes
- Disk usage exceeds 90%

**Delivery**:
- **Email**: marcoculver@gmail.com (via msmtp)
- **Telegram**: Sent to chat ID 1269568755

**Alert format**:
- Subject line includes hostname and issue
- Body includes status, logs, and fix commands
- Telegram message includes emoji indicators

#### 2. Status Report (Every 12 hours)
**Contains**:
- All services status (5 services)
- All timers status (4 timers)
- All containers status (5 containers)
- System stats (disk, memory, uptime, load)
- Count of recent log files (24h)
- Database size

**Delivery**: Telegram only

**Format**: Comprehensive table with emoji indicators:
- ✅ = Running/OK
- ❌ = Down/Failed
- ⏱️ = Inactive timer
- 🐳 = Container issue

### Health Check Scripts

#### `/usr/local/bin/adsb-health-check.sh`
- Runs every 5 minutes via timer
- Checks all services, timers, containers
- Sends alerts only when issues first detected
- Uses state file to prevent alert spam: `/var/run/adsb-health-state`
- Clears alerts when issues resolved

#### `/usr/local/bin/adsb-status-report.sh`
- Runs every 12 hours via timer
- Always sends report (not just on issues)
- Provides comprehensive system overview
- Includes uptime and performance metrics

### Manual Health Check
```bash
# Run health check manually
sudo /usr/local/bin/adsb-health-check.sh

# Send status report manually
sudo /usr/local/bin/adsb-status-report.sh

# View health check logs
journalctl -u adsb-health-check -n 50

# Check alert state file
sudo cat /var/run/adsb-health-state
```

---

## Directory Structure

### On Raspberry Pi

```
/opt/adsb-logger/
├── adsb_logger.py              # Main logger script
├── callsign_logger/            # Callsign tracking module
│   ├── __init__.py
│   ├── config.py               # Configuration
│   ├── database.py             # SQLite database interface
│   ├── monitor.py              # File-based monitor
│   ├── http_monitor.py         # HTTP stream monitor
│   ├── fr24_api.py             # FlightRadar24 API client
│   └── backfill_routes.py      # Backfill missing routes
├── telegram_bot/               # Telegram bot modules
│   ├── __init__.py
│   ├── flight_bot.py           # Flight extraction bot
│   └── callsign_bot.py         # Callsign tracker bot
├── flight_extractor/           # Flight extraction
│   ├── file_scanner.py
│   ├── extractor.py
│   └── ...
├── flight_charts/              # Visualization modules
│   ├── altitude_chart.py
│   ├── speed_chart.py
│   ├── track_map.py
│   └── ...
└── run_monitor.py              # Monitor launcher

/opt/adsb-logs/
├── callsigns.db                # SQLite database
├── adsb_state_YYYY-MM-DD_HH.jsonl      # Current hour (active)
└── YYYY/                       # Organized by date
    └── MM/
        └── DD/
            ├── adsb_state_YYYY-MM-DD_HH.jsonl.gz
            └── ...

/usr/local/bin/
├── adsb-health-check.sh        # Health monitoring script
├── adsb-status-report.sh       # Status report script
├── adsb-pipeline.sh            # Data pipeline script
├── adsb-dropbox-sync.sh        # Dropbox sync script
└── adsb-log-organize.sh        # Log organization script

/etc/systemd/system/
├── adsb-logger.service
├── adsb-callsign-monitor.service
├── adsb-flight-bot.service
├── callsign-monitor.service
├── callsign-tracker-bot.service
├── adsb-health-check.service
├── adsb-health-check.timer
├── adsb-status-report.service
├── adsb-status-report.timer
├── adsb-pipeline.service
├── adsb-pipeline.timer
├── adsb-dropbox-sync.service
├── adsb-dropbox-sync.timer
├── adsb-log-organize.service
└── adsb-log-organize.timer
```

### Dropbox Structure
```
Dropbox/ADSBPi-Base/
└── raw/
    └── YYYY/
        └── MM/
            └── DD/
                ├── adsb_state_YYYY-MM-DD_HH.jsonl.gz
                └── ...
```

---

## Database

### Location
- **Pi**: `/opt/adsb-logs/callsigns.db`
- **Dropbox**: `Dropbox/ADSBPi-Base/callsigns.db`

### Schema

#### `callsigns` table
```sql
CREATE TABLE callsigns (
    callsign TEXT PRIMARY KEY,
    flight_number TEXT,
    airline TEXT,
    origin TEXT,
    destination TEXT,
    aircraft_type TEXT,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    sighting_count INTEGER,
    route_updated TIMESTAMP
);
```

**Fields**:
- `callsign`: ADS-B callsign (e.g., UAE123, FDB456)
- `flight_number`: Commercial flight number (e.g., EK525, FZ789)
- `airline`: emirates or flydubai
- `origin`: IATA code of departure airport
- `destination`: IATA code of arrival airport
- `aircraft_type`: ICAO aircraft type code
- `first_seen`: First time callsign was observed
- `last_seen`: Most recent sighting
- `sighting_count`: Number of times seen
- `route_updated`: Last time route data was fetched from API

### Accessing Database
```bash
# On Pi
sqlite3 /opt/adsb-logs/callsigns.db

# View all callsigns
SELECT * FROM callsigns ORDER BY last_seen DESC LIMIT 10;

# Count by airline
SELECT airline, COUNT(*) FROM callsigns GROUP BY airline;

# Find specific callsign
SELECT * FROM callsigns WHERE callsign = 'UAE123';
```

---

## Configuration Files

### Environment Variables (Set in systemd services)
```bash
# Telegram Bot Configuration (Flight & Callsign Bots)
TELEGRAM_BOT_TOKEN=8380442252:AAHhJd8vHDGEDHZK0-F7k7LY3fwmnINqGbw
TELEGRAM_ALLOWED_USERS=1269568755

# Health Monitoring Bot (in health check scripts)
TELEGRAM_BOT_TOKEN=8279120117:AAGy7o3LdvTgB8jUTtluYbw_kxuBD_AFx9o

# Paths
LOG_DIR=/opt/adsb-logs
CALLSIGN_DB_PATH=/opt/adsb-logs/callsigns.db
```

### FlightRadar24 API Token
Located in: `callsign_logger/config.py`
```python
FR24_API_TOKEN = "019b78ac-9271-7363-a509-d40935899ac5|VdqpeiWbwaeUlsowb4eOV2Utrm481SWbyNpvI1bYf0bb4efd"
```

### Email Configuration
Located in: `/etc/msmtprc` (on Pi)
```ini
defaults
auth           on
tls            on
tls_trust_file /etc/ssl/certs/ca-certificates.crt
logfile        /var/log/msmtp.log

account        gmail
host           smtp.gmail.com
port           587
from           marcoculver@gmail.com
user           marcoculver@gmail.com
password       YOUR_APP_PASSWORD

account default : gmail
```

### Rclone Configuration
Located in: `~/.config/rclone/rclone.conf` (on Pi)
```ini
[dropbox]
type = dropbox
token = YOUR_DROPBOX_TOKEN
```

---

## Troubleshooting

### Service Not Running

**Check status**:
```bash
systemctl status SERVICE_NAME
```

**View logs**:
```bash
journalctl -u SERVICE_NAME -n 50
journalctl -u SERVICE_NAME -f  # Follow live
```

**Restart service**:
```bash
sudo systemctl restart SERVICE_NAME
```

### Logger Not Writing

**Possible causes**:
1. Ultrafeeder container not running
2. Permission issues on `/opt/adsb-logs`
3. Disk full

**Check**:
```bash
# Is ultrafeeder running?
docker ps | grep ultrafeeder

# Can we reach the endpoint?
curl http://127.0.0.1:8080/data/aircraft.json | head

# Check permissions
ls -la /opt/adsb-logs

# Check disk space
df -h /opt/adsb-logs
```

**Fix**:
```bash
# Restart ultrafeeder
docker restart ultrafeeder

# Fix permissions
sudo chown -R adsbpi-base:adsbpi-base /opt/adsb-logs

# Restart logger
sudo systemctl restart adsb-logger
```

### Files Not Syncing to Dropbox

**Check**:
```bash
# Test rclone
rclone listremotes
rclone lsd dropbox:

# Check sync timer
systemctl status adsb-dropbox-sync.timer

# View sync logs
journalctl -u adsb-dropbox-sync -n 50
```

**Fix**:
```bash
# Reconfigure rclone
rclone config

# Restart sync timer
sudo systemctl restart adsb-dropbox-sync.timer
```

### Telegram Bot Not Responding

**Check**:
```bash
# Is bot service running?
systemctl status adsb-flight-bot
systemctl status callsign-tracker-bot

# View bot logs
journalctl -u adsb-flight-bot -f
journalctl -u callsign-tracker-bot -f
```

**Test bot manually**:
```bash
# On Pi
cd /opt/adsb-logger
python3 -m telegram_bot.flight_bot
```

**Common issues**:
- Invalid bot token
- Wrong user ID
- Python dependencies missing

### Callsign Database Empty

**Check**:
```bash
# Database exists and has data?
sqlite3 /opt/adsb-logs/callsigns.db "SELECT COUNT(*) FROM callsigns;"

# Monitor service running?
systemctl status adsb-callsign-monitor
```

**Fix**:
```bash
# Restart monitor
sudo systemctl restart adsb-callsign-monitor

# Check logs for errors
journalctl -u adsb-callsign-monitor -n 100
```

### Health Alerts Not Sending

**Check email**:
```bash
# Test msmtp
echo "Test" | msmtp marcoculver@gmail.com

# Check msmtp logs
sudo tail /var/log/msmtp.log
```

**Check Telegram**:
```bash
# Test Telegram API
curl -X POST "https://api.telegram.org/bot8380442252:AAHhJd8vHDGEDHZK0-F7k7LY3fwmnINqGbw/sendMessage" \
  -d "chat_id=1269568755" \
  -d "text=Test message"
```

### High Disk Usage

**Check what's using space**:
```bash
# Overall usage
df -h /opt/adsb-logs

# Largest directories
du -sh /opt/adsb-logs/*/ | sort -rh | head -10

# Count files
find /opt/adsb-logs -name "*.jsonl.gz" | wc -l
```

**Fix**:
```bash
# Run pipeline manually (prunes files >180 days)
sudo /usr/local/bin/adsb-pipeline.sh

# Or manually delete old files (after verifying in Dropbox!)
find /opt/adsb-logs -name "*.jsonl.gz" -mtime +180 -delete
```

### Permission Denied Errors

**Common cause**: Service trying to write to directory it doesn't own

**Fix**:
```bash
# Make sure adsb-logger owns logs directory
sudo chown -R adsbpi-base:adsbpi-base /opt/adsb-logs

# Make sure scripts are executable
sudo chmod +x /usr/local/bin/adsb-*.sh

# Restart affected service
sudo systemctl restart SERVICE_NAME
```

---

## Quick Reference Commands

### Service Management
```bash
# View all adsb services
systemctl list-units | grep adsb

# View all timers
systemctl list-timers | grep adsb

# Restart everything
sudo systemctl restart adsb-logger
sudo systemctl restart adsb-callsign-monitor
sudo systemctl restart callsign-monitor
sudo systemctl restart adsb-flight-bot
sudo systemctl restart callsign-tracker-bot
sudo systemctl restart adsb-health-check.timer
sudo systemctl restart adsb-status-report.timer
```

### Monitoring
```bash
# Watch logs in real-time
journalctl -u adsb-logger -f

# Check recent errors
journalctl -u adsb-logger -p err -n 50

# View all adsb-related logs
journalctl -t adsb-health -n 100
```

### Health Check
```bash
# Manual health check
sudo /usr/local/bin/adsb-health-check.sh

# Send status report
sudo /usr/local/bin/adsb-status-report.sh

# View current health state
sudo cat /var/run/adsb-health-state
```

### Docker
```bash
# View all containers
docker ps

# View logs
docker logs ultrafeeder --tail 50
docker logs piaware --tail 50

# Restart container
docker restart ultrafeeder
```

### Database Queries
```bash
# Open database
sqlite3 /opt/adsb-logs/callsigns.db

# Recent callsigns
SELECT callsign, flight_number, origin, destination, last_seen
FROM callsigns
ORDER BY last_seen DESC
LIMIT 20;

# Count by airline
SELECT airline, COUNT(*) as count
FROM callsigns
GROUP BY airline;
```

---

## Support Contacts

- **Pi Hostname**: adsbpi-base
- **SSH User**: adsbpi-base
- **Email Alerts**: marcoculver@gmail.com
- **Telegram User ID**: 1269568755
- **Project Location**: `/opt/adsb-logger/`
- **Log Location**: `/opt/adsb-logs/`
- **Dropbox**: `Dropbox/ADSBPi-Base/raw/`

---

*Last Updated: 2026-01-02*
