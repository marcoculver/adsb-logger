"""Background monitoring service for callsign tracking."""
import gzip
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Set, Dict, Any

from .config import (
    DEFAULT_LOG_DIR,
    ALL_CALLSIGN_PREFIXES,
    TRACKED_AIRLINES,
    MONITOR_INTERVAL_SECONDS,
    LOOKBACK_HOURS,
    API_CACHE_HOURS,
)
from .database import CallsignDatabase
from .fr24_api import FlightRadar24API, convert_callsign_to_flight_number

log = logging.getLogger(__name__)


class CallsignMonitor:
    """
    Background service that monitors ADS-B logs for Emirates and Flydubai callsigns.

    Continuously scans log files and updates the database with:
    - New callsigns
    - Flight numbers and routes (via FR24 API)
    - Sighting frequency for schedule analysis
    """

    def __init__(
        self,
        db: Optional[CallsignDatabase] = None,
        api: Optional[FlightRadar24API] = None,
        log_dir: Optional[Path] = None,
        skip_api: bool = False
    ):
        self.db = db or CallsignDatabase()
        self.api = api or FlightRadar24API()
        self.log_dir = log_dir or DEFAULT_LOG_DIR
        self.skip_api = skip_api  # Skip API lookups (for historical scans)
        self.running = False
        self.last_processed_file = None
        self.last_processed_line = 0

        # Track callsigns seen in current session to avoid duplicate API calls
        self.session_seen: Set[str] = set()

    def get_airline_for_callsign(self, callsign: str) -> Optional[str]:
        """Determine which airline a callsign belongs to."""
        callsign = callsign.strip().upper()
        for airline_key, config in TRACKED_AIRLINES.items():
            for prefix in config["callsign_prefixes"]:
                if callsign.startswith(prefix):
                    return config["name"]
        return None

    def is_tracked_callsign(self, callsign: str) -> bool:
        """Check if a callsign should be tracked."""
        if not callsign:
            return False
        callsign = callsign.strip().upper()
        return any(callsign.startswith(prefix) for prefix in ALL_CALLSIGN_PREFIXES)

    def process_record(self, record: Dict[str, Any]) -> bool:
        """
        Process a single ADS-B record.

        Returns True if this was a tracked callsign.
        """
        callsign = (record.get("flight") or "").strip().upper()

        if not self.is_tracked_callsign(callsign):
            return False

        airline = self.get_airline_for_callsign(callsign)
        if not airline:
            return False

        # Extract record data
        hex_code = record.get("hex")
        aircraft_type = record.get("t")  # ICAO type
        registration = record.get("r")
        ts = record.get("_ts")

        seen_at = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)

        # Check if we need to look up route info
        flight_number = None
        route = None
        origin = None
        destination = None

        # Check cache first
        cached = self.db.get_cached_route(callsign)
        if cached:
            flight_number = cached.get("flight_number")
            route = cached.get("route")
            origin = cached.get("origin")
            destination = cached.get("destination")
        elif callsign not in self.session_seen:
            # Try API lookup for new callsigns
            self.session_seen.add(callsign)

            # Only try API if enabled and available
            if not self.skip_api and self.api._api_available is not False:
                try:
                    route_data = self.api.lookup_route(callsign)
                    if route_data:
                        flight_number = route_data.get("flight_number")
                        route = route_data.get("route")
                        origin = route_data.get("origin")
                        destination = route_data.get("destination")

                        # Also get aircraft info if not in record
                        if not aircraft_type:
                            aircraft_type = route_data.get("aircraft_type")
                        if not registration:
                            registration = route_data.get("registration")

                        # Cache the result
                        self.db.cache_route(callsign, flight_number, route, origin, destination)
                        log.info(f"Looked up route for {callsign}: {route}")
                except Exception as e:
                    log.debug(f"Failed to lookup route for {callsign}: {e}")

        # If no API data, try heuristic conversion
        if not flight_number:
            flight_number = convert_callsign_to_flight_number(callsign)

        # Update database
        is_new = self.db.upsert_callsign(
            callsign=callsign,
            airline=airline,
            hex_code=hex_code,
            aircraft_type=aircraft_type,
            registration=registration,
            flight_number=flight_number,
            route=route,
            origin=origin,
            destination=destination,
        )

        # Add sighting for schedule tracking
        self.db.add_sighting(callsign, seen_at, hex_code)

        return True

    def scan_file(self, file_path: Path, start_line: int = 0) -> int:
        """
        Scan a log file for tracked callsigns.

        Returns the number of lines processed.
        """
        if not file_path.exists():
            return 0

        lines_processed = 0
        tracked_count = 0

        try:
            if file_path.suffix == ".gz" or file_path.name.endswith(".jsonl.gz"):
                opener = lambda: gzip.open(file_path, "rt", encoding="utf-8", errors="replace")
            else:
                opener = lambda: open(file_path, "r", encoding="utf-8", errors="replace")

            with opener() as f:
                for line_num, line in enumerate(f):
                    if line_num < start_line:
                        continue

                    lines_processed += 1
                    line = line.strip()
                    if not line:
                        continue

                    # Quick check for tracked prefixes before parsing
                    if not any(prefix in line for prefix in ALL_CALLSIGN_PREFIXES):
                        continue

                    try:
                        record = json.loads(line)
                        if self.process_record(record):
                            tracked_count += 1
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            log.error(f"Error scanning {file_path}: {e}")

        if tracked_count > 0:
            log.debug(f"Found {tracked_count} tracked callsigns in {file_path.name}")

        return lines_processed

    def get_recent_files(self, hours: int = 1) -> list:
        """Get log files from the last N hours."""
        now = datetime.now(timezone.utc)
        files = []

        for h in range(hours + 1):
            check_time = now - timedelta(hours=h)
            date_str = check_time.strftime("%Y-%m-%d")
            hour_str = check_time.strftime("%H")

            # Check organized structure
            organized_path = (
                self.log_dir /
                check_time.strftime("%Y") /
                check_time.strftime("%m") /
                check_time.strftime("%d")
            )

            patterns = [
                organized_path / f"adsb_state_{date_str}_{hour_str}.jsonl.gz",
                organized_path / f"adsb_state_{date_str}_{hour_str}.jsonl",
                self.log_dir / f"adsb_state_{date_str}_{hour_str}.jsonl.gz",
                self.log_dir / f"adsb_state_{date_str}_{hour_str}.jsonl",
            ]

            for p in patterns:
                if p.exists():
                    files.append(p)
                    break

        return sorted(set(files), key=lambda p: p.name)

    def run_once(self):
        """Run a single scan cycle."""
        files = self.get_recent_files(LOOKBACK_HOURS)

        for file_path in files:
            # Determine starting line
            if file_path == self.last_processed_file:
                start_line = self.last_processed_line
            else:
                start_line = 0

            lines = self.scan_file(file_path, start_line)

            # Update tracking
            self.last_processed_file = file_path
            self.last_processed_line = start_line + lines

    def run(self):
        """Run the monitor continuously."""
        self.running = True

        def handle_stop(signum, frame):
            log.info("Received stop signal, shutting down...")
            self.running = False

        signal.signal(signal.SIGTERM, handle_stop)
        signal.signal(signal.SIGINT, handle_stop)

        log.info("Starting callsign monitor")
        log.info(f"  Log directory: {self.log_dir}")
        log.info(f"  Tracking: {', '.join(ALL_CALLSIGN_PREFIXES)}")
        log.info(f"  Scan interval: {MONITOR_INTERVAL_SECONDS}s")

        # Test API connection
        if self.api.test_connection():
            log.info("FR24 API connection verified")
        else:
            log.warning("FR24 API connection failed - will use heuristic flight numbers")

        while self.running:
            try:
                self.run_once()
            except Exception as e:
                log.exception(f"Error in monitor cycle: {e}")

            # Wait for next cycle
            for _ in range(MONITOR_INTERVAL_SECONDS):
                if not self.running:
                    break
                time.sleep(1)

        log.info("Callsign monitor stopped")

    def scan_historical(self, start_date: datetime, end_date: datetime):
        """Scan historical log files for a date range."""
        current = start_date
        total_files = 0
        total_tracked = 0

        while current <= end_date:
            # Find files for this date
            date_path = (
                self.log_dir /
                current.strftime("%Y") /
                current.strftime("%m") /
                current.strftime("%d")
            )

            if date_path.exists():
                for f in sorted(date_path.glob("adsb_state_*.jsonl.gz")):
                    lines = self.scan_file(f)
                    total_files += 1
                    log.info(f"Scanned {f.name}: {lines} lines")

            current += timedelta(days=1)

        stats = self.db.get_stats()
        log.info(f"Historical scan complete: {total_files} files, {stats['total_callsigns']} unique callsigns")


def main():
    """Run the callsign monitor as a standalone service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    monitor = CallsignMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
