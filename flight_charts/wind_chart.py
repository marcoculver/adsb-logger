"""Wind analysis chart (track vs heading)."""
import logging
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

from .base import BaseChart, HAS_MATPLOTLIB, HAS_PLOTLY

if HAS_MATPLOTLIB:
    import matplotlib.pyplot as plt
if HAS_PLOTLY:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

log = logging.getLogger(__name__)


def unwrap_angles(angles: np.ndarray) -> np.ndarray:
    """
    Unwrap angles to prevent discontinuities when crossing 0/360.

    This keeps the line continuous by adjusting values that jump
    more than 180 degrees.
    """
    angles = np.array(angles, dtype=float)
    # Convert to radians, unwrap, convert back to degrees
    radians = np.deg2rad(angles)
    unwrapped = np.unwrap(radians)
    return np.rad2deg(unwrapped)


def normalize_to_range(angles: np.ndarray, center: float = 180) -> np.ndarray:
    """
    Normalize unwrapped angles back to a displayable range.

    Uses the median to determine the best center point for display.
    """
    angles = np.array(angles, dtype=float)
    median_val = np.nanmedian(angles)
    # Shift to center around median
    return angles


def split_at_discontinuities(x, y, threshold=180):
    """
    Split data into segments at discontinuities.

    Returns list of (x_segment, y_segment) tuples.
    """
    x = np.array(x)
    y = np.array(y)

    # Find discontinuities
    diff = np.abs(np.diff(y))
    breaks = np.where(diff > threshold)[0] + 1

    # Split into segments
    segments = []
    prev_idx = 0
    for idx in breaks:
        if idx - prev_idx > 1:  # Only add segments with more than 1 point
            segments.append((x[prev_idx:idx], y[prev_idx:idx]))
        prev_idx = idx

    # Add final segment
    if len(x) - prev_idx > 1:
        segments.append((x[prev_idx:], y[prev_idx:]))

    return segments


