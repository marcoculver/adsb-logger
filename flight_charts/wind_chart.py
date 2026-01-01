"""Wind analysis chart (track vs heading)."""
import logging
from pathlib import Path
from typing import Optional

from .base import BaseChart, HAS_MATPLOTLIB, HAS_PLOTLY

if HAS_MATPLOTLIB:
    import matplotlib.pyplot as plt
    import numpy as np
if HAS_PLOTLY:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

log = logging.getLogger(__name__)


class WindChart(BaseChart):
    """
    Wind analysis chart showing track vs heading.

    Features:
    - Track (actual ground path)
    - True heading (where aircraft is pointing)
    - Difference indicates wind correction angle
    - If available: wind speed/direction from ADS-B
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

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_track = "track" in df.columns and df["track"].notna().any()
        has_true_heading = "true_heading" in df.columns and df["true_heading"].notna().any()
        has_mag_heading = "mag_heading" in df.columns and df["mag_heading"].notna().any()
        has_wind = "wd" in df.columns and df["wd"].notna().any()

        if not has_track:
            log.warning("No track data for wind chart")
            return None

        # Create subplots: top for track/heading, bottom for wind correction or wind data
        if has_wind:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        else:
            fig, ax1 = plt.subplots(1, 1, figsize=(12, 5))
            ax2 = None

        # Track and heading
        ax1.plot(df["datetime"], df["track"], "b-", linewidth=1.5,
                label="Track (ground path)", alpha=0.9)

        if has_true_heading:
            ax1.plot(df["datetime"], df["true_heading"], "r--", linewidth=1.5,
                    label="True Heading", alpha=0.8)
        elif has_mag_heading:
            ax1.plot(df["datetime"], df["mag_heading"], "r--", linewidth=1.5,
                    label="Mag Heading", alpha=0.8)

        ax1.set_ylabel("Degrees")
        ax1.set_ylim(0, 360)
        ax1.set_yticks([0, 90, 180, 270, 360])
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)
        ax1.set_title(self.title)

        # Wind correction angle or actual wind data
        if ax2 is not None and has_wind:
            ws = df.get("ws", None)
            wd = df["wd"]

            ax2.plot(df["datetime"], wd, "g-", linewidth=1.5, label="Wind Direction")
            ax2.set_ylabel("Wind Direction (deg)", color="green")
            ax2.tick_params(axis="y", labelcolor="green")
            ax2.set_ylim(0, 360)

            if ws is not None and ws.notna().any():
                ax2b = ax2.twinx()
                ax2b.plot(df["datetime"], ws, "m-", linewidth=1.5, label="Wind Speed")
                ax2b.set_ylabel("Wind Speed (kts)", color="magenta")
                ax2b.tick_params(axis="y", labelcolor="magenta")

            ax2.grid(True, alpha=0.3)
            ax2.legend(loc="upper left")
            self._format_time_axis(ax2)
            ax2.set_xlabel("Time (UTC)")
        else:
            self._format_time_axis(ax1)
            ax1.set_xlabel("Time (UTC)")

            # If we have heading, show wind correction angle
            if has_true_heading or has_mag_heading:
                heading = df["true_heading"] if has_true_heading else df["mag_heading"]
                wca = df["track"] - heading

                # Handle wrap-around
                wca = wca.apply(lambda x: x - 360 if x > 180 else (x + 360 if x < -180 else x))

                ax1b = ax1.twinx()
                ax1b.fill_between(df["datetime"], 0, wca, alpha=0.3, color="purple")
                ax1b.set_ylabel("Wind Correction Angle (deg)", color="purple")
                ax1b.tick_params(axis="y", labelcolor="purple")
                ax1b.set_ylim(-30, 30)

        plt.tight_layout()
        return fig

    def _create_plotly_figure(self) -> Optional['go.Figure']:
        if not HAS_PLOTLY or self.df is None:
            return None

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_track = "track" in df.columns and df["track"].notna().any()
        has_true_heading = "true_heading" in df.columns and df["true_heading"].notna().any()
        has_mag_heading = "mag_heading" in df.columns and df["mag_heading"].notna().any()
        has_wind = "wd" in df.columns and df["wd"].notna().any()

        if not has_track:
            return None

        # Create subplots
        if has_wind:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.1,
                subplot_titles=("Track vs Heading", "Wind Data"),
                specs=[[{"secondary_y": True}], [{"secondary_y": True}]]
            )
        else:
            fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Track
        fig.add_trace(
            go.Scatter(
                x=df["datetime"],
                y=df["track"],
                name="Track",
                line=dict(color="blue", width=2),
                hovertemplate="<b>Track: %{y:.0f}°</b><extra></extra>"
            ),
            row=1, col=1, secondary_y=False
        )

        # Heading
        if has_true_heading:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["true_heading"],
                    name="True Heading",
                    line=dict(color="red", width=2, dash="dash"),
                    hovertemplate="<b>HDG: %{y:.0f}°</b><extra></extra>"
                ),
                row=1, col=1, secondary_y=False
            )
        elif has_mag_heading:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["mag_heading"],
                    name="Mag Heading",
                    line=dict(color="red", width=2, dash="dash"),
                    hovertemplate="<b>HDG: %{y:.0f}°</b><extra></extra>"
                ),
                row=1, col=1, secondary_y=False
            )

        # Wind correction angle
        if has_true_heading or has_mag_heading:
            heading = df["true_heading"] if has_true_heading else df["mag_heading"]
            wca = df["track"] - heading
            # Handle wrap-around
            wca = wca.apply(lambda x: x - 360 if x > 180 else (x + 360 if x < -180 else x))

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

        # Wind data if available
        if has_wind:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["wd"],
                    name="Wind Direction",
                    line=dict(color="green", width=2),
                    hovertemplate="<b>WD: %{y:.0f}°</b><extra></extra>"
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
        fig.update_yaxes(title_text="WCA (°)", range=[-30, 30], row=1, col=1, secondary_y=True)

        if has_wind:
            fig.update_yaxes(title_text="Wind Dir (°)", range=[0, 360], row=2, col=1, secondary_y=False)
            fig.update_yaxes(title_text="Wind Speed (kts)", row=2, col=1, secondary_y=True)
            fig.update_xaxes(title_text="Time (UTC)", row=2, col=1)
        else:
            fig.update_xaxes(title_text="Time (UTC)", row=1, col=1)

        return fig
