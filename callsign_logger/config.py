"""Configuration for callsign logger."""
import os
import sys
from pathlib import Path

# API Configuration
FR24_API_TOKEN = os.environ.get(
    "FR24_API_TOKEN",
    "019b78ac-9271-7363-a509-d40935899ac5|VdqpeiWbwaeUlsowb4eOV2Utrm481SWbyNpvI1bYf0bb4efd"
)

# Database path
# Allow override via environment variable
if os.environ.get("CALLSIGN_DB_PATH"):
    DEFAULT_DB_PATH = Path(os.environ.get("CALLSIGN_DB_PATH"))
    DEFAULT_LOG_DIR = DEFAULT_DB_PATH.parent
elif sys.platform == "win32":
    DEFAULT_DB_PATH = Path(r"M:\Dropbox\ADSBPi-Base\callsigns.db")
    DEFAULT_LOG_DIR = Path(r"M:\Dropbox\ADSBPi-Base\raw")
else:
    DEFAULT_DB_PATH = Path("/opt/adsb-logs/callsigns.db")
    DEFAULT_LOG_DIR = Path("/opt/adsb-logs")

# Airlines to track
TRACKED_AIRLINES = {
    "emirates": {
        "callsign_prefixes": ["UAE"],
        "flight_prefix": "EK",
        "name": "Emirates",
    },
    "flydubai": {
        "callsign_prefixes": ["FDB"],
        "flight_prefix": "FZ",
        "name": "Flydubai",
    },
}

# All callsign prefixes to filter
ALL_CALLSIGN_PREFIXES = []
for airline in TRACKED_AIRLINES.values():
    ALL_CALLSIGN_PREFIXES.extend(airline["callsign_prefixes"])

# Monitoring settings
MONITOR_INTERVAL_SECONDS = 60  # How often to scan for new data
LOOKBACK_HOURS = 1  # How far back to look for new records

# API rate limiting
API_CACHE_HOURS = 24  # Cache route data for this long
API_REQUEST_DELAY = 1.0  # Seconds between API requests
