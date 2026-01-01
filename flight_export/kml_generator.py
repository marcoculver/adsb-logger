"""Generate KML flight paths for Google Earth."""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import simplekml
    HAS_SIMPLEKML = True
except ImportError:
    HAS_SIMPLEKML = False

from flight_extractor.config import KML_ALTITUDE_COLORS

log = logging.getLogger(__name__)


class KMLGenerator:
    """
    Generate 3D KML flight paths for Google Earth.

    Features:
    - 3D flight path with altitude
    - Color coding by altitude bands
    - Placemark for start, end, and max altitude points
    - Time-stamped path for playback
    """

    # Altitude bands (ft) -> KML color (aabbggrr)
    ALTITUDE_COLORS = [
        (0, "ff0000ff"),       # Red: ground
        (10000, "ff00a5ff"),   # Orange: 0-10k
        (20000, "ff00ffff"),   # Yellow: 10k-20k
        (30000, "ff00ff00"),   # Green: 20k-30k
        (40000, "ffff7f00"),   # Cyan: 30k-40k
        (50000, "ffff0000"),   # Blue: 40k+
    ]

    def __init__(self):
        if not HAS_SIMPLEKML:
            log.warning("simplekml not installed - KML generation will use fallback")

    def generate(
        self,
        records: List[dict],
        output_path: Path,
        callsign: str,
        flight_date: Optional[str] = None
    ) -> Path:
        """
        Generate KML file with 3D flight path.

        Args:
            records: Flight data records with lat, lon, alt_baro
            output_path: Path to output KML file
            callsign: Flight callsign for naming
            flight_date: Optional date string for title

        Returns:
            Path to created KML file
        """
        # Filter records with valid positions
        positioned = [
            r for r in records
            if r.get("lat") is not None and r.get("lon") is not None
        ]

        if not positioned:
            log.warning("No positioned records for KML generation")
            return output_path

        log.info(f"Generating KML with {len(positioned)} points")

        if HAS_SIMPLEKML:
            return self._generate_with_simplekml(positioned, output_path, callsign, flight_date)
        else:
            return self._generate_fallback(positioned, output_path, callsign, flight_date)

    def _generate_with_simplekml(
        self,
        records: List[dict],
        output_path: Path,
        callsign: str,
        flight_date: Optional[str]
    ) -> Path:
        """Generate KML using simplekml library."""
        kml = simplekml.Kml()

        title = f"{callsign}"
        if flight_date:
            title += f" - {flight_date}"

        kml.document.name = title

        # Create line style
        line_style = simplekml.Style()
        line_style.linestyle.width = 3
        line_style.linestyle.color = simplekml.Color.cyan

        # Build coordinate list
        coords = []
        for r in records:
            lat = r.get("lat")
            lon = r.get("lon")
            alt = self._get_altitude_meters(r)
            coords.append((lon, lat, alt))

        # Create the flight path line
        linestring = kml.newlinestring(name="Flight Path")
        linestring.coords = coords
        linestring.altitudemode = simplekml.AltitudeMode.absolute
        linestring.style = line_style
        linestring.extrude = 0
        linestring.tessellate = 1

        # Add start point
        start = records[0]
        start_point = kml.newpoint(name="Start")
        start_point.coords = [(start["lon"], start["lat"], self._get_altitude_meters(start))]
        start_point.style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"
        start_point.style.iconstyle.scale = 1.0
        if start.get("_ts_iso"):
            start_point.description = f"Time: {start['_ts_iso']}"

        # Add end point
        end = records[-1]
        end_point = kml.newpoint(name="End")
        end_point.coords = [(end["lon"], end["lat"], self._get_altitude_meters(end))]
        end_point.style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/red-circle.png"
        end_point.style.iconstyle.scale = 1.0
        if end.get("_ts_iso"):
            end_point.description = f"Time: {end['_ts_iso']}"

        # Add max altitude point
        max_alt_record = max(records, key=lambda r: self._get_altitude_ft(r) or 0)
        if self._get_altitude_ft(max_alt_record):
            max_point = kml.newpoint(name=f"Max Alt: {self._get_altitude_ft(max_alt_record):.0f} ft")
            max_point.coords = [(
                max_alt_record["lon"],
                max_alt_record["lat"],
                self._get_altitude_meters(max_alt_record)
            )]
            max_point.style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/blu-circle.png"
            max_point.style.iconstyle.scale = 0.8

        kml.save(str(output_path))
        log.info(f"KML saved to {output_path}")
        return output_path

    def _generate_fallback(
        self,
        records: List[dict],
        output_path: Path,
        callsign: str,
        flight_date: Optional[str]
    ) -> Path:
        """Generate KML manually without simplekml."""
        title = f"{callsign}"
        if flight_date:
            title += f" - {flight_date}"

        # Build coordinates string
        coords_lines = []
        for r in records:
            lat = r.get("lat")
            lon = r.get("lon")
            alt = self._get_altitude_meters(r)
            coords_lines.append(f"{lon},{lat},{alt}")

        coords_str = " ".join(coords_lines)

        # Start and end points
        start = records[0]
        end = records[-1]

        kml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{title}</name>
    <Style id="flightPath">
      <LineStyle>
        <color>ffffff00</color>
        <width>3</width>
      </LineStyle>
    </Style>
    <Style id="startIcon">
      <IconStyle>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/grn-circle.png</href></Icon>
      </IconStyle>
    </Style>
    <Style id="endIcon">
      <IconStyle>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href></Icon>
      </IconStyle>
    </Style>

    <Placemark>
      <name>Flight Path</name>
      <styleUrl>#flightPath</styleUrl>
      <LineString>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>{coords_str}</coordinates>
      </LineString>
    </Placemark>

    <Placemark>
      <name>Start</name>
      <description>Time: {start.get('_ts_iso', 'N/A')}</description>
      <styleUrl>#startIcon</styleUrl>
      <Point>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>{start['lon']},{start['lat']},{self._get_altitude_meters(start)}</coordinates>
      </Point>
    </Placemark>

    <Placemark>
      <name>End</name>
      <description>Time: {end.get('_ts_iso', 'N/A')}</description>
      <styleUrl>#endIcon</styleUrl>
      <Point>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>{end['lon']},{end['lat']},{self._get_altitude_meters(end)}</coordinates>
      </Point>
    </Placemark>

  </Document>
