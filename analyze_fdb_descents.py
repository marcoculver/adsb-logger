#!/usr/bin/env python3
"""
Analyze descent speeds for FDB (Flydubai) aircraft.

Extracts descent data from when aircraft start descending into DXB until 15,000 ft,
calculating TAS, IAS, and G/S for each flight.
"""
import gzip
import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import csv
import math

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# Constants
RAW_LOG_DIR = Path("/mnt/m/Dropbox/ADSBPi-Base/raw")
DB_PATH = Path("/mnt/m/Dropbox/ADSBPi-Base/callsigns.db")
OUTPUT_DIR = Path("/mnt/m/Dropbox/ADSBPi-Base/analyses/Descent Speed Analysis")

# Flydubai operates only these aircraft types
FLYDUBAI_AIRCRAFT_TYPES = {'B738', 'B38M', 'B39M', 'B737', 'B73G', 'B73H'}

# DXB airport coordinates
DXB_LAT = 25.2532
DXB_LON = 55.3657

# Descent criteria
DESCENT_START_ALT = 40000  # Start looking for descents below this altitude
DESCENT_END_ALT = 15000    # End analysis at this altitude
MIN_DESCENT_RATE = -100    # ft/min (negative means descending)
DXB_RADIUS_NM = 150        # Consider descents within this radius of DXB


