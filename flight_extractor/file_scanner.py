"""Efficient scanning of JSONL.gz log files for flight data."""
import gzip
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Generator, List, Optional, Set, Tuple

from .config import Config, FILE_PREFIX, FILE_SUFFIX_GZ, FILE_SUFFIX_JSONL

log = logging.getLogger(__name__)


class FlightScanner:
    """Efficiently scan JSONL.gz files for specific flight data."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.log_dir = self.config.log_dir

    def find_files_for_date(self, target_date: date) -> List[Path]:
        """
        Find all hourly log files for a given date (hours 00-23).

        Checks both organized structure (YYYY/MM/DD/) and flat structure.
        Returns files sorted by hour.
        """
        files = []

        # Check organized structure: YYYY/MM/DD/
        organized_dir = self.log_dir / f"{target_date.year}" / f"{target_date.month:02d}" / f"{target_date.day:02d}"
        if organized_dir.exists():
            files.extend(organized_dir.glob(f"{FILE_PREFIX}*.jsonl.gz"))
            files.extend(organized_dir.glob(f"{FILE_PREFIX}*.jsonl"))

        # Also check flat structure (files not yet organized)
        date_prefix = target_date.strftime("%Y-%m-%d")
        files.extend(self.log_dir.glob(f"{FILE_PREFIX}{date_prefix}_*.jsonl.gz"))
        files.extend(self.log_dir.glob(f"{FILE_PREFIX}{date_prefix}_*.jsonl"))

        # Remove duplicates and sort by filename (which sorts by hour)
        unique_files = list(set(files))
        unique_files.sort(key=lambda p: p.name)

        return unique_files

    def find_files_for_hours(
        self,
        target_date: date,
        start_hour: int = 0,
        end_hour: int = 23
    ) -> List[Path]:
        """Find log files for specific hours on a date."""
        all_files = self.find_files_for_date(target_date)

        filtered = []
        for f in all_files:
            # Extract hour from filename: adsb_state_2024-12-31_14.jsonl.gz
            try:
                hour_str = f.stem.replace(".jsonl", "").split("_")[-1]
                hour = int(hour_str)
                if start_hour <= hour <= end_hour:
                    filtered.append(f)
            except (ValueError, IndexError):
                log.warning(f"Could not parse hour from filename: {f.name}")
                continue

        return filtered

    def scan_file(
        self,
        file_path: Path,
        callsign: Optional[str] = None,
        hex_code: Optional[str] = None
    ) -> Generator[dict, None, None]:
        """
        Stream records matching callsign or hex from a log file.

        Uses streaming to minimize memory usage.
        Performs quick string check before JSON parsing for efficiency.
        """
        if not file_path.exists():
            log.warning(f"File not found: {file_path}")
            return

        # Normalize search terms
        search_callsign = callsign.strip().upper() if callsign else None
        search_hex = hex_code.strip().lower() if hex_code else None

        # Quick string to search for before parsing
        quick_check = search_callsign or search_hex

        try:
            # Choose opener based on extension
            if file_path.suffix == ".gz" or file_path.name.endswith(".jsonl.gz"):
                opener = lambda: gzip.open(file_path, "rt", encoding="utf-8", errors="replace")
            else:
                opener = lambda: open(file_path, "r", encoding="utf-8", errors="replace")

            with opener() as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    # Quick string check before parsing JSON
                    if quick_check and quick_check.lower() not in line.lower():
                        continue

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        log.debug(f"JSON parse error in {file_path.name}:{line_num}: {e}")
                        continue

                    # Verify match
                    if search_callsign:
                        flight = (record.get("flight") or "").strip().upper()
                        if flight != search_callsign:
                            continue
                    if search_hex:
                        hex_val = (record.get("hex") or "").strip().lower()
                        if hex_val != search_hex:
                            continue

                    yield record

        except Exception as e:
            log.error(f"Error reading {file_path}: {e}")

    def scan_files(
        self,
        files: List[Path],
        callsign: Optional[str] = None,
        hex_code: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> List[dict]:
        """
        Scan multiple files and collect all matching records.

        Returns records sorted by timestamp.
        """
        all_records = []

        for i, file_path in enumerate(files):
            if progress_callback:
                progress_callback(i + 1, len(files), file_path.name)

            for record in self.scan_file(file_path, callsign, hex_code):
                all_records.append(record)

        # Sort by timestamp
        all_records.sort(key=lambda r: r.get("_ts", 0))

        return all_records

    def extract_flight_data(
        self,
        callsign: str,
        start_date: date,
        end_date: Optional[date] = None,
        hex_code: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> List[dict]:
        """
        Extract all data for a flight across a date range.

        Args:
            callsign: Flight callsign (e.g., "FDB8876")
            start_date: Start date for extraction
            end_date: End date (inclusive), defaults to start_date
            hex_code: Optional ICAO hex code to also match
            progress_callback: Optional callback(current, total, filename)

        Returns:
            List of records sorted by timestamp
        """
        if end_date is None:
            end_date = start_date

        # Collect all files in date range
        all_files = []
        current = start_date
        while current <= end_date:
            all_files.extend(self.find_files_for_date(current))
            current += timedelta(days=1)

        # Remove duplicates and sort
        all_files = sorted(set(all_files), key=lambda p: p.name)

        log.info(f"Scanning {len(all_files)} files for {callsign}")

        return self.scan_files(all_files, callsign, hex_code, progress_callback)

    def get_unique_callsigns(
        self,
        target_date: date,
        hours: Optional[Tuple[int, int]] = None
    ) -> Set[str]:
        """
        Get all unique callsigns seen on a date.

        Useful for listing available flights.
        """
        if hours:
            files = self.find_files_for_hours(target_date, hours[0], hours[1])
        else:
            files = self.find_files_for_date(target_date)

        callsigns = set()

        for file_path in files:
            try:
                if file_path.suffix == ".gz" or file_path.name.endswith(".jsonl.gz"):
                    opener = lambda p=file_path: gzip.open(p, "rt", encoding="utf-8")
                else:
                    opener = lambda p=file_path: open(p, "r", encoding="utf-8")

                with opener() as f:
                    for line in f:
                        if '"flight"' not in line:
                            continue
                        try:
                            record = json.loads(line)
                            flight = (record.get("flight") or "").strip()
                            if flight:
                                callsigns.add(flight)
                        except json.JSONDecodeError:
                            continue

            except Exception as e:
                log.warning(f"Error scanning {file_path.name} for callsigns: {e}")

        return callsigns

    def check_flight_exists(
        self,
        callsign: str,
        target_date: date,
        hours: Optional[Tuple[int, int]] = None
    ) -> bool:
        """Quick check if a flight exists on a date (stops at first match)."""
        if hours:
            files = self.find_files_for_hours(target_date, hours[0], hours[1])
        else:
            files = self.find_files_for_date(target_date)

        for file_path in files:
            for _ in self.scan_file(file_path, callsign=callsign):
                return True  # Found at least one record

        return False