</kml>'''

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(kml_content)

        log.info(f"KML saved to {output_path} (fallback method)")
        return output_path

    def _get_altitude_ft(self, record: dict) -> Optional[float]:
        """Get altitude in feet from record."""
        alt = record.get("alt_baro")
        if alt is None or alt == "ground":
            return 0
        try:
            return float(alt)
        except (ValueError, TypeError):
            return 0

    def _get_altitude_meters(self, record: dict) -> float:
        """Get altitude in meters from record (KML uses meters)."""
        alt_ft = self._get_altitude_ft(record) or 0
        return alt_ft * 0.3048  # feet to meters

    def altitude_to_color(self, altitude_ft: float) -> str:
        """Map altitude to KML color (aabbggrr format)."""
        for threshold, color in reversed(self.ALTITUDE_COLORS):
            if altitude_ft >= threshold:
                return color
        return self.ALTITUDE_COLORS[0][1]

    def generate_segmented(
        self,
        records: List[dict],
        output_path: Path,
        callsign: str,
        flight_date: Optional[str] = None
    ) -> Path:
        """
        Generate KML with altitude-colored segments.

        Creates separate line segments colored by altitude band.
        More visually informative but larger file.
        """
        if not HAS_SIMPLEKML:
            return self.generate(records, output_path, callsign, flight_date)

        positioned = [
            r for r in records
            if r.get("lat") is not None and r.get("lon") is not None
        ]

        if len(positioned) < 2:
            return self.generate(records, output_path, callsign, flight_date)

        kml = simplekml.Kml()
        title = f"{callsign}"
        if flight_date:
            title += f" - {flight_date}"
        kml.document.name = title

        # Create folder for path segments
        folder = kml.newfolder(name="Flight Path")

        # Create segments between points
        for i in range(len(positioned) - 1):
            r1 = positioned[i]
            r2 = positioned[i + 1]

            alt1 = self._get_altitude_ft(r1) or 0
            alt2 = self._get_altitude_ft(r2) or 0
            avg_alt = (alt1 + alt2) / 2

            segment = folder.newlinestring()
            segment.coords = [
                (r1["lon"], r1["lat"], self._get_altitude_meters(r1)),
                (r2["lon"], r2["lat"], self._get_altitude_meters(r2)),
            ]
            segment.altitudemode = simplekml.AltitudeMode.absolute
            segment.style.linestyle.color = self.altitude_to_color(avg_alt)
            segment.style.linestyle.width = 3

        # Add start/end points (same as regular generate)
        start = positioned[0]
        start_point = kml.newpoint(name="Start")
        start_point.coords = [(start["lon"], start["lat"], self._get_altitude_meters(start))]
        start_point.style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"

        end = positioned[-1]
        end_point = kml.newpoint(name="End")
        end_point.coords = [(end["lon"], end["lat"], self._get_altitude_meters(end))]
        end_point.style.iconstyle.icon.href = "http://maps.google.com/mapfiles/kml/paddle/red-circle.png"

        kml.save(str(output_path))
        log.info(f"Segmented KML saved to {output_path}")
        return output_path
