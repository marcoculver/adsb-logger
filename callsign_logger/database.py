"""SQLite database for callsign tracking."""
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .config import DEFAULT_DB_PATH

log = logging.getLogger(__name__)


class CallsignDatabase:
    """SQLite database for tracking callsigns and flight data."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Main callsigns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS callsigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    callsign TEXT NOT NULL,
                    flight_number TEXT,
                    route TEXT,
                    origin TEXT,
                    destination TEXT,
                    airline TEXT,
                    hex_code TEXT,
                    aircraft_type TEXT,
                    registration TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    sighting_count INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(callsign)
                )
            """)

            # Sightings table for frequency/schedule analysis
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sightings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    callsign TEXT NOT NULL,
                    seen_at TEXT NOT NULL,
                    day_of_week INTEGER,
                    hour_of_day INTEGER,
                    hex_code TEXT,
                    FOREIGN KEY (callsign) REFERENCES callsigns(callsign)
                )
            """)

            # Route cache table (for API responses)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS route_cache (
                    callsign TEXT PRIMARY KEY,
                    flight_number TEXT,
                    route TEXT,
                    origin TEXT,
                    destination TEXT,
                    cached_at TEXT NOT NULL
                )
            """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_callsigns_callsign ON callsigns(callsign)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_callsigns_airline ON callsigns(airline)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sightings_callsign ON sightings(callsign)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sightings_dow ON sightings(day_of_week)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sightings_hour ON sightings(hour_of_day)")

            log.info(f"Database initialized at {self.db_path}")

    def upsert_callsign(
        self,
        callsign: str,
        airline: str,
        hex_code: Optional[str] = None,
        aircraft_type: Optional[str] = None,
        registration: Optional[str] = None,
        flight_number: Optional[str] = None,
        route: Optional[str] = None,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
    ) -> bool:
        """
        Insert or update a callsign record.

        Returns True if this is a new callsign, False if updated.
        """
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Check if exists
            cursor.execute("SELECT id, sighting_count FROM callsigns WHERE callsign = ?", (callsign,))
            row = cursor.fetchone()

            if row:
                # Update existing
                count = row["sighting_count"] + 1
                cursor.execute("""
                    UPDATE callsigns SET
                        last_seen = ?,
                        sighting_count = ?,
                        updated_at = ?,
                        hex_code = COALESCE(?, hex_code),
                        aircraft_type = COALESCE(?, aircraft_type),
                        registration = COALESCE(?, registration),
                        flight_number = COALESCE(?, flight_number),
                        route = COALESCE(?, route),
                        origin = COALESCE(?, origin),
                        destination = COALESCE(?, destination)
                    WHERE callsign = ?
                """, (now, count, now, hex_code, aircraft_type, registration,
                      flight_number, route, origin, destination, callsign))
                is_new = False
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO callsigns (
                        callsign, airline, hex_code, aircraft_type, registration,
                        flight_number, route, origin, destination,
                        first_seen, last_seen, sighting_count, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (callsign, airline, hex_code, aircraft_type, registration,
                      flight_number, route, origin, destination,
                      now, now, now, now))
                is_new = True
                log.info(f"New callsign: {callsign} ({airline})")

            return is_new

    def add_sighting(self, callsign: str, seen_at: datetime, hex_code: Optional[str] = None):
        """Record a sighting for schedule analysis."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sightings (callsign, seen_at, day_of_week, hour_of_day, hex_code)
                VALUES (?, ?, ?, ?, ?)
            """, (
                callsign,
                seen_at.isoformat(),
                seen_at.weekday(),  # 0=Monday, 6=Sunday
                seen_at.hour,
                hex_code
            ))

    def get_callsign(self, callsign: str) -> Optional[Dict[str, Any]]:
        """Get a specific callsign record."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM callsigns WHERE callsign = ?", (callsign,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_callsigns(self, airline: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all callsigns, optionally filtered by airline."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if airline:
                cursor.execute(
                    "SELECT * FROM callsigns WHERE airline = ? ORDER BY sighting_count DESC",
                    (airline,)
                )
            else:
                cursor.execute("SELECT * FROM callsigns ORDER BY sighting_count DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_schedule(self, callsign: str) -> Dict[str, Any]:
        """
        Get schedule pattern for a callsign.

        Returns frequency by day of week and hour.
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Count by day of week
            cursor.execute("""
                SELECT day_of_week, COUNT(*) as count
                FROM sightings WHERE callsign = ?
                GROUP BY day_of_week ORDER BY day_of_week
            """, (callsign,))
            by_day = {row["day_of_week"]: row["count"] for row in cursor.fetchall()}

            # Count by hour
            cursor.execute("""
                SELECT hour_of_day, COUNT(*) as count
                FROM sightings WHERE callsign = ?
                GROUP BY hour_of_day ORDER BY hour_of_day
            """, (callsign,))
            by_hour = {row["hour_of_day"]: row["count"] for row in cursor.fetchall()}

            # Total sightings
            cursor.execute(
                "SELECT COUNT(*) as total FROM sightings WHERE callsign = ?",
                (callsign,)
            )
            total = cursor.fetchone()["total"]

            return {
                "callsign": callsign,
                "total_sightings": total,
                "by_day_of_week": by_day,
                "by_hour": by_hour,
            }

    def get_cached_route(self, callsign: str, max_age_hours: int = 24) -> Optional[Dict[str, Any]]:
        """Get cached route data if not expired."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM route_cache WHERE callsign = ?",
                (callsign,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            # Check if expired
            cached_at = datetime.fromisoformat(row["cached_at"])
            if datetime.now(timezone.utc) - cached_at > timedelta(hours=max_age_hours):
                return None

            return dict(row)

    def cache_route(
        self,
        callsign: str,
        flight_number: Optional[str],
        route: Optional[str],
        origin: Optional[str],
        destination: Optional[str]
    ):
        """Cache route data from API."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO route_cache
                (callsign, flight_number, route, origin, destination, cached_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (callsign, flight_number, route, origin, destination, now))

    def export_csv(self, output_path: Path, airline: Optional[str] = None) -> Path:
        """Export callsigns to CSV file."""
        import csv

        callsigns = self.get_all_callsigns(airline)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            if not callsigns:
                f.write("No data\n")
                return output_path

            writer = csv.DictWriter(f, fieldnames=[
                "callsign", "flight_number", "route", "origin", "destination",
                "airline", "hex_code", "aircraft_type", "registration",
                "first_seen", "last_seen", "sighting_count"
            ])
            writer.writeheader()

            for cs in callsigns:
                writer.writerow({
                    "callsign": cs["callsign"],
                    "flight_number": cs.get("flight_number") or "",
                    "route": cs.get("route") or "",
                    "origin": cs.get("origin") or "",
                    "destination": cs.get("destination") or "",
                    "airline": cs["airline"],
                    "hex_code": cs.get("hex_code") or "",
                    "aircraft_type": cs.get("aircraft_type") or "",
                    "registration": cs.get("registration") or "",
                    "first_seen": cs["first_seen"],
                    "last_seen": cs["last_seen"],
                    "sighting_count": cs["sighting_count"],
                })

        log.info(f"Exported {len(callsigns)} callsigns to {output_path}")
        return output_path

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as count FROM callsigns")
            total_callsigns = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM sightings")
            total_sightings = cursor.fetchone()["count"]

            cursor.execute("""
                SELECT airline, COUNT(*) as count
                FROM callsigns GROUP BY airline
            """)
            by_airline = {row["airline"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("""
                SELECT callsign, sighting_count
                FROM callsigns ORDER BY sighting_count DESC LIMIT 10
            """)
            top_callsigns = [(row["callsign"], row["sighting_count"]) for row in cursor.fetchall()]

            return {
                "total_callsigns": total_callsigns,
                "total_sightings": total_sightings,
                "by_airline": by_airline,
                "top_callsigns": top_callsigns,
            }
