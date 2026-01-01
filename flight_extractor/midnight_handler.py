"""Handle flights that cross midnight boundaries."""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from .config import Config
from .file_scanner import FlightScanner

log = logging.getLogger(__name__)


class MidnightCrossoverHandler:
    """
    Detect and handle flights that cross midnight (00:00 UTC) boundaries.

    When a user requests flight FDB8876 for 2024-12-31, but the flight
    continues past midnight into 2025-01-01, this handler detects that
    and expands the date range to capture the complete flight.
    """

    def __init__(self, config: Optional[Config] = None, scanner: Optional[FlightScanner] = None):
        self.config = config or Config()
        self.scanner = scanner or FlightScanner(self.config)

        # Settings
        self.gap_threshold = self.config.flight_gap_threshold  # seconds
        self.max_crossover_hours = self.config.max_crossover_hours
        self.midnight_window = self.config.midnight_window_hours

    def detect_crossover(
        self,
        callsign: str,
        primary_date: date
    ) -> Tuple[date, date]:
        """
        Determine the actual date range for a flight.

        Strategy:
        1. Check if flight was active near end of primary_date (hours 21-23)
        2. If so, scan first hours of next day for continuation
        3. Also check if flight started on previous day (hours 21-23)
        4. Return the expanded (start_date, end_date) tuple

        Args:
            callsign: Flight callsign to search for
            primary_date: The date the user requested

        Returns:
            Tuple of (start_date, end_date) - may be same date if no crossover
        """
        log.info(f"Checking midnight crossover for {callsign} on {primary_date}")

        start_date = primary_date
        end_date = primary_date

        # Check for continuation AFTER midnight (into next day)
        end_date = self._check_forward_crossover(callsign, primary_date)

        # Check for start BEFORE midnight (from previous day)
        start_date = self._check_backward_crossover(callsign, primary_date)

        if start_date != primary_date or end_date != primary_date:
            log.info(f"Crossover detected: {callsign} spans {start_date} to {end_date}")
        else:
            log.debug(f"No crossover detected for {callsign} on {primary_date}")

        return (start_date, end_date)

    def _check_forward_crossover(self, callsign: str, primary_date: date) -> date:
        """Check if flight continues past midnight into the next day."""
        # Get records from end of primary date (last 3 hours)
        evening_files = self.scanner.find_files_for_hours(
            primary_date,
            start_hour=24 - self.midnight_window,
            end_hour=23
        )

        if not evening_files:
            return primary_date

        # Check if flight was active near midnight
        last_record = None
        for record in self.scanner.scan_files(evening_files, callsign=callsign):
            last_record = record

        if not last_record:
            return primary_date

        # Was the last record within the window of midnight?
        last_ts = last_record.get("_ts", 0)
        last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
        midnight = datetime.combine(primary_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

        time_to_midnight = (midnight - last_dt).total_seconds()

        if time_to_midnight > 1800:  # More than 30 minutes before midnight
            return primary_date

        log.debug(f"Flight {callsign} was active {time_to_midnight:.0f}s before midnight")

        # Check next day for continuation
        next_date = primary_date + timedelta(days=1)
        return self._find_end_date(callsign, next_date, last_ts)

    def _check_backward_crossover(self, callsign: str, primary_date: date) -> date:
        """Check if flight started on the previous day."""
        # Get records from start of primary date (first 3 hours)
        morning_files = self.scanner.find_files_for_hours(
            primary_date,
            start_hour=0,
            end_hour=self.midnight_window - 1
        )

        if not morning_files:
            return primary_date

        # Check if flight was active near start of day
        first_record = None
        for record in self.scanner.scan_files(morning_files, callsign=callsign):
            first_record = record
            break  # Just need the first one

        if not first_record:
            return primary_date

        # Was the first record within the window of midnight?
        first_ts = first_record.get("_ts", 0)
        first_dt = datetime.fromtimestamp(first_ts, tz=timezone.utc)
        midnight = datetime.combine(primary_date, datetime.min.time(), tzinfo=timezone.utc)

        time_after_midnight = (first_dt - midnight).total_seconds()

        if time_after_midnight > 1800:  # More than 30 minutes after midnight
            return primary_date

        log.debug(f"Flight {callsign} was active {time_after_midnight:.0f}s after midnight")

        # Check previous day for start
        prev_date = primary_date - timedelta(days=1)
        return self._find_start_date(callsign, prev_date, first_ts)

    def _find_end_date(self, callsign: str, check_date: date, last_known_ts: int) -> date:
        """
        Find the actual end date by scanning forward until flight ends.

        A flight is considered ended when there's a gap > threshold
        or we've scanned max_crossover_hours without finding records.
        """
        end_date = check_date - timedelta(days=1)  # Start with day before check_date
        current_date = check_date
        hours_checked = 0
        prev_ts = last_known_ts

        while hours_checked < self.max_crossover_hours:
            # Check one hour at a time
            hour = hours_checked % 24
            if hour == 0 and hours_checked > 0:
                current_date += timedelta(days=1)

            files = self.scanner.find_files_for_hours(current_date, hour, hour)

            if not files:
                hours_checked += 1
                continue

            found_any = False
            for record in self.scanner.scan_files(files, callsign=callsign):
                ts = record.get("_ts", 0)
                gap = ts - prev_ts

                if gap > self.gap_threshold:
                    # Gap too large - flight ended before this
                    log.debug(f"Flight gap of {gap}s detected, ending search")
                    return end_date

                prev_ts = ts
                end_date = current_date
                found_any = True

            if not found_any and hours_checked > 0:
                # No records in this hour after finding some - check gap
                hours_since = hours_checked
                if hours_since * 3600 > self.gap_threshold:
                    return end_date

            hours_checked += 1

        return end_date

    def _find_start_date(self, callsign: str, check_date: date, first_known_ts: int) -> date:
        """
        Find the actual start date by scanning backward until flight start.
        """
        start_date = check_date + timedelta(days=1)  # Start with day after check_date
        current_date = check_date
        hours_checked = 0
        next_ts = first_known_ts

        while hours_checked < self.max_crossover_hours:
            # Check one hour at a time, going backward
            hour = 23 - (hours_checked % 24)
            if hour == 23 and hours_checked > 0:
                current_date -= timedelta(days=1)

            files = self.scanner.find_files_for_hours(current_date, hour, hour)

            if not files:
                hours_checked += 1
                continue

            # Get all records for this hour and find the latest one
            records = list(self.scanner.scan_files(files, callsign=callsign))

            if not records:
                hours_checked += 1
                if hours_checked * 3600 > self.gap_threshold:
                    return start_date
                continue

            # Check if records connect to what we have
            last_record = records[-1]
            ts = last_record.get("_ts", 0)
            gap = next_ts - ts

            if gap > self.gap_threshold:
                # Gap too large - this is a different flight
                log.debug(f"Backward gap of {gap}s detected, stopping search")
                return start_date

            # Records connect - update our earliest known point
            first_record = records[0]
            next_ts = first_record.get("_ts", 0)
            start_date = current_date

            hours_checked += 1

        return start_date

    def is_same_flight(
        self,
        record1: dict,
        record2: dict,
        max_gap: Optional[int] = None
    ) -> bool:
        """
        Determine if two records belong to the same continuous flight.

        Criteria:
        - Same hex code (ICAO address)
        - Time gap < threshold
        - Optionally: position continuity
        """
        if max_gap is None:
            max_gap = self.gap_threshold

        # Must have same hex code
        hex1 = (record1.get("hex") or "").strip().lower()
        hex2 = (record2.get("hex") or "").strip().lower()

        if hex1 != hex2:
            return False

        # Check time gap
        ts1 = record1.get("_ts", 0)
        ts2 = record2.get("_ts", 0)
        gap = abs(ts2 - ts1)

        if gap > max_gap:
            return False

        return True

    def split_into_flights(self, records: List[dict]) -> List[List[dict]]:
        """
        Split a list of records into separate continuous flights.

        Useful when the same callsign is used multiple times in a day.
        """
        if not records:
            return []

        flights = []
        current_flight = [records[0]]

        for i in range(1, len(records)):
            if self.is_same_flight(records[i-1], records[i]):
                current_flight.append(records[i])
            else:
                # Start new flight
                flights.append(current_flight)
                current_flight = [records[i]]

        # Don't forget the last flight
        if current_flight:
            flights.append(current_flight)

        log.debug(f"Split {len(records)} records into {len(flights)} flight(s)")
        return flights