class WindChart(BaseChart):
    """
    Wind analysis chart showing track vs heading.

    Features:
    - Track (actual ground path)
    - True heading (where aircraft is pointing)
    - Difference indicates wind correction angle
    - If available: wind speed/direction from ADS-B
    - Handles 0/360 wrap-around gracefully
    """

    @property
    def name(self) -> str:
        return "wind_analysis"

    @property
    def title(self) -> str:
        return f"{self.callsign} - Wind Analysis (Track vs Heading)"

    def _create_matplotlib_figure(self) -> Optional['plt.Figure']:
        if not HAS_MATPLOTLIB or self.df is None:
            return None

        df = self.df.copy()

        if "datetime" not in df.columns:
            return None

        has_track = "track" in df.columns and df["track"].notna().any()
        has_true_heading = "true_heading" in df.columns and df["true_heading"].notna().any()
        has_mag_heading = "mag_heading" in df.columns and df["mag_heading"].notna().any()
        has_wind = "wd" in df.columns and df["wd"].notna().any()
        has_wind_speed = "ws" in df.columns and df["ws"].notna().any()

        if not has_track:
            log.warning("No track data for wind chart")
            return None

        # Create subplots
        if has_wind:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                           gridspec_kw={"height_ratios": [2, 1]})
        else:
            fig, ax1 = plt.subplots(1, 1, figsize=(12, 5))
            ax2 = None

        # Get heading data
        heading_col = "true_heading" if has_true_heading else ("mag_heading" if has_mag_heading else None)

        # Plot track - split at discontinuities to avoid ugly lines
        track_segments = split_at_discontinuities(df["datetime"].values, df["track"].values)
        for i, (x_seg, y_seg) in enumerate(track_segments):
            ax1.plot(x_seg, y_seg, "b-", linewidth=1.5, alpha=0.9,
                    label="Track" if i == 0 else None)

        # Plot heading
        if heading_col:
            heading_segments = split_at_discontinuities(df["datetime"].values, df[heading_col].values)
            for i, (x_seg, y_seg) in enumerate(heading_segments):
                ax1.plot(x_seg, y_seg, "r--", linewidth=1.5, alpha=0.8,
                        label="Heading" if i == 0 else None)

        ax1.set_ylabel("Degrees")
        ax1.set_ylim(0, 360)
        ax1.set_yticks([0, 45, 90, 135, 180, 225, 270, 315, 360])
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)
        ax1.set_title(self.title)

        # Calculate and plot wind correction angle on secondary axis
        if heading_col:
            heading = df[heading_col].values
            track = df["track"].values

            # Calculate WCA (positive = crabbing right, negative = crabbing left)
            wca = track - heading
            # Normalize to -180 to +180
            wca = np.where(wca > 180, wca - 360, wca)
            wca = np.where(wca < -180, wca + 360, wca)

            ax1b = ax1.twinx()
            ax1b.fill_between(df["datetime"], 0, wca, alpha=0.3, color="purple",
                            where=~np.isnan(wca))
            ax1b.axhline(y=0, color="purple", linestyle="-", linewidth=0.5, alpha=0.5)
            ax1b.set_ylabel("Wind Correction Angle (°)", color="purple")
            ax1b.tick_params(axis="y", labelcolor="purple")
            ax1b.set_ylim(-45, 45)

        # Wind data subplot
        if ax2 is not None and has_wind:
            # Split wind direction at discontinuities too
            wd_segments = split_at_discontinuities(df["datetime"].values, df["wd"].values)
            for i, (x_seg, y_seg) in enumerate(wd_segments):
                ax2.plot(x_seg, y_seg, "g-", linewidth=1.5,
                        label="Wind Dir" if i == 0 else None)

            ax2.set_ylabel("Wind Direction (°)", color="green")
            ax2.tick_params(axis="y", labelcolor="green")
            ax2.set_ylim(0, 360)
            ax2.set_yticks([0, 90, 180, 270, 360])

            if has_wind_speed:
                ax2b = ax2.twinx()
                ax2b.plot(df["datetime"], df["ws"], "m-", linewidth=1.5, label="Wind Speed")
                ax2b.set_ylabel("Wind Speed (kts)", color="magenta")
                ax2b.tick_params(axis="y", labelcolor="magenta")
                ax2b.set_ylim(0, max(df["ws"].max() * 1.2, 50))

            ax2.grid(True, alpha=0.3)
            ax2.legend(loc="upper left")
            self._format_time_axis(ax2)
            ax2.set_xlabel("Time (UTC)")
        else:
            self._format_time_axis(ax1)
            ax1.set_xlabel("Time (UTC)")

        plt.tight_layout()
        return fig

    def _create_plotly_figure(self) -> Optional['go.Figure']:
        if not HAS_PLOTLY or self.df is None:
            return None

        df = self.df.copy()

        if "datetime" not in df.columns:
            return None

        has_track = "track" in df.columns and df["track"].notna().any()
        has_true_heading = "true_heading" in df.columns and df["true_heading"].notna().any()
        has_mag_heading = "mag_heading" in df.columns and df["mag_heading"].notna().any()
        has_wind = "wd" in df.columns and df["wd"].notna().any()

        if not has_track:
            return None

        # Get heading column
        heading_col = "true_heading" if has_true_heading else ("mag_heading" if has_mag_heading else None)

        # Create subplots
        if has_wind:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.1,
                row_heights=[0.65, 0.35],
                subplot_titles=("Track vs Heading", "Wind Data"),
                specs=[[{"secondary_y": True}], [{"secondary_y": True}]]
            )
        else:
            fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Plot track - use None to break lines at discontinuities
        track_with_breaks = self._insert_breaks(df["datetime"].values, df["track"].values)
        fig.add_trace(
            go.Scatter(
                x=track_with_breaks[0],
                y=track_with_breaks[1],
                name="Track",
                line=dict(color="blue", width=2),
                hovertemplate="<b>Track: %{y:.0f}°</b><extra></extra>",
                connectgaps=False
            ),
            row=1, col=1, secondary_y=False
        )

        # Plot heading
        if heading_col:
            hdg_with_breaks = self._insert_breaks(df["datetime"].values, df[heading_col].values)
            fig.add_trace(
                go.Scatter(
                    x=hdg_with_breaks[0],
                    y=hdg_with_breaks[1],
                    name="Heading",
                    line=dict(color="red", width=2, dash="dash"),
                    hovertemplate="<b>HDG: %{y:.0f}°</b><extra></extra>",
                    connectgaps=False
                ),
                row=1, col=1, secondary_y=False
            )

            # Wind correction angle
            heading = df[heading_col].values
            track = df["track"].values
            wca = track - heading
            wca = np.where(wca > 180, wca - 360, wca)
            wca = np.where(wca < -180, wca + 360, wca)

            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=wca,
                    name="Wind Correction",
                    fill="tozeroy",
                    fillcolor="rgba(128, 0, 128, 0.2)",
                    line=dict(color="purple", width=1),
                    hovertemplate="<b>WCA: %{y:.1f}°</b><extra></extra>"
                ),
                row=1, col=1, secondary_y=True
            )

        # Wind data
        if has_wind:
            wd_with_breaks = self._insert_breaks(df["datetime"].values, df["wd"].values)
            fig.add_trace(
                go.Scatter(
                    x=wd_with_breaks[0],
                    y=wd_with_breaks[1],
                    name="Wind Direction",
                    line=dict(color="green", width=2),
                    hovertemplate="<b>WD: %{y:.0f}°</b><extra></extra>",
                    connectgaps=False
                ),
                row=2, col=1, secondary_y=False
            )

            if "ws" in df.columns and df["ws"].notna().any():
                fig.add_trace(
                    go.Scatter(
                        x=df["datetime"],
                        y=df["ws"],
                        name="Wind Speed",
                        line=dict(color="magenta", width=2),
                        hovertemplate="<b>WS: %{y:.0f} kts</b><extra></extra>"
                    ),
                    row=2, col=1, secondary_y=True
                )

        # Layout
        fig.update_layout(
            title=self.title,
            hovermode="x unified",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=600 if has_wind else 400,
        )

        fig.update_yaxes(title_text="Degrees", range=[0, 360], row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="WCA (°)", range=[-45, 45], row=1, col=1, secondary_y=True)

        if has_wind:
            fig.update_yaxes(title_text="Wind Dir (°)", range=[0, 360], row=2, col=1, secondary_y=False)
            fig.update_yaxes(title_text="Wind Speed (kts)", row=2, col=1, secondary_y=True)
            fig.update_xaxes(title_text="Time (UTC)", row=2, col=1)
        else:
            fig.update_xaxes(title_text="Time (UTC)", row=1, col=1)

        return fig

    def _insert_breaks(self, x, y, threshold=180):
        """Insert None values at discontinuities to break the line."""
        x = list(x)
        y = list(y)

        new_x = []
        new_y = []

        for i in range(len(y)):
            new_x.append(x[i])
            new_y.append(y[i])

            if i < len(y) - 1:
                # Check for discontinuity
                if y[i] is not None and y[i+1] is not None:
                    diff = abs(float(y[i+1]) - float(y[i]))
                    if diff > threshold:
                        new_x.append(None)
                        new_y.append(None)

        return new_x, new_y
