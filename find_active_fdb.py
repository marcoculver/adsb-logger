#!/usr/bin/env python3
"""Find currently active FDB flights."""
import json
from urllib.request import Request, urlopen
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from callsign_logger.config import FR24_API_TOKEN

headers = {
    "Accept": "application/json",
    "Accept-Version": "v1",
    "Authorization": f"Bearer {FR24_API_TOKEN}",
    "User-Agent": "ADSB-Logger/1.0",
}

print("Searching for active Flydubai flights...")

# Get all flights in UAE region
url = "https://fr24api.flightradar24.com/api/live/flight-positions/full?bounds=24,26,54,56"

try:
    req = Request(url, headers=headers)
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

        if data.get("data"):
            fdb_flights = []
            for flight in data["data"]:
                callsign = flight.get("identification", {}).get("callsign")
                if callsign and callsign.startswith("FDB"):
                    fdb_flights.append(flight)

            if fdb_flights:
                print(f"\nFound {len(fdb_flights)} active FDB flights:")
                for f in fdb_flights[:5]:  # Show first 5
                    cs = f.get("identification", {}).get("callsign")
                    flight_id = f.get("id")
                    origin = f.get("airport", {}).get("origin", {}).get("code", {}).get("iata")
                    dest = f.get("airport", {}).get("destination", {}).get("code", {}).get("iata")
                    route = f"{origin}-{dest}" if origin and dest else "N/A"
                    print(f"  {cs}: ID={flight_id}, Route={route}")
            else:
                print("\n✗ No active FDB flights found in UAE region right now")
                print("\nTrying to search for any FDB callsign pattern...")

                # Try specific known FDB flights
                test_callsigns = ["FDB1", "FDB10", "FDB100", "FDB2", "FDB20"]
                for cs in test_callsigns:
                    url2 = f"https://fr24api.flightradar24.com/api/live/flight-positions/full?callsigns={cs}"
                    req2 = Request(url2, headers=headers)
                    with urlopen(req2, timeout=10) as resp2:
                        data2 = json.loads(resp2.read().decode("utf-8"))
                        if data2.get("data"):
                            print(f"  Found: {cs}")
                            break
        else:
            print("✗ No flights found")

except Exception as e:
    print(f"✗ Error: {e}")
