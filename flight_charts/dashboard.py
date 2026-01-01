"""Generate combined dashboard with all charts."""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .altitude_chart import AltitudeChart
from .speed_chart import SpeedChart
from .vertical_rate import VerticalRateChart
from .wind_chart import WindChart
from .signal_chart import SignalChart
from .accuracy_chart import AccuracyChart
from .phase_chart import FlightPhaseChart
from .track_map import TrackMapChart

log = logging.getLogger(__name__)

# Chart classes in display order
CHART_CLASSES = [
    TrackMapChart,       # Ground track map first
    AltitudeChart,
    FlightPhaseChart,    # Flight phases
    SpeedChart,
    VerticalRateChart,
    WindChart,
    SignalChart,
    AccuracyChart,
]


def generate_all_charts(
    records: List[dict],
    callsign: str,
    output_dir: Path,
    generate_png: bool = True,
    generate_html: bool = True,
    dpi: int = 150,
    max_points: int = 10000,
    progress_callback: Optional[callable] = None
) -> Dict[str, Tuple[Optional[Path], Optional[Path]]]:
    """
    Generate all chart types for a flight.

    Args:
        records: Flight data records
        callsign: Flight callsign for titles
        output_dir: Directory for output files
        generate_png: Whether to generate matplotlib PNG files
        generate_html: Whether to generate plotly HTML files
        dpi: DPI for PNG output
        max_points: Max points before decimation
        progress_callback: Optional callback(current, total, chart_name)

    Returns:
        Dict mapping chart name to (png_path, html_path) tuples
    """
    results = {}
    total = len(CHART_CLASSES)

    for i, ChartClass in enumerate(CHART_CLASSES):
        chart_name = ChartClass.__name__

        if progress_callback:
            progress_callback(i + 1, total, chart_name)

        try:
            chart = ChartClass(
                records=records,
                callsign=callsign,
                output_dir=output_dir,
                dpi=dpi,
                max_points=max_points
            )

            png_path = None
            html_path = None

            if generate_png:
                try:
                    png_path = chart.generate_matplotlib()
                except Exception as e:
                    log.warning(f"Failed to generate PNG for {chart_name}: {e}")

            if generate_html:
                try:
                    html_path = chart.generate_plotly()
                except Exception as e:
                    log.warning(f"Failed to generate HTML for {chart_name}: {e}")

            results[chart.name] = (png_path, html_path)

        except Exception as e:
            log.error(f"Failed to create chart {chart_name}: {e}")

    return results


def generate_dashboard(
    records: List[dict],
    callsign: str,
    output_dir: Path,
    flight_metadata: Optional[dict] = None
) -> Optional[Path]:
    """
    Generate a combined HTML dashboard with all charts embedded.

    Args:
        records: Flight data records
        callsign: Flight callsign
        output_dir: Directory for output
        flight_metadata: Optional metadata dict for header info

    Returns:
        Path to dashboard.html file
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        log.warning("plotly not available - cannot generate dashboard")
        return None

    output_path = output_dir / "charts" / "dashboard.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate individual chart figures
    charts = []

    for ChartClass in CHART_CLASSES:
        try:
            chart = ChartClass(
                records=records,
                callsign=callsign,
                output_dir=output_dir
            )
            fig = chart._create_plotly_figure()
            if fig is not None:
                charts.append((chart.title, fig))
        except Exception as e:
            log.warning(f"Failed to create dashboard chart {ChartClass.__name__}: {e}")

    if not charts:
        log.warning("No charts generated for dashboard")
        return None

    # Build combined HTML
    html_parts = [
        """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Flight Dashboard - """ + callsign + """</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            color: white;
            padding: 20px 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 {
            margin: 0 0 10px 0;
            font-size: 28px;
        }
        .header .meta {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            font-size: 14px;
            opacity: 0.9;
        }
        .header .meta span {
            background: rgba(255,255,255,0.1);
            padding: 5px 12px;
            border-radius: 5px;
        }
        .chart-container {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .chart-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
        }
        .footer {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Flight Dashboard: """ + callsign + """</h1>
        <div class="meta">
"""
    ]

    # Add metadata to header
    if flight_metadata:
        if flight_metadata.get("aircraft_type"):
            html_parts.append(f'            <span>Aircraft: {flight_metadata["aircraft_type"]}</span>\n')
        if flight_metadata.get("registration"):
            html_parts.append(f'            <span>Reg: {flight_metadata["registration"]}</span>\n')
        if flight_metadata.get("duration_minutes"):
            html_parts.append(f'            <span>Duration: {flight_metadata["duration_minutes"]:.0f} min</span>\n')
        if flight_metadata.get("max_altitude_ft"):
            html_parts.append(f'            <span>Max Alt: {flight_metadata["max_altitude_ft"]:.0f} ft</span>\n')
        if flight_metadata.get("records_extracted"):
            html_parts.append(f'            <span>Records: {flight_metadata["records_extracted"]}</span>\n')

    html_parts.append("""        </div>
    </div>
""")

    # Add each chart
    for i, (title, fig) in enumerate(charts):
        # Get the plotly HTML div
        chart_html = fig.to_html(
            include_plotlyjs=False,
            full_html=False,
            div_id=f"chart_{i}"
        )

        html_parts.append(f"""    <div class="chart-container">
        <div class="chart-title">{title}</div>
        {chart_html}
    </div>
""")

    html_parts.append("""    <div class="footer">
        Generated by ADS-B Flight Analyzer
    </div>
</body>
</html>""")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(html_parts))

    log.info(f"Dashboard saved to {output_path}")
    return output_path
