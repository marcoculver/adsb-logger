#!/usr/bin/env python3
"""Scan historical ADSB logs to populate callsign database."""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from callsign_logger.monitor import CallsignMonitor
from callsign_logger.database import CallsignDatabase

# Use Dropbox paths
db = CallsignDatabase(db_path=Path("/mnt/m/Dropbox/ADSBPi-Base/callsigns.db"))
monitor = CallsignMonitor(
    db=db,
    log_dir=Path("/mnt/m/Dropbox/ADSBPi-Base/raw"),
    skip_api=False  # Enable API lookups
)

# Scan last 7 days
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

print(f"Scanning logs from {start_date.date()} to {end_date.date()}")
print("This will take several minutes...\n")

monitor.scan_historical(start_date, end_date)

print("\nDone! Run the export script to generate updated CSV.")