class FlightTrack:
    """Track a single flight's trajectory."""

    def __init__(self, hex_code: str, callsign: str, registration: str = None, aircraft_type: str = None):
        self.hex_code = hex_code
        self.callsign = callsign
        self.registration = registration
        self.aircraft_type = aircraft_type
        self.points: List[Dict] = []
        self.in_descent = False
        self.descent_started = False
        self.descent_points: List[Dict] = []

    def add_point(self, record: Dict):
        """Add a data point to the flight track."""
        # Don't keep all points, only descent points to save memory
        # self.points.append(record)

        # Check if we're in descent phase
        alt_baro = record.get('alt_baro')
        baro_rate = record.get('baro_rate')
        lat = record.get('lat')
        lon = record.get('lon')

        # Handle string values (data quality issue)
        if isinstance(alt_baro, str):
            try:
                alt_baro = float(alt_baro) if alt_baro != 'ground' else 0
            except (ValueError, TypeError):
                alt_baro = None

        if isinstance(baro_rate, str):
            try:
                baro_rate = float(baro_rate)
            except (ValueError, TypeError):
                baro_rate = None

        if alt_baro is None or lat is None or lon is None:
            return

        # Check if within DXB area
        distance_nm = calculate_distance(lat, lon, DXB_LAT, DXB_LON)

        # Start tracking descent if:
        # 1. Below start altitude
        # 2. Descending (negative baro rate)
        # 3. Within radius of DXB
        if (not self.descent_started and
            alt_baro < DESCENT_START_ALT and
            alt_baro > DESCENT_END_ALT and
            distance_nm < DXB_RADIUS_NM and
            baro_rate is not None and
            baro_rate < MIN_DESCENT_RATE):

            self.descent_started = True
            self.in_descent = True
            log.debug(f"Descent started for {self.callsign} at {alt_baro} ft, {distance_nm:.1f} NM from DXB")

        # Track descent points
        if self.in_descent and alt_baro > DESCENT_END_ALT:
            self.descent_points.append(record)
        elif self.in_descent and alt_baro <= DESCENT_END_ALT:
            # Descent complete
            self.in_descent = False
            log.debug(f"Descent complete for {self.callsign}, {len(self.descent_points)} points")

    def get_descent_stats(self) -> Optional[Dict]:
        """Calculate descent statistics."""
        if not self.descent_points or len(self.descent_points) < 2:
            return None

        # Extract speeds from descent points
        tas_values = [p['tas'] for p in self.descent_points if p.get('tas')]
        ias_values = [p['ias'] for p in self.descent_points if p.get('ias')]
        gs_values = [p['gs'] for p in self.descent_points if p.get('gs')]

        if not tas_values or not ias_values or not gs_values:
            return None

        # Get altitude range
        altitudes = [p['alt_baro'] for p in self.descent_points if p.get('alt_baro')]
        start_alt = max(altitudes) if altitudes else None
        end_alt = min(altitudes) if altitudes else None

        # Get timestamps
        start_time = datetime.fromtimestamp(self.descent_points[0]['_ts'])
        end_time = datetime.fromtimestamp(self.descent_points[-1]['_ts'])
        duration_mins = (end_time - start_time).total_seconds() / 60

        return {
            'callsign': self.callsign,
            'registration': self.registration or 'Unknown',
            'aircraft_type': self.aircraft_type or 'Unknown',
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_mins': round(duration_mins, 2),
            'start_altitude_ft': start_alt,
            'end_altitude_ft': end_alt,
            'avg_tas_kt': round(sum(tas_values) / len(tas_values), 1),
            'avg_ias_kt': round(sum(ias_values) / len(ias_values), 1),
            'avg_gs_kt': round(sum(gs_values) / len(gs_values), 1),
            'max_tas_kt': round(max(tas_values), 1),
            'max_ias_kt': round(max(ias_values), 1),
            'max_gs_kt': round(max(gs_values), 1),
            'min_tas_kt': round(min(tas_values), 1),
            'min_ias_kt': round(min(ias_values), 1),
            'min_gs_kt': round(min(gs_values), 1),
            'num_points': len(self.descent_points),
        }


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great circle distance in nautical miles."""
    # Haversine formula
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)

    a = (math.sin(dLat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(dLon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))

    # Radius of Earth in nautical miles
    R = 3440.065
    return R * c


def get_fdb_callsigns() -> set:
    """Get all FDB callsigns from the database."""
    callsigns = set()

    if not DB_PATH.exists():
        log.warning(f"Database not found at {DB_PATH}")
        return callsigns

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT callsign FROM callsigns WHERE airline = 'Flydubai'")
        callsigns = {row[0] for row in cursor.fetchall()}
        conn.close()
        log.info(f"Found {len(callsigns)} FDB callsigns in database")
    except Exception as e:
        log.error(f"Error reading database: {e}")

    return callsigns


def scan_log_file(file_path: Path, fdb_callsigns: set, flights: Dict[str, FlightTrack]):
    """Scan a single log file for FDB flights."""
    log.info(f"Scanning {file_path.name}")

    records_processed = 0
    fdb_records = 0

    try:
        if file_path.suffix == '.gz':
            opener = lambda: gzip.open(file_path, 'rt', encoding='utf-8', errors='replace')
        else:
            opener = lambda: open(file_path, 'r', encoding='utf-8', errors='replace')

        with opener() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # Quick filter for FDB
                if 'FDB' not in line:
                    continue

                try:
                    record = json.loads(line)
                    records_processed += 1

                    flight = (record.get('flight') or '').strip().upper()
                    hex_code = record.get('hex')
                    aircraft_type = record.get('t')

                    # Filter for FDB callsign AND valid Flydubai aircraft type
                    if not flight.startswith('FDB') or not hex_code:
                        continue

                    # Skip if aircraft type is known and NOT a Flydubai type
                    if aircraft_type and aircraft_type not in FLYDUBAI_AIRCRAFT_TYPES:
                        continue

                    fdb_records += 1

                    # Create or get flight track
                    if hex_code not in flights:
                        flights[hex_code] = FlightTrack(
                            hex_code=hex_code,
                            callsign=flight,
                            registration=record.get('r'),
                            aircraft_type=aircraft_type
                        )

                    flights[hex_code].add_point(record)

                except json.JSONDecodeError:
                    continue

        if fdb_records > 0:
            log.info(f"  Found {fdb_records} FDB records")

    except Exception as e:
        log.error(f"Error scanning {file_path}: {e}")


def find_all_log_files() -> List[Path]:
    """Find all JSONL log files in the raw directory."""
    files = []

    # Check both organized and flat structure
    for pattern in ['**/*.jsonl.gz', '**/*.jsonl']:
        files.extend(RAW_LOG_DIR.glob(pattern))

    return sorted(files, key=lambda p: p.name)


def main():
    """Main analysis function."""
    log.info("=== FDB Descent Speed Analysis ===")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Get FDB callsigns from database
    fdb_callsigns = get_fdb_callsigns()

    # Find all log files
    log_files = find_all_log_files()
    log.info(f"Found {len(log_files)} log files to process")

    # Track flights currently in progress
    flights: Dict[str, FlightTrack] = {}

    # Open CSV file for streaming writes
    csv_path = OUTPUT_DIR / "fdb_descent_speeds.csv"
    fieldnames = [
        'callsign', 'registration', 'aircraft_type',
        'start_time', 'end_time', 'duration_mins',
        'start_altitude_ft', 'end_altitude_ft',
        'avg_tas_kt', 'avg_ias_kt', 'avg_gs_kt',
        'max_tas_kt', 'max_ias_kt', 'max_gs_kt',
        'min_tas_kt', 'min_ias_kt', 'min_gs_kt',
        'num_points'
    ]

    # Statistics accumulators
    all_stats = []
    flight_count = 0

    with open(csv_path, 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        # Scan all log files
        for i, log_file in enumerate(log_files):
            scan_log_file(log_file, fdb_callsigns, flights)

            # Every 10 files, flush completed descents to save memory
            if i % 10 == 0 and i > 0:
                completed_hex_codes = []
                for hex_code, flight_track in flights.items():
                    # Check if descent is complete (not currently descending)
                    if flight_track.descent_started and not flight_track.in_descent:
                        stats = flight_track.get_descent_stats()
                        if stats:
                            writer.writerow(stats)
                            all_stats.append(stats)
                            flight_count += 1
                        completed_hex_codes.append(hex_code)

                # Remove completed flights from memory
                for hex_code in completed_hex_codes:
                    del flights[hex_code]

                if completed_hex_codes:
                    log.info(f"Processed {flight_count} descents so far, {len(flights)} flights still tracking")

        # Final flush of remaining flights
        for flight_track in flights.values():
            if flight_track.descent_started:
                stats = flight_track.get_descent_stats()
                if stats:
                    writer.writerow(stats)
                    all_stats.append(stats)
                    flight_count += 1

    log.info(f"CSV written to {csv_path}")
    log.info(f"Found {flight_count} flights with valid descent data")

    if flight_count == 0:
        log.warning("No descent data found!")
        return

    # Calculate fleet averages
    fleet_avg_tas = sum(s['avg_tas_kt'] for s in all_stats) / len(all_stats)
    fleet_avg_ias = sum(s['avg_ias_kt'] for s in all_stats) / len(all_stats)
    fleet_avg_gs = sum(s['avg_gs_kt'] for s in all_stats) / len(all_stats)

    # Write summary
    summary_path = OUTPUT_DIR / "fleet_summary.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("FDB Fleet Descent Speed Analysis Summary\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Flights Analyzed: {len(all_stats)}\n")
        f.write(f"Altitude Range: Descent start to 15,000 ft\n\n")
        f.write("Fleet Average Descent Speeds:\n")
        f.write(f"  Average TAS: {fleet_avg_tas:.1f} knots\n")
        f.write(f"  Average IAS: {fleet_avg_ias:.1f} knots\n")
        f.write(f"  Average G/S: {fleet_avg_gs:.1f} knots\n\n")

        # Additional statistics
        f.write("Speed Ranges:\n")
        f.write(f"  TAS Range: {min(s['min_tas_kt'] for s in all_stats):.1f} - "
                f"{max(s['max_tas_kt'] for s in all_stats):.1f} knots\n")
        f.write(f"  IAS Range: {min(s['min_ias_kt'] for s in all_stats):.1f} - "
                f"{max(s['max_ias_kt'] for s in all_stats):.1f} knots\n")
        f.write(f"  G/S Range: {min(s['min_gs_kt'] for s in all_stats):.1f} - "
                f"{max(s['max_gs_kt'] for s in all_stats):.1f} knots\n\n")

        # Aircraft type breakdown
        by_type = defaultdict(list)
        for s in all_stats:
            by_type[s['aircraft_type']].append(s)

        f.write("By Aircraft Type:\n")
        for acft_type, type_stats in sorted(by_type.items()):
            avg_tas = sum(s['avg_tas_kt'] for s in type_stats) / len(type_stats)
            avg_ias = sum(s['avg_ias_kt'] for s in type_stats) / len(type_stats)
            avg_gs = sum(s['avg_gs_kt'] for s in type_stats) / len(type_stats)
            f.write(f"\n  {acft_type} ({len(type_stats)} flights):\n")
            f.write(f"    Avg TAS: {avg_tas:.1f} kt, Avg IAS: {avg_ias:.1f} kt, Avg G/S: {avg_gs:.1f} kt\n")

    log.info(f"Summary written to {summary_path}")
    log.info("\n=== Analysis Complete ===")
    log.info(f"Results saved to: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
