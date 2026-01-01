"""Export flight data to CSV with logically grouped columns."""
import csv
import logging
from pathlib import Path
from typing import List, Optional

from flight_extractor.config import CSV_COLUMN_ORDER, CSV_COLUMN_GROUPS

log = logging.getLogger(__name__)


class CSVExporter:
    """
    Export flight data to CSV with logically grouped columns.

    Column order follows these groups:
    1. Timestamp (_ts, _ts_iso)
    2. Identity (hex, flight, squawk, category, etc.)
    3. Position (lat, lon, alt_baro, alt_geom)
    4. Velocity (gs, ias, tas, mach, rates)
    5. Direction (track, heading)
    6. Atmospheric (wind, temperature)
    7. Navigation (nav_altitude, nav_heading, nav_qnh)
    8. Data Quality (nic, nac, sil, rssi)
    9. Signal (messages, seen, distance)
    10. Source (mlat, tisb, poll)
    """

    def __init__(self, column_order: Optional[List[str]] = None):
        """
        Initialize exporter.

        Args:
            column_order: Custom column order, or use default CSV_COLUMN_ORDER
        """
        self.column_order = column_order or CSV_COLUMN_ORDER

    def export(
        self,
        records: List[dict],
        output_path: Path,
        include_header_comments: bool = True
    ) -> Path:
        """
        Export records to CSV file.

        Args:
            records: List of flight data records
            output_path: Path to output CSV file
            include_header_comments: Whether to include column group comments

        Returns:
            Path to created CSV file
        """
        if not records:
            log.warning("No records to export")
            return output_path

        # Determine which columns actually have data
        used_columns = self._find_used_columns(records)

        # Filter column order to only include used columns
        columns = [c for c in self.column_order if c in used_columns]

        # Add any extra columns not in our predefined order
        extra_cols = used_columns - set(columns)
        columns.extend(sorted(extra_cols))

        log.info(f"Exporting {len(records)} records with {len(columns)} columns to {output_path}")

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            if include_header_comments:
                f.write(self._generate_header_comments())

            writer = csv.DictWriter(
                f,
                fieldnames=columns,
                extrasaction="ignore"
            )
            writer.writeheader()

            for record in records:
                # Clean up the record for CSV output
                clean_record = self._clean_record(record)
                writer.writerow(clean_record)

        log.info(f"CSV export complete: {output_path}")
        return output_path

    def _find_used_columns(self, records: List[dict]) -> set:
        """Find all columns that have at least one non-null value."""
        used = set()
        for record in records:
            for key, value in record.items():
                if value is not None and value != "":
                    used.add(key)
        return used

    def _clean_record(self, record: dict) -> dict:
        """Clean a record for CSV output."""
        clean = {}
        for key, value in record.items():
            if value is None:
                clean[key] = ""
            elif isinstance(value, bool):
                clean[key] = "1" if value else "0"
            elif isinstance(value, (list, dict)):
                clean[key] = str(value)
            else:
                clean[key] = value
        return clean

    def _generate_header_comments(self) -> str:
        """Generate header comments explaining column groups."""
        lines = [
            "# ADS-B Flight Data Export",
            "# Column Groups:",
        ]

        for group_name, columns in CSV_COLUMN_GROUPS.items():
            cols_str = ", ".join(columns)
            lines.append(f"#   {group_name}: {cols_str}")

        lines.append("#")
        return "\n".join(lines) + "\n"

    def export_minimal(
        self,
        records: List[dict],
        output_path: Path
    ) -> Path:
        """
        Export a minimal CSV with just essential columns.

        Useful for quick analysis or smaller file size.
        """
        minimal_columns = [
            "_ts_iso",
            "flight",
            "lat", "lon",
            "alt_baro",
            "gs",
            "track",
            "baro_rate",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=minimal_columns,
                extrasaction="ignore"
            )
            writer.writeheader()

            for record in records:
                clean_record = self._clean_record(record)
                writer.writerow(clean_record)

        return output_path
