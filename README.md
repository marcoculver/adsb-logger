# ADSB Logger

High-fidelity ADS-B state logger for tar1090/readsb aircraft.json data.

## Features

- Polls aircraft.json at 1 second intervals
- Hourly log rotation with gzip compression
- Consolidated pipeline for organizing, syncing, and pruning
- 180-day local retention with Dropbox backup verification before deletion
- Health monitoring with email alerts
- Systemd service with security hardening

## Architecture

```
┌─────────────────┐     ┌─────────────────────────────────────────────┐
│  adsb-logger    │     │  adsb-pipeline.sh (hourly at :05)           │
│  (continuous)   │     │                                             │
│                 │     │  1. Organize files into YYYY/MM/DD          │
│  Polls every 1s │     │  2. Sync to Dropbox                         │
│  Compresses     │────▶│  3. Verify files exist in Dropbox           │
│  hourly at :00  │     │  4. Prune files older than 180 days         │
│                 │     │  5. Clean empty directories                 │
└─────────────────┘     └─────────────────────────────────────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
               /opt/adsb-logs/                    dropbox:ADSBPi-Base/raw/
               └── 2025/                          └── 2025/
                   └── 12/                            └── 12/
                       └── 31/                            └── 31/
                           └── adsb_state_*.jsonl.gz          └── adsb_state_*.jsonl.gz
```

## Output Format

Each line is a JSON object:
```json
{
  "_ts": 1735689600,
  "_ts_iso": "2025-12-31T12:00:00Z",
  "_poll": 12345,
  "hex": "a1b2c3",
  "flight": "UAL123",
  "lat": 37.7749,
  "lon": -122.4194,
  "alt_baro": 35000,
  "gs": 450,
  ...
}
```

## Installation

### 1. Copy files to the Pi

```bash
# Copy main script
sudo mkdir -p /opt/adsb-logger
sudo cp adsb_logger.py /opt/adsb-logger/
sudo chown -R adsbpi-base:adsbpi-base /opt/adsb-logger

# Copy helper scripts
sudo cp scripts/adsb-pipeline.sh /usr/local/bin/
sudo cp scripts/adsb-health-check.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/adsb-*.sh

# Copy systemd files
sudo cp systemd/adsb-logger.service /etc/systemd/system/
sudo cp systemd/adsb-pipeline.service /etc/systemd/system/
sudo cp systemd/adsb-pipeline.timer /etc/systemd/system/
sudo cp systemd/adsb-health-check.service /etc/systemd/system/
sudo cp systemd/adsb-health-check.timer /etc/systemd/system/
```

### 2. Disable old timers (if upgrading)

```bash
sudo systemctl disable --now adsb-log-organize.timer 2>/dev/null || true
sudo systemctl disable --now adsb-dropbox-sync.timer 2>/dev/null || true
```

### 3. Enable and start services

```bash
sudo systemctl daemon-reload

# Main logger
sudo systemctl enable --now adsb-logger

# Hourly pipeline (organize, sync, prune)
sudo systemctl enable --now adsb-pipeline.timer

# Health monitoring (every 5 minutes)
sudo systemctl enable --now adsb-health-check.timer
```

### 4. Verify

```bash
# Check services
sudo systemctl status adsb-logger
sudo systemctl list-timers | grep adsb

# View logs
journalctl -u adsb-logger -f
journalctl -u adsb-pipeline -f
```

## Email Alerts Setup

The health check can send email alerts. You need to configure msmtp:

### 1. Install msmtp

```bash
sudo apt install msmtp msmtp-mta
```

### 2. Configure msmtp

Create `/etc/msmtprc`:

```ini
# Gmail example
defaults
auth           on
tls            on
tls_trust_file /etc/ssl/certs/ca-certificates.crt
logfile        /var/log/msmtp.log

account        gmail
host           smtp.gmail.com
port           587
from           your-email@gmail.com
user           your-email@gmail.com
password       your-app-password

account default : gmail
```

**Note:** For Gmail, you need an [App Password](https://myaccount.google.com/apppasswords), not your regular password.

### 3. Secure the config

```bash
sudo chmod 600 /etc/msmtprc
```

### 4. Test email

```bash
echo "Test email from $(hostname)" | mail -s "Test" your-email@gmail.com
```

## Configuration

### Logger (adsb_logger.py)

| Argument | Default | Description |
|----------|---------|-------------|
| `--url` | `http://127.0.0.1:8080/data/aircraft.json` | tar1090/readsb endpoint |
| `--outdir` | `/opt/adsb-logs` | Output directory |
| `--tick` | `1.0` | Poll interval (seconds) |
| `--timeout` | `2.0` | HTTP timeout (seconds) |
| `--fsync-every` | `1.0` | Fsync interval (seconds) |
| `--quiet` | off | Reduce logging verbosity |

### Pipeline (adsb-pipeline.sh)

Edit the script to change:
- `KEEP_DAYS=180` - Days to keep on local disk
- `DROPBOX_REMOTE` - Dropbox destination path

## Monitoring

### View live logs

```bash
# Logger output
journalctl -u adsb-logger -f

# Pipeline runs
journalctl -u adsb-pipeline -f

# Health checks
journalctl -u adsb-health-check -f
```

### Check status

```bash
# Service status
systemctl status adsb-logger

# Timer status
systemctl list-timers | grep adsb

# Disk usage
du -sh /opt/adsb-logs/
```

### Manual pipeline run

```bash
sudo /usr/local/bin/adsb-pipeline.sh
```

## Troubleshooting

### Logger not writing

1. Check if ultrafeeder is running: `docker ps | grep ultrafeeder`
2. Test the endpoint: `curl http://127.0.0.1:8080/data/aircraft.json | head`
3. Check logger logs: `journalctl -u adsb-logger -n 50`

### Files not syncing to Dropbox

1. Check rclone config: `rclone listremotes`
2. Test Dropbox connection: `rclone lsd dropbox:`
3. Check pipeline logs: `journalctl -u adsb-pipeline -n 50`

### Files not being pruned

1. Verify files exist in Dropbox first (safety check)
2. Run pipeline manually to see output: `sudo /usr/local/bin/adsb-pipeline.sh`
3. Check if files are older than 180 days: `find /opt/adsb-logs -name "*.jsonl.gz" -mtime +180`

## Data Fields

The logger captures these fields from aircraft.json:

| Field | Description |
|-------|-------------|
| `hex` | ICAO 24-bit address |
| `flight` | Callsign |
| `lat`, `lon` | Position |
| `alt_baro`, `alt_geom` | Altitude (barometric/geometric) |
| `gs`, `ias`, `tas`, `mach` | Speed |
| `track`, `mag_heading`, `true_heading` | Direction |
| `baro_rate`, `geom_rate` | Vertical rate |
| `squawk` | Transponder code |
| `t` | Aircraft type (e.g., B738) |
| `r` | Registration |
| `rssi` | Signal strength |
| ... | And more |

## License

MIT
