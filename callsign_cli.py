#!/usr/bin/env python3
"""
Command-line interface for callsign logger.

Usage:
    python callsign_cli.py monitor          # Run background monitor
    python callsign_cli.py scan 2025-12-31  # Scan specific date
    python callsign_cli.py list             # List all callsigns
    python callsign_cli.py export           # Export to CSV
    python callsign_cli.py stats            # Show statistics
    python callsign_cli.py schedule FDB4CE  # Show schedule for callsign
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


def parse_date(date_str: str) -> datetime:
    """Parse date string."""
    for fmt in ["%Y-%m-%d", "%Y%m%d"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {date_str}")


def cmd_monitor(args):
    """Run the background monitor."""
    from callsign_logger import CallsignMonitor

    monitor = CallsignMonitor()
    monitor.run()


def cmd_scan(args):
    """Scan historical log files."""
    from callsign_logger import CallsignMonitor

    start_date = parse_date(args.start_date)

    if args.end_date:
        end_date = parse_date(args.end_date)
    else:
        end_date = start_date

    print(f"Scanning logs from {start_date.date()} to {end_date.date()}...")

    monitor = CallsignMonitor()
    monitor.scan_historical(start_date, end_date)

    # Show results
    stats = monitor.db.get_stats()
    print(f"\nScan complete!")
    print(f"  Total callsigns: {stats['total_callsigns']}")
    print(f"  By airline: {stats['by_airline']}")


def cmd_list(args):
    """List all callsigns."""
    from callsign_logger import CallsignDatabase

    db = CallsignDatabase()
    callsigns = db.get_all_callsigns(args.airline)

    if not callsigns:
        print("No callsigns found.")
        return

    # Print header
    print(f"\n{'Callsign':<10} {'Flight':<8} {'Route':<12} {'Type':<6} {'Reg':<10} {'Count':>6} {'Last Seen':<20}")
    print("-" * 80)

    for cs in callsigns[:args.limit]:
        print(
            f"{cs['callsign']:<10} "
            f"{(cs.get('flight_number') or '-'):<8} "
            f"{(cs.get('route') or '-'):<12} "
            f"{(cs.get('aircraft_type') or '-'):<6} "
            f"{(cs.get('registration') or '-'):<10} "
            f"{cs['sighting_count']:>6} "
            f"{cs['last_seen'][:19]:<20}"
        )

    if len(callsigns) > args.limit:
        print(f"\n... and {len(callsigns) - args.limit} more (use --limit to show more)")

    print(f"\nTotal: {len(callsigns)} callsigns")


def cmd_export(args):
    """Export callsigns to CSV."""
    from callsign_logger import CallsignDatabase

    db = CallsignDatabase()

    output_path = Path(args.output) if args.output else Path("callsigns_export.csv")
    db.export_csv(output_path, args.airline)

    print(f"Exported to {output_path}")


def cmd_stats(args):
    """Show database statistics."""
    from callsign_logger import CallsignDatabase

    db = CallsignDatabase()
    stats = db.get_stats()

    print("\n=== Callsign Database Statistics ===\n")
    print(f"Total unique callsigns: {stats['total_callsigns']}")
    print(f"Total sightings: {stats['total_sightings']}")

    print("\nBy airline:")
    for airline, count in stats['by_airline'].items():
        print(f"  {airline}: {count}")

    print("\nTop 10 most frequent callsigns:")
    for callsign, count in stats['top_callsigns']:
        cs_data = db.get_callsign(callsign)
        route = cs_data.get('route', '-') if cs_data else '-'
        print(f"  {callsign:<10} {route:<12} ({count} sightings)")


def cmd_schedule(args):
    """Show schedule pattern for a callsign."""
    from callsign_logger import CallsignDatabase

    db = CallsignDatabase()
    callsign = args.callsign.upper()

    cs_data = db.get_callsign(callsign)
    if not cs_data:
        print(f"Callsign {callsign} not found.")
        return

    schedule = db.get_schedule(callsign)

    print(f"\n=== Schedule for {callsign} ===\n")
    print(f"Flight: {cs_data.get('flight_number', 'Unknown')}")
    print(f"Route: {cs_data.get('route', 'Unknown')}")
    print(f"Total sightings: {schedule['total_sightings']}")

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    print("\nBy day of week:")
    for i, day in enumerate(days):
        count = schedule['by_day_of_week'].get(i, 0)
        bar = "█" * min(count, 50)
        print(f"  {day}: {bar} ({count})")

    print("\nBy hour (UTC):")
    for hour in range(24):
        count = schedule['by_hour'].get(hour, 0)
        bar = "█" * min(count, 30)
        if count > 0:
            print(f"  {hour:02d}:00 {bar} ({count})")


def cmd_lookup(args):
    """Look up a callsign via FR24 API."""
    from callsign_logger import FlightRadar24API

    api = FlightRadar24API()
    callsign = args.callsign.upper()

    print(f"Looking up {callsign}...")
    route = api.lookup_route(callsign)

    if route:
        print(f"\n  Callsign: {callsign}")
        print(f"  Flight:   {route.get('flight_number', 'Unknown')}")
        print(f"  Route:    {route.get('route', 'Unknown')}")
        print(f"  Origin:   {route.get('origin', 'Unknown')}")
        print(f"  Dest:     {route.get('destination', 'Unknown')}")
        print(f"  Aircraft: {route.get('aircraft_type', 'Unknown')}")
        print(f"  Reg:      {route.get('registration', 'Unknown')}")
    else:
        print(f"  No data found for {callsign}")
        print("  (Flight may not be currently active)")


def main():
    parser = argparse.ArgumentParser(
        description="Callsign Logger - Track Emirates and Flydubai flights",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Run background monitor")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan historical logs")
    scan_parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    scan_parser.add_argument("--end-date", "-e", help="End date (default: same as start)")

    # List command
    list_parser = subparsers.add_parser("list", help="List callsigns")
    list_parser.add_argument("--airline", "-a", help="Filter by airline (Emirates/Flydubai)")
    list_parser.add_argument("--limit", "-l", type=int, default=50, help="Max results")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export to CSV")
    export_parser.add_argument("--output", "-o", help="Output file path")
    export_parser.add_argument("--airline", "-a", help="Filter by airline")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Show callsign schedule")
    schedule_parser.add_argument("callsign", help="Callsign to analyze")

    # Lookup command
    lookup_parser = subparsers.add_parser("lookup", help="Look up callsign via API")
    lookup_parser.add_argument("callsign", help="Callsign to look up")

    args = parser.parse_args()

    try:
        if args.command == "monitor":
            cmd_monitor(args)
        elif args.command == "scan":
            cmd_scan(args)
        elif args.command == "list":
            cmd_list(args)
        elif args.command == "export":
            cmd_export(args)
        elif args.command == "stats":
            cmd_stats(args)
        elif args.command == "schedule":
            cmd_schedule(args)
        elif args.command == "lookup":
            cmd_lookup(args)
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 1
    except Exception as e:
        log.exception(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
