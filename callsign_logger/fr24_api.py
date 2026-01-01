"""FlightRadar24 API client for route lookups."""
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote
import json

from .config import FR24_API_TOKEN, API_REQUEST_DELAY

log = logging.getLogger(__name__)


class FlightRadar24API:
    """
    Client for FlightRadar24 API.

    Used to look up flight routes and details from callsigns.
    """

    BASE_URL = "https://fr24api.flightradar24.com/api"

    def __init__(self, token: Optional[str] = None, use_sandbox: bool = False):
        self.token = token or FR24_API_TOKEN
        self.use_sandbox = use_sandbox
        self.last_request_time = 0
        self._api_available = None  # Will be set after first test

    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < API_REQUEST_DELAY:
            time.sleep(API_REQUEST_DELAY - elapsed)
        self.last_request_time = time.time()

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make API request."""
        # Skip if we already know API is unavailable
        if self._api_available is False:
            return None

        self._rate_limit()

        # Use sandbox prefix if enabled
        if self.use_sandbox:
            url = f"{self.BASE_URL}/sandbox/{endpoint}"
        else:
            url = f"{self.BASE_URL}/{endpoint}"

        if params:
            query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
            url = f"{url}?{query}"

        headers = {
            "Accept": "application/json",
            "Accept-Version": "v1",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "ADSB-Logger/1.0",
        }

        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except HTTPError as e:
            log.warning(f"FR24 API HTTP error {e.code}: {e.reason}")
            if e.code == 429:
                log.warning("Rate limited - waiting 60 seconds")
                time.sleep(60)
            elif e.code in (400, 401, 403):
                # Mark API as unavailable to avoid repeated failures
                if self._api_available is None:
                    log.warning("FR24 API unavailable - will use heuristic flight numbers only")
                    self._api_available = False
            return None
        except URLError as e:
            log.warning(f"FR24 API URL error: {e.reason}")
            return None
        except Exception as e:
            log.warning(f"FR24 API error: {e}")
            return None

    def get_flight_by_callsign(self, callsign: str) -> Optional[Dict[str, Any]]:
        """
        Look up a flight by its callsign.

        Returns flight details including route if available.
        """
        callsign = callsign.strip().upper()

        # Try the live flight positions endpoint
        data = self._request("live/flight-positions/full", {"callsigns": callsign})

        if not data or "data" not in data:
            return None

        flights = data.get("data", [])
        if not flights:
            return None

        flight = flights[0]

        # Extract relevant info
        result = {
            "callsign": callsign,
            "flight_number": flight.get("flight"),
            "aircraft_type": flight.get("aircraft", {}).get("model", {}).get("code"),
            "registration": flight.get("aircraft", {}).get("registration"),
            "origin": flight.get("airport", {}).get("origin", {}).get("code", {}).get("iata"),
            "destination": flight.get("airport", {}).get("destination", {}).get("code", {}).get("iata"),
            "airline": flight.get("airline", {}).get("name"),
        }

        # Build route string
        if result["origin"] and result["destination"]:
            result["route"] = f"{result['origin']}-{result['destination']}"

        return result

    def get_flight_details(self, flight_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed flight information by flight ID."""
        data = self._request(f"flights/{flight_id}")
        return data

    def search_flights(
        self,
        callsign_prefix: Optional[str] = None,
        airline_icao: Optional[str] = None,
        bounds: Optional[str] = None
    ) -> Optional[list]:
        """
        Search for live flights.

        Args:
            callsign_prefix: Filter by callsign prefix (e.g., "UAE", "FDB")
            airline_icao: Filter by airline ICAO code
            bounds: Geographic bounds "lat1,lat2,lon1,lon2"
        """
        params = {}
        if callsign_prefix:
            params["callsigns"] = callsign_prefix
        if airline_icao:
            params["airlines"] = airline_icao
        if bounds:
            params["bounds"] = bounds

        data = self._request("live/flight-positions/full", params)

        if not data or "data" not in data:
            return None

        return data["data"]

    def lookup_route(self, callsign: str) -> Optional[Dict[str, str]]:
        """
        Simple route lookup - returns just the essential route info.

        Returns dict with: flight_number, route, origin, destination
        """
        flight = self.get_flight_by_callsign(callsign)

        if not flight:
            return None

        return {
            "flight_number": flight.get("flight_number"),
            "route": flight.get("route"),
            "origin": flight.get("origin"),
            "destination": flight.get("destination"),
            "aircraft_type": flight.get("aircraft_type"),
            "registration": flight.get("registration"),
        }

    def test_connection(self) -> bool:
        """Test API connectivity."""
        try:
            # Try a simple search with limit
            data = self._request("live/flight-positions/light", {"limit": 1})
            if data and "data" in data:
                log.info("FR24 API connection successful")
                return True
            return False
        except Exception as e:
            log.error(f"FR24 API connection test failed: {e}")
            return False


def convert_callsign_to_flight_number(callsign: str) -> Optional[str]:
    """
    Attempt to convert a callsign to a flight number based on known patterns.

    For Emirates: UAE123 -> EK123
    For Flydubai: FDB123 or FDB1AB -> FZ123 or FZ1AB

    Note: This is a heuristic and may not always be accurate.
    The API lookup is preferred for accurate data.
    """
    callsign = callsign.strip().upper()

    # Emirates: UAE -> EK
    if callsign.startswith("UAE"):
        suffix = callsign[3:].lstrip("0")  # Remove leading zeros
        if suffix.isdigit():
            return f"EK{suffix}"
        return f"EK{callsign[3:]}"

    # Flydubai: FDB -> FZ
    if callsign.startswith("FDB"):
        suffix = callsign[3:]
        # Some FDB callsigns have letters (like FDB4CE)
        # Try to extract just the numeric part
        numeric_part = ""
        for c in suffix:
            if c.isdigit():
                numeric_part += c
            else:
                break

        if numeric_part:
            return f"FZ{numeric_part.lstrip('0') or '0'}"
        return f"FZ{suffix}"

    return None
