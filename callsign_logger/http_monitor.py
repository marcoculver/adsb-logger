"""HTTP-based monitoring service for callsign tracking.

This version polls aircraft.json via HTTP instead of reading log files.
Suitable for Docker-based ADSB setups like docker-adsb-ultrafeeder.
"""
import json
import logging
import signal
import time
from datetime import datetime, timezone
from typing import Optional, Set, Dict, Any
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

from .config import (
    ALL_CALLSIGN_PREFIXES,
    TRACKED_AIRLINES,
    MONITOR_INTERVAL_SECONDS,
)
from .database import CallsignDatabase
from .fr24_api import FlightRadar24API, convert_callsign_to_flight_number

log = logging.getLogger(__name__)


class HTTPCallsignMonitor:
    """
    Background service that monitors ADSB data via HTTP for Emirates and Flydubai callsigns.

    Polls aircraft.json endpoint and updates the database with:
    - New callsigns
    - Flight numbers and routes (via FR24 API)
    - Sighting frequency for schedule analysis
    """

    def __init__(
        self,
        aircraft_json_url: str = "http://localhost:8080/data/aircraft.json",
        db: Optional[CallsignDatabase] = None,
        api: Optional[FlightRadar24API] = None,
        skip_api: bool = False,
        poll_interval: int = MONITOR_INTERVAL_SECONDS,
    ):
        self.aircraft_json_url = aircraft_json_url
        self.db = db or CallsignDatabase()
        self.api = api or FlightRadar24API()
        self.skip_api = skip_api
        self.poll_interval = poll_interval
        self.running = False

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

    def fetch_aircraft_data(self) -> Optional[Dict[str, Any]]:
        """Fetch current aircraft data from HTTP endpoint."""
        try:
            with urlopen(self.aircraft_json_url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data
        except (URLError, HTTPError) as e:
            log.error(f"Failed to fetch aircraft data: {e}")
            return None
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse aircraft JSON: {e}")
            return None
        except Exception as e:
            log.exception(f"Unexpected error fetching aircraft data: {e}")
            return None

    def process_aircraft(self, aircraft: Dict[str, Any]) -> bool:
        """
        Process a single aircraft record.

        Returns True if this was a tracked callsign.
        """
        callsign = (aircraft.get("flight") or "").strip().upper()

        if not self.is_tracked_callsign(callsign):
            return False

        airline = self.get_airline_for_callsign(callsign)
        if not airline:
            return False

        # Extract aircraft data
        hex_code = aircraft.get("hex")
        aircraft_type = aircraft.get("t")  # ICAO type code
        registration = aircraft.get("r")

        seen_at = datetime.now(timezone.utc)

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

        if is_new:
            log.info(f"New callsign: {callsign} ({airline})")

        return True

    def run_once(self):
        """Run a single poll cycle."""
        data = self.fetch_aircraft_data()
        if not data:
            return

        aircraft_list = data.get("aircraft", [])
        if not aircraft_list:
            log.debug("No aircraft in response")
            return

        tracked_count = 0
        for aircraft in aircraft_list:
            if self.process_aircraft(aircraft):
                tracked_count += 1

        if tracked_count > 0:
            log.debug(f"Found {tracked_count} tracked callsigns in current snapshot")

    def run(self):
        """Run the monitor continuously."""
        self.running = True

        def handle_stop(signum, frame):
            log.info("Received stop signal, shutting down...")
            self.running = False

        signal.signal(signal.SIGTERM, handle_stop)
        signal.signal(signal.SIGINT, handle_stop)

        log.info("Starting HTTP callsign monitor")
        log.info(f"  Aircraft JSON URL: {self.aircraft_json_url}")
        log.info(f"  Tracking: {', '.join(ALL_CALLSIGN_PREFIXES)}")
        log.info(f"  Poll interval: {self.poll_interval}s")

        # Test API connection
        if not self.skip_api:
            if self.api.test_connection():
                log.info("FR24 API connection verified")
            else:
                log.warning("FR24 API connection failed - will use heuristic flight numbers")

        # Test aircraft data endpoint
        test_data = self.fetch_aircraft_data()
        if test_data:
            aircraft_count = len(test_data.get("aircraft", []))
            log.info(f"Aircraft data endpoint working ({aircraft_count} aircraft)")
        else:
            log.error("Failed to fetch aircraft data - check URL and network connectivity")

        while self.running:
            try:
                self.run_once()
            except Exception as e:
                log.exception(f"Error in monitor cycle: {e}")

            # Wait for next cycle
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)

        log.info("HTTP callsign monitor stopped")


def main():
    """Run the HTTP callsign monitor as a standalone service."""
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Get URL from environment or use default
    url = os.environ.get("AIRCRAFT_JSON_URL", "http://localhost:8080/data/aircraft.json")

    monitor = HTTPCallsignMonitor(aircraft_json_url=url)
    monitor.run()


if __name__ == "__main__":
    main()
