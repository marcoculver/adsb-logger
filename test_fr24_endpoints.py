#!/usr/bin/env python3
"""Test different FR24 API endpoint formats."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from callsign_logger.config import FR24_API_TOKEN

# Test callsign
callsign = "FDB1211"

# Different endpoint formats to try for flight-summary
endpoints = [
    # Flight summary with path parameter
    f"https://fr24api.flightradar24.com/api/flight-summary/light/{callsign}",
    f"https://fr24api.flightradar24.com/api/flight-summary/full/{callsign}",
    # Flight summary with query parameter
    f"https://fr24api.flightradar24.com/api/flight-summary/light?callsign={callsign}",
    f"https://fr24api.flightradar24.com/api/flight-summary/full?callsign={callsign}",
    f"https://fr24api.flightradar24.com/api/flight-summary/light?flight={callsign}",
    f"https://fr24api.flightradar24.com/api/flight-summary/full?flight={callsign}",
    # Without /api prefix
    f"https://fr24api.flightradar24.com/flight-summary/light/{callsign}",
    f"https://fr24api.flightradar24.com/flight-summary/full/{callsign}",
    # Live endpoint (known to work)
    f"https://fr24api.flightradar24.com/api/live/flight-positions/full?callsigns={callsign}",
]

headers = {
    "Accept": "application/json",
    "Accept-Version": "v1",
    "Authorization": f"Bearer {FR24_API_TOKEN}",
    "User-Agent": "ADSB-Logger/1.0",
}

print(f"Testing FR24 API endpoints for callsign: {callsign}\n")
print(f"API Token: {FR24_API_TOKEN[:20]}...\n")

for i, url in enumerate(endpoints, 1):
    print(f"{i}. Testing: {url}")
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"   ✓ SUCCESS - Status {resp.status}")
            print(f"   Response keys: {list(data.keys())[:5]}")
            # Print flight info if found
            if "identification" in data:
                flight_num = data.get("identification", {}).get("number", {}).get("default")
                print(f"   Flight number: {flight_num}")
            elif "data" in data and data["data"]:
                print(f"   Found {len(data['data'])} flights")
            print()
            break
    except HTTPError as e:
        print(f"   ✗ HTTP {e.code}: {e.reason}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    print()
else:
    print("All endpoints failed!")
