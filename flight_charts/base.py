"""Base chart class and utilities for flight visualization."""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)

# Check for optional dependencies
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


def prepare_dataframe(records: List[dict]) -> 'pd.DataFrame':
    """
    Convert records to pandas DataFrame with proper types.

    Args:
        records: List of flight data records

    Returns:
        DataFrame with cleaned and typed data
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required for chart generation")

    df = pd.DataFrame(records)

    # Convert timestamp to datetime
    if "_ts" in df.columns:
        df["datetime"] = pd.to_datetime(df["_ts"], unit="s", utc=True)

    # Ensure numeric columns are numeric
    numeric_cols = [
        "lat", "lon", "alt_baro", "alt_geom",
        "gs", "ias", "tas", "mach",
        "baro_rate", "geom_rate",
        "track", "true_heading", "mag_heading",
        "rssi", "messages",
        "nic", "nac_p", "nac_v", "sil", "gva", "sda",
        "wd", "ws", "oat", "tat",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Handle "ground" altitude values
    for alt_col in ["alt_baro", "alt_geom"]:
        if alt_col in df.columns:
            df[alt_col] = df[alt_col].replace("ground", 0)
            df[alt_col] = pd.to_numeric(df[alt_col], errors="coerce")

    return df


class BaseChart(ABC):
    """Abstract base class for all chart types."""

    def __init__(
        self,
        records: List[dict],
        callsign: str,
        output_dir: Optional[Path] = None,
        dpi: int = 150,
        max_points: int = 10000
    ):
        """
        Initialize chart generator.

        Args:
            records: Flight data records
            callsign: Flight callsign for titles
            output_dir: Directory for output files
            dpi: DPI for PNG output
            max_points: Max points before decimation
        """
        self.records = records
        self.callsign = callsign
        self.output_dir = output_dir
        self.dpi = dpi
        self.max_points = max_points

        # Prepare DataFrame
        if HAS_PANDAS:
            self.df = prepare_dataframe(records)
            # Decimate if needed
            if len(self.df) > max_points:
                step = len(self.df) // max_points
                self.df = self.df.iloc[::step].copy()
                log.info(f"Decimated data from {len(records)} to {len(self.df)} points")
        else:
            self.df = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Chart name for filenames (e.g., 'altitude_profile')."""
        pass

    @property
    @abstractmethod
    def title(self) -> str:
        """Chart title for display."""
        pass

    def generate_matplotlib(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Generate static PNG chart using matplotlib.

        Args:
            output_path: Path for output file, or auto-generate from output_dir

        Returns:
            Path to generated file, or None if matplotlib unavailable
        """
        if not HAS_MATPLOTLIB:
            log.warning("matplotlib not available - skipping PNG generation")
            return None

        if output_path is None and self.output_dir:
            output_path = self.output_dir / "charts" / f"{self.name}.png"

        if output_path is None:
            raise ValueError("No output path specified")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        fig = self._create_matplotlib_figure()
        if fig is None:
            return None

        fig.savefig(output_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        log.info(f"Saved matplotlib chart: {output_path}")
        return output_path

    def generate_plotly(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Generate interactive HTML chart using plotly.

        Args:
            output_path: Path for output file, or auto-generate from output_dir

        Returns:
            Path to generated file, or None if plotly unavailable
        """
        if not HAS_PLOTLY:
            log.warning("plotly not available - skipping HTML generation")
            return None

        if output_path is None and self.output_dir:
            output_path = self.output_dir / "charts" / f"{self.name}.html"

        if output_path is None:
            raise ValueError("No output path specified")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        fig = self._create_plotly_figure()
        if fig is None:
            return None

        fig.write_html(
            str(output_path),
            include_plotlyjs="cdn",
            full_html=True
        )

        log.info(f"Saved plotly chart: {output_path}")
        return output_path

    def generate_both(self) -> Tuple[Optional[Path], Optional[Path]]:
        """Generate both PNG and HTML versions."""
        png_path = self.generate_matplotlib()
        html_path = self.generate_plotly()
        return (png_path, html_path)

    @abstractmethod
    def _create_matplotlib_figure(self) -> Optional['plt.Figure']:
        """Create matplotlib figure. Override in subclass."""
        pass

    @abstractmethod
    def _create_plotly_figure(self) -> Optional['go.Figure']:
        """Create plotly figure. Override in subclass."""
        pass

    def _format_time_axis(self, ax, locator_minutes: int = 10):
        """Format matplotlib time axis."""
        if not HAS_MATPLOTLIB:
            return
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=locator_minutes))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
