#!/usr/bin/env python3
"""
Backfill missing route data for Flydubai callsigns using FR24 API.
"""
import sys
import time
import logging
from pathlib import Path

# Add callsign_logger to path
sys.path.insert(0, str(Path(__file__).parent))

from callsign_logger.database import CallsignDatabase
from callsign_logger.fr24_api import FlightRadar24API

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)


def main():
    """Backfill routes for callsigns missing route data."""
    # Use the Dropbox database path explicitly
    db_path = Path("/mnt/m/Dropbox/ADSBPi-Base/callsigns.db")
    db = CallsignDatabase(db_path=db_path)
    api = FlightRadar24API()

    # Test API connection first
    log.info("Testing FR24 API connection...")
    if not api.test_connection():
        log.error("FR24 API connection failed!")
        log.error("Check your API token in callsign_logger/config.py")
        return

    log.info("FR24 API connection successful")

    # Get all Flydubai callsigns without routes
    all_callsigns = db.get_all_callsigns(airline="Flydubai")

    missing_routes = [
        cs for cs in all_callsigns
        if not cs.get('route') or cs.get('route') == ''
    ]

    log.info(f"Found {len(missing_routes)} Flydubai callsigns without routes")

    if not missing_routes:
        log.info("All callsigns already have route data!")
        return

    success_count = 0
    fail_count = 0

    for i, cs in enumerate(missing_routes):
        callsign = cs['callsign']
        log.info(f"[{i+1}/{len(missing_routes)}] Looking up {callsign}...")

        try:
            route_data = api.lookup_route(callsign)

            if route_data and route_data.get('route'):
                # Update database with route info
                db.cache_route(
                    callsign=callsign,
                    flight_number=route_data.get('flight_number'),
                    route=route_data.get('route'),
                    origin=route_data.get('origin'),
                    destination=route_data.get('destination')
                )

                # Also update the main callsigns table
                db.upsert_callsign(
                    callsign=callsign,
                    airline="Flydubai",
                    flight_number=route_data.get('flight_number'),
                    route=route_data.get('route'),
                    origin=route_data.get('origin'),
                    destination=route_data.get('destination'),
                    aircraft_type=route_data.get('aircraft_type'),
                    registration=route_data.get('registration')
                )

                log.info(f"  ✓ {callsign}: {route_data.get('route')}")
                success_count += 1
            else:
                log.warning(f"  ✗ {callsign}: No route data available (flight may not be active)")
                fail_count += 1

            # Rate limiting - wait between requests
            time.sleep(1.5)

        except KeyboardInterrupt:
            log.info("\nBackfill interrupted by user")
            break
        except Exception as e:
            log.error(f"  ✗ {callsign}: Error - {e}")
            fail_count += 1

    log.info("\n=== Backfill Complete ===")
    log.info(f"Successfully updated: {success_count}")
    log.info(f"Failed/Not found: {fail_count}")
    log.info(f"Total processed: {success_count + fail_count}/{len(missing_routes)}")


if __name__ == '__main__':
    main()
