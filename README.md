# ADSB Logger

High-fidelity ADS-B state logger for tar1090/readsb aircraft.json data.

## Features

- Polls aircraft.json at configurable intervals (default 1 second)
- Logs all aircraft with full field preservation
- Hourly log rotation with gzip compression
- Automatic retention management (default 30 days)
- Atomic file operations to prevent corruption
- Systemd service with security hardening

## Output Format

- **Active hour**: `/opt/adsb-logs/adsb_state_YYYY-MM-DD_HH.jsonl` (plain text, always readable)
- **Finalized hours**: `/opt/adsb-logs/adsb_state_YYYY-MM-DD_HH.jsonl.gz` (compressed)

Each line is a JSON object containing:
- `_ts`: Unix timestamp
- `_ts_iso`: ISO 8601 timestamp
- `_poll`: Poll sequence number
- Aircraft fields (hex, flight, lat, lon, altitude, speed, etc.)
- `_raw`: Complete original record from aircraft.json

## Installation

### 1. Copy files to the Pi

```bash
# Copy main script
sudo mkdir -p /opt/adsb-logger
sudo cp adsb_logger.py /opt/adsb-logger/
sudo chown -R adsbpi-base:adsbpi-base /opt/adsb-logger

# Copy helper scripts
sudo cp scripts/adsb-log-organize.sh /usr/local/bin/
sudo cp scripts/adsb-dropbox-sync.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/adsb-*.sh

# Copy systemd service
sudo cp systemd/adsb-logger.service /etc/systemd/system/
sudo mkdir -p /etc/systemd/system/adsb-logger.service.d
sudo cp systemd/adsb-logger.service.d/override.conf /etc/systemd/system/adsb-logger.service.d/
```

### 2. Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable adsb-logger
sudo systemctl start adsb-logger
```

### 3. Check status

```bash
sudo systemctl status adsb-logger
journalctl -u adsb-logger -f
```

## Configuration

Command-line arguments (modify in the systemd service file):

| Argument | Default | Description |
|----------|---------|-------------|
| `--url` | `http://127.0.0.1:8080/data/aircraft.json` | tar1090/readsb endpoint |
| `--outdir` | `/opt/adsb-logs` | Output directory |
| `--tick` | `1.0` | Poll interval (seconds) |
| `--keep-days` | `30` | Retention period (days) |
| `--timeout` | `2.0` | HTTP timeout (seconds) |
| `--fsync-every` | `1.0` | Fsync interval (seconds) |
| `--prune-every` | `3600` | Prune check interval (seconds) |

## Helper Scripts

### adsb-log-organize.sh

Organizes completed log files into a date-based directory structure:
```
/opt/adsb-logs/2025/12/30/adsb_state_2025-12-30_05.jsonl.gz
```

### adsb-dropbox-sync.sh

Syncs compressed log files to Dropbox using rclone. Requires rclone to be configured with a `dropbox:` remote.

## Requirements

- Python 3.10+
- tar1090 or readsb running with aircraft.json endpoint
- systemd (for service management)
- rclone (optional, for Dropbox sync)

## License

MIT
