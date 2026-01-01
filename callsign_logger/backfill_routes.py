#!/usr/bin/env python3
"""
Backfill missing route data from FR24 API.

This script queries the FR24 API for callsigns that are missing
route information and updates the database.

Usage:
    python -m callsign_logger.backfill_routes [--all] [--dry-run]

Options:
    --all      : Update all callsigns, even if they already have route data
    --dry-run  : Show what would be updated without making changes
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from .database import CallsignDatabase
from .fr24_api import FlightRadar24API

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def backfill_routes(db: CallsignDatabase, api: FlightRadar24API, update_all: bool = False, dry_run: bool = False):
    """Backfill missing route data from API."""

    # Get all callsigns
    all_callsigns = db.get_all_callsigns()

    if not all_callsigns:
        log.info("No callsigns found in database")
        return

    log.info(f"Found {len(all_callsigns)} callsigns in database")

    # Filter to those needing updates
    to_update = []
    for cs in all_callsigns:
        if update_all:
            to_update.append(cs)
        elif not cs.get('route') or not cs.get('flight_number'):
            to_update.append(cs)

    if not to_update:
        log.info("All callsigns already have route data")
        return

    log.info(f"Will attempt to update {len(to_update)} callsigns")

    if dry_run:
        log.info("DRY RUN MODE - No changes will be made")
        for cs in to_update[:10]:
            log.info(f"  Would update: {cs['callsign']}")
        if len(to_update) > 10:
            log.info(f"  ... and {len(to_update) - 10} more")
        return

    # Test API connection first
    log.info("Testing FR24 API connection...")
    if not api.test_connection():
        log.error("FR24 API connection failed")
        log.error("Cannot proceed with backfill")
        return

    log.info("API connection OK")
    log.info("Starting backfill...")
    print()

    updated = 0
    failed = 0
    no_data = 0

    for i, cs in enumerate(to_update, 1):
        callsign = cs['callsign']

        log.info(f"[{i}/{len(to_update)}] Looking up {callsign}...")

        try:
            route_data = api.lookup_route(callsign)

            if route_data:
                flight_number = route_data.get('flight_number')
                route = route_data.get('route')
                origin = route_data.get('origin')
                destination = route_data.get('destination')
                aircraft_type = route_data.get('aircraft_type')
                registration = route_data.get('registration')

                if flight_number or route:
                    # Update database
                    db.upsert_callsign(
                        callsign=callsign,
                        airline=cs['airline'],
                        flight_number=flight_number,
                        route=route,
                        origin=origin,
                        destination=destination,
                        aircraft_type=aircraft_type or cs.get('aircraft_type'),
                        registration=registration or cs.get('registration'),
                    )

                    # Cache the route
                    db.cache_route(callsign, flight_number, route, origin, destination)

                    log.info(f"  ✓ Updated: {flight_number} {route or '(no route)'}")
                    updated += 1
                else:
                    log.info(f"  - No route data returned (might not be currently flying)")
                    no_data += 1
            else:
                log.info(f"  - No data returned")
                no_data += 1

        except Exception as e:
            log.error(f"  ✗ Error: {e}")
            failed += 1

        # Rate limiting
        if i < len(to_update):
            time.sleep(1.5)  # Be nice to the API

    print()
    log.info("="  * 60)
    log.info("Backfill complete")
    log.info(f"  Updated:  {updated}")
    log.info(f"  No data:  {no_data}")
    log.info(f"  Failed:   {failed}")
    log.info(f"  Total:    {len(to_update)}")
    log.info("="  * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill missing route data from FR24 API"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Update all callsigns, even if they already have route data"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes"
    )

    args = parser.parse_args()

    # Initialize
    db = CallsignDatabase()
    api = FlightRadar24API()

    # Run backfill
    try:
        backfill_routes(db, api, update_all=args.all, dry_run=args.dry_run)
    except KeyboardInterrupt:
        log.info("\nInterrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
