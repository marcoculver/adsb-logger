"""Main flight data extraction orchestrator."""
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from .config import Config
from .file_scanner import FlightScanner
from .midnight_handler import MidnightCrossoverHandler

log = logging.getLogger(__name__)


@dataclass
class FlightMetadata:
    """Metadata about an extracted flight."""
    callsign: str
    hex_code: Optional[str] = None
    registration: Optional[str] = None
    aircraft_type: Optional[str] = None
    operator: Optional[str] = None

    # Time bounds
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    duration_minutes: float = 0.0

    # Position bounds
    first_position: Optional[Dict[str, float]] = None
    last_position: Optional[Dict[str, float]] = None
    max_altitude_ft: Optional[float] = None
    min_altitude_ft: Optional[float] = None
    max_ground_speed_kts: Optional[float] = None

    # Extraction info
    requested_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    crossover_detected: bool = False
    files_scanned: int = 0
    records_extracted: int = 0
    extraction_time_seconds: float = 0.0


@dataclass
class FlightData:
    """Complete extracted flight data."""
    metadata: FlightMetadata
    records: List[dict] = field(default_factory=list)
    output_dir: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "callsign": self.metadata.callsign,
            "hex": self.metadata.hex_code,
            "registration": self.metadata.registration,
            "aircraft_type": self.metadata.aircraft_type,
            "operator": self.metadata.operator,
            "extraction": {
                "requested_date": self.metadata.requested_date.isoformat() if self.metadata.requested_date else None,
                "actual_start": self.metadata.first_seen.isoformat() if self.metadata.first_seen else None,
                "actual_end": self.metadata.last_seen.isoformat() if self.metadata.last_seen else None,
                "crossover_detected": self.metadata.crossover_detected,
                "files_scanned": self.metadata.files_scanned,
                "records_extracted": self.metadata.records_extracted,
                "extraction_time_seconds": round(self.metadata.extraction_time_seconds, 2),
            },
            "flight": {
                "duration_minutes": round(self.metadata.duration_minutes, 1),
                "first_position": self.metadata.first_position,
                "last_position": self.metadata.last_position,
                "max_altitude_ft": self.metadata.max_altitude_ft,
                "min_altitude_ft": self.metadata.min_altitude_ft,
                "max_ground_speed_kts": self.metadata.max_ground_speed_kts,
            },
            "output_dir": str(self.output_dir) if self.output_dir else None,
        }


