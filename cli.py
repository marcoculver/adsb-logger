#!/usr/bin/env python3
"""
Command-line interface for ADS-B flight data extraction.

Usage:
    python cli.py extract FDB8876 2024-12-31
    python cli.py extract FDB8876 2024-12-31 --no-charts
    python cli.py extract FDB8876 2024-12-31 --end-date 2025-01-01
    python cli.py list 2024-12-31
    python cli.py list 2024-12-31 --pattern "FDB*"
"""

import argparse
import logging
import sys
from datetime import datetime, date
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


def parse_date(date_str: str) -> date:
    """Parse date string in various formats."""
    for fmt in ["%Y-%m-%d", "%Y%m%d", "%d/%m/%Y", "%d-%m-%Y"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {date_str}. Use YYYY-MM-DD format.")


def cmd_extract(args):
    """Handle the extract command."""
    from flight_extractor import FlightExtractor, Config
    from flight_export import CSVExporter, KMLGenerator
    from flight_charts import generate_all_charts, generate_dashboard

    # Parse arguments
    callsign = args.callsign.upper()
    target_date = parse_date(args.date)
    end_date = parse_date(args.end_date) if args.end_date else None

    # Setup config
    config = Config.from_env()
    if args.log_dir:
        config.log_dir = Path(args.log_dir)
    if args.output_dir:
        config.output_dir = Path(args.output_dir)

    print(f"\n{'='*60}")
    print(f"  ADS-B Flight Extractor")
    print(f"{'='*60}")
    print(f"  Callsign: {callsign}")
    print(f"  Date: {target_date}")
    if end_date:
        print(f"  End Date: {end_date}")
    print(f"  Log Dir: {config.log_dir}")
    print(f"  Output Dir: {config.output_dir}")
    print(f"{'='*60}\n")

    # Check if log directory exists
    if not config.log_dir.exists():
        print(f"ERROR: Log directory not found: {config.log_dir}")
        print("  Make sure Dropbox is synced or specify --log-dir")
        return 1

    # Create extractor
    extractor = FlightExtractor(config)

    def progress(current, total, message):
        print(f"  [{current}/{total}] {message}")

    # Extract flight data
    print("Extracting flight data...")
    flight_data = extractor.extract(
        callsign=callsign,
        target_date=target_date,
        check_crossover=not args.no_crossover,
        progress_callback=progress if args.verbose else None
    )

    if not flight_data.records:
        print(f"\nNo data found for {callsign} on {target_date}")
        return 1

    print(f"\nFound {len(flight_data.records)} records")
    print(f"  Duration: {flight_data.metadata.duration_minutes:.1f} minutes")
    print(f"  Max Altitude: {flight_data.metadata.max_altitude_ft or 'N/A'} ft")
    print(f"  Max Speed: {flight_data.metadata.max_ground_speed_kts or 'N/A'} kts")

    if flight_data.metadata.crossover_detected:
        print(f"  Midnight crossover detected!")
        print(f"  Actual range: {flight_data.metadata.actual_start_date} to {flight_data.metadata.actual_end_date}")

    output_dir = flight_data.output_dir
    print(f"\nOutput directory: {output_dir}")

    # Save metadata and summary
    print("\nSaving metadata...")
    extractor.save_metadata(flight_data)
    extractor.save_summary(flight_data)

    # Export CSV
    print("Exporting CSV...")
    csv_exporter = CSVExporter()
    csv_path = csv_exporter.export(
        flight_data.records,
        output_dir / "flight_data.csv"
    )
    print(f"  Saved: {csv_path.name}")

    # Generate KML
    if not args.no_kml:
        print("Generating KML...")
        kml_gen = KMLGenerator()
        kml_path = kml_gen.generate(
            flight_data.records,
            output_dir / "flight_path.kml",
            callsign,
            str(target_date)
        )
        print(f"  Saved: {kml_path.name}")

    # Generate charts
    if not args.no_charts:
        print("\nGenerating charts...")

        def chart_progress(current, total, name):
            print(f"  [{current}/{total}] {name}")

        results = generate_all_charts(
            records=flight_data.records,
            callsign=callsign,
            output_dir=output_dir,
            generate_png=not args.html_only,
            generate_html=not args.png_only,
            progress_callback=chart_progress
        )

        # Generate dashboard
        print("Generating dashboard...")
        dashboard_path = generate_dashboard(
            records=flight_data.records,
            callsign=callsign,
            output_dir=output_dir,
            flight_metadata={
                "aircraft_type": flight_data.metadata.aircraft_type,
                "registration": flight_data.metadata.registration,
                "duration_minutes": flight_data.metadata.duration_minutes,
                "max_altitude_ft": flight_data.metadata.max_altitude_ft,
                "records_extracted": flight_data.metadata.records_extracted,
            }
        )
        if dashboard_path:
            print(f"  Saved: {dashboard_path.name}")

    print(f"\n{'='*60}")
    print(f"  Extraction complete!")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")

    return 0


def cmd_list(args):
    """Handle the list command - show flights on a date."""
    from flight_extractor import FlightScanner, Config
    import fnmatch

    target_date = parse_date(args.date)

    config = Config.from_env()
    if args.log_dir:
        config.log_dir = Path(args.log_dir)

    print(f"\nListing flights on {target_date}")
    print(f"Log directory: {config.log_dir}")

    if not config.log_dir.exists():
        print(f"ERROR: Log directory not found: {config.log_dir}")
        return 1

    scanner = FlightScanner(config)

    print("Scanning files (this may take a moment)...")
    callsigns = scanner.get_unique_callsigns(target_date)

    if not callsigns:
        print(f"No flights found on {target_date}")
        return 0

    # Filter by pattern if specified
    if args.pattern:
        pattern = args.pattern.upper()
        callsigns = {cs for cs in callsigns if fnmatch.fnmatch(cs.upper(), pattern)}

    # Sort and display
    sorted_callsigns = sorted(callsigns)

    print(f"\nFound {len(sorted_callsigns)} unique callsigns:\n")

    # Display in columns
    cols = 4
    for i in range(0, len(sorted_callsigns), cols):
        row = sorted_callsigns[i:i+cols]
        print("  " + "  ".join(f"{cs:<12}" for cs in row))

    print()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="ADS-B Flight Data Extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py extract FDB8876 2024-12-31
  python cli.py extract FDB8876 2024-12-31 --no-charts
  python cli.py list 2024-12-31 --pattern "FDB*"
        """
    )

    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose output")
    parser.add_argument("--log-dir", type=str,
                       help="Override log directory path")
    parser.add_argument("--output-dir", type=str,
                       help="Override output directory path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Extract command
    extract_parser = subparsers.add_parser("extract",
                                           help="Extract flight data")
    extract_parser.add_argument("callsign",
                               help="Flight callsign (e.g., FDB8876)")
    extract_parser.add_argument("date",
                               help="Date in YYYY-MM-DD format")
    extract_parser.add_argument("--end-date",
                               help="End date for multi-day extraction")
    extract_parser.add_argument("--no-charts", action="store_true",
                               help="Skip chart generation")
    extract_parser.add_argument("--no-kml", action="store_true",
                               help="Skip KML generation")
    extract_parser.add_argument("--no-crossover", action="store_true",
                               help="Don't check for midnight crossover")
    extract_parser.add_argument("--html-only", action="store_true",
                               help="Only generate HTML charts (no PNG)")
    extract_parser.add_argument("--png-only", action="store_true",
                               help="Only generate PNG charts (no HTML)")

    # List command
    list_parser = subparsers.add_parser("list",
                                        help="List flights on a date")
    list_parser.add_argument("date",
                            help="Date in YYYY-MM-DD format")
    list_parser.add_argument("--pattern", "-p",
                            help="Filter by callsign pattern (e.g., FDB*)")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.command == "extract":
            return cmd_extract(args)
        elif args.command == "list":
            return cmd_list(args)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        log.exception(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
