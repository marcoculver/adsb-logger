#!/usr/bin/env python3
"""Test flight-summary with flight ID."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from callsign_logger.config import FR24_API_TOKEN

callsign = "FDB1211"

headers = {
    "Accept": "application/json",
    "Accept-Version": "v1",
    "Authorization": f"Bearer {FR24_API_TOKEN}",
    "User-Agent": "ADSB-Logger/1.0",
}

print(f"Step 1: Getting flight data for {callsign} from live endpoint...")
url = f"https://fr24api.flightradar24.com/api/live/flight-positions/full?callsigns={callsign}"

try:
    req = Request(url, headers=headers)
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

        if data.get("data"):
            flight = data["data"][0]
            print(f"✓ Found flight data")
            print(f"\nFlight data keys: {list(flight.keys())}")

            # Look for possible ID fields
            flight_id = flight.get("id")
            ident = flight.get("identification")

            print(f"\nFlight ID: {flight_id}")
            print(f"Identification: {json.dumps(ident, indent=2) if ident else None}")

            # Try flight-summary with the ID
            if flight_id:
                print(f"\n\nStep 2: Testing flight-summary endpoints with ID: {flight_id}")

                test_urls = [
                    f"https://fr24api.flightradar24.com/api/flight-summary/light/{flight_id}",
                    f"https://fr24api.flightradar24.com/api/flight-summary/full/{flight_id}",
                    f"https://fr24api.flightradar24.com/flight-summary/light/{flight_id}",
                    f"https://fr24api.flightradar24.com/flight-summary/full/{flight_id}",
                ]

                for test_url in test_urls:
                    print(f"\nTrying: {test_url}")
                    try:
                        req2 = Request(test_url, headers=headers)
                        with urlopen(req2, timeout=10) as resp2:
                            summary = json.loads(resp2.read().decode("utf-8"))
                            print(f"  ✓ SUCCESS!")
                            print(f"  Keys: {list(summary.keys())[:10]}")
                            break
                    except HTTPError as e:
                        print(f"  ✗ HTTP {e.code}: {e.reason}")
                    except Exception as e:
                        print(f"  ✗ Error: {e}")
            else:
                print("\n✗ No flight ID found in response")
        else:
            print("✗ No flight data returned (flight might not be active)")

except Exception as e:
    print(f"✗ Error: {e}")