class FlightExtractor:
    """Main orchestrator for flight data extraction."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.scanner = FlightScanner(self.config)
        self.crossover_handler = MidnightCrossoverHandler(self.config, self.scanner)

    def extract(
        self,
        callsign: str,
        target_date: date,
        check_crossover: bool = True,
        create_output_dir: bool = True,
        progress_callback: Optional[callable] = None
    ) -> FlightData:
        """
        Extract complete flight data for a callsign on a date.

        Args:
            callsign: Flight callsign (e.g., "FDB8876")
            target_date: Primary date to search
            check_crossover: Whether to check for midnight crossover
            create_output_dir: Whether to create output directory
            progress_callback: Optional callback(current, total, message)

        Returns:
            FlightData with all records and metadata
        """
        import time
        start_time = time.monotonic()

        callsign = callsign.strip().upper()
        log.info(f"Extracting flight data for {callsign} on {target_date}")

        metadata = FlightMetadata(
            callsign=callsign,
            requested_date=target_date,
        )

        # Determine date range (handle midnight crossover)
        if check_crossover:
            start_date, end_date = self.crossover_handler.detect_crossover(callsign, target_date)
            metadata.actual_start_date = start_date
            metadata.actual_end_date = end_date
            metadata.crossover_detected = (start_date != target_date or end_date != target_date)
        else:
            start_date = end_date = target_date
            metadata.actual_start_date = target_date
            metadata.actual_end_date = target_date

        # Collect all files
        all_files = []
        current = start_date
        while current <= end_date:
            all_files.extend(self.scanner.find_files_for_date(current))
            current += timedelta(days=1)

        all_files = sorted(set(all_files), key=lambda p: p.name)
        metadata.files_scanned = len(all_files)

        log.info(f"Scanning {len(all_files)} files from {start_date} to {end_date}")

        # Extract records
        records = self.scanner.scan_files(all_files, callsign=callsign, progress_callback=progress_callback)
        metadata.records_extracted = len(records)

        if not records:
            log.warning(f"No records found for {callsign} on {target_date}")
            metadata.extraction_time_seconds = time.monotonic() - start_time
            return FlightData(metadata=metadata, records=[])

        # Compute metadata from records
        self._compute_metadata(metadata, records)

        # Create output directory
        output_dir = None
        if create_output_dir:
            output_dir = self.create_output_directory(callsign, target_date)

        metadata.extraction_time_seconds = time.monotonic() - start_time

        flight_data = FlightData(
            metadata=metadata,
            records=records,
            output_dir=output_dir
        )

        log.info(
            f"Extracted {len(records)} records for {callsign}: "
            f"{metadata.duration_minutes:.1f} min, max alt {metadata.max_altitude_ft} ft"
        )

        return flight_data

    def _compute_metadata(self, metadata: FlightMetadata, records: List[dict]):
        """Compute flight metadata from extracted records."""
        if not records:
            return

        first = records[0]
        last = records[-1]

        # Time bounds
        first_ts = first.get("_ts")
        last_ts = last.get("_ts")

        if first_ts:
            metadata.first_seen = datetime.fromtimestamp(first_ts, tz=timezone.utc)
        if last_ts:
            metadata.last_seen = datetime.fromtimestamp(last_ts, tz=timezone.utc)

        if first_ts and last_ts:
            metadata.duration_minutes = (last_ts - first_ts) / 60.0

        # Identity from first record with data
        for r in records:
            if not metadata.hex_code and r.get("hex"):
                metadata.hex_code = r.get("hex", "").strip().lower()
            if not metadata.registration and r.get("r"):
                metadata.registration = r.get("r", "").strip()
            if not metadata.aircraft_type and r.get("t"):
                metadata.aircraft_type = r.get("t", "").strip()
            if not metadata.operator and r.get("ownOp"):
                metadata.operator = r.get("ownOp", "").strip()

            if all([metadata.hex_code, metadata.registration, metadata.aircraft_type, metadata.operator]):
                break

        # Position bounds
        first_pos = self._find_first_position(records)
        last_pos = self._find_last_position(records)

        if first_pos:
            metadata.first_position = {"lat": first_pos[0], "lon": first_pos[1]}
        if last_pos:
            metadata.last_position = {"lat": last_pos[0], "lon": last_pos[1]}

        # Altitude and speed extremes
        max_alt = None
        min_alt = None
        max_gs = None

        for r in records:
            alt = r.get("alt_baro")
            if alt is not None and alt != "ground":
                try:
                    alt_num = float(alt)
                    if max_alt is None or alt_num > max_alt:
                        max_alt = alt_num
                    if min_alt is None or alt_num < min_alt:
                        min_alt = alt_num
                except (ValueError, TypeError):
                    pass

            gs = r.get("gs")
            if gs is not None:
                try:
                    gs_num = float(gs)
                    if max_gs is None or gs_num > max_gs:
                        max_gs = gs_num
                except (ValueError, TypeError):
                    pass

        metadata.max_altitude_ft = max_alt
        metadata.min_altitude_ft = min_alt
        metadata.max_ground_speed_kts = max_gs

    def _find_first_position(self, records: List[dict]) -> Optional[tuple]:
        """Find first record with valid lat/lon."""
        for r in records:
            lat = r.get("lat")
            lon = r.get("lon")
            if lat is not None and lon is not None:
                return (lat, lon)
        return None

    def _find_last_position(self, records: List[dict]) -> Optional[tuple]:
        """Find last record with valid lat/lon."""
        for r in reversed(records):
            lat = r.get("lat")
            lon = r.get("lon")
            if lat is not None and lon is not None:
                return (lat, lon)
        return None

    def create_output_directory(self, callsign: str, target_date: date) -> Path:
        """
        Create and return output directory for extraction results.

        Format: /output_dir/YYYYMMDD_CALLSIGN/
        """
        dir_name = f"{target_date.strftime('%Y%m%d')}_{callsign.upper()}"
        output_path = self.config.output_dir / dir_name

        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "charts").mkdir(exist_ok=True)

        return output_path

    def save_metadata(self, flight_data: FlightData) -> Path:
        """Save flight metadata to JSON file."""
        if not flight_data.output_dir:
            raise ValueError("No output directory set")

        metadata_path = flight_data.output_dir / "metadata.json"

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(flight_data.to_dict(), f, indent=2, default=str)

        log.info(f"Saved metadata to {metadata_path}")
        return metadata_path

    def generate_summary(self, flight_data: FlightData) -> str:
        """Generate human-readable flight summary."""
        m = flight_data.metadata
        lines = [
            f"Flight Summary: {m.callsign}",
            "=" * 40,
            "",
            f"Aircraft: {m.aircraft_type or 'Unknown'} ({m.registration or 'N/A'})",
            f"Operator: {m.operator or 'Unknown'}",
            f"ICAO Hex: {m.hex_code or 'Unknown'}",
            "",
            f"First Seen: {m.first_seen.strftime('%Y-%m-%d %H:%M:%S UTC') if m.first_seen else 'N/A'}",
            f"Last Seen:  {m.last_seen.strftime('%Y-%m-%d %H:%M:%S UTC') if m.last_seen else 'N/A'}",
            f"Duration:   {m.duration_minutes:.1f} minutes",
            "",
        ]

        if m.first_position:
            lines.append(f"Start: {m.first_position['lat']:.4f}, {m.first_position['lon']:.4f}")
        if m.last_position:
            lines.append(f"End:   {m.last_position['lat']:.4f}, {m.last_position['lon']:.4f}")

        lines.extend([
            "",
            f"Max Altitude:     {m.max_altitude_ft:.0f} ft" if m.max_altitude_ft else "Max Altitude: N/A",
            f"Min Altitude:     {m.min_altitude_ft:.0f} ft" if m.min_altitude_ft else "Min Altitude: N/A",
            f"Max Ground Speed: {m.max_ground_speed_kts:.0f} kts" if m.max_ground_speed_kts else "Max Speed: N/A",
            "",
            "Extraction Info:",
            f"  Requested Date: {m.requested_date}",
            f"  Crossover:      {'Yes' if m.crossover_detected else 'No'}",
            f"  Files Scanned:  {m.files_scanned}",
            f"  Records:        {m.records_extracted}",
            f"  Time:           {m.extraction_time_seconds:.2f}s",
        ])

        return "\n".join(lines)

    def save_summary(self, flight_data: FlightData) -> Path:
        """Save human-readable summary to text file."""
        if not flight_data.output_dir:
            raise ValueError("No output directory set")

        summary = self.generate_summary(flight_data)
        summary_path = flight_data.output_dir / "summary.txt"

        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)

        log.info(f"Saved summary to {summary_path}")
        return summary_path
