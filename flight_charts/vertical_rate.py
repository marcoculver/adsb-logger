"""Vertical rate chart."""
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


class VerticalRateChart(BaseChart):
    """
    Vertical rate chart showing climb/descent performance.

    Features:
    - Barometric and geometric vertical rates
    - Color-coded climb/descent phases
    - Phase transition markers
    """

    @property
    def name(self) -> str:
        return "vertical_rate"

    @property
    def title(self) -> str:
        return f"{self.callsign} - Vertical Rate"

    def _create_matplotlib_figure(self) -> Optional['plt.Figure']:
        if not HAS_MATPLOTLIB or self.df is None:
            return None

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_baro_rate = "baro_rate" in df.columns and df["baro_rate"].notna().any()
        has_geom_rate = "geom_rate" in df.columns and df["geom_rate"].notna().any()

        if not has_baro_rate and not has_geom_rate:
            log.warning("No vertical rate data for chart")
            return None

        fig, ax = plt.subplots(1, 1, figsize=(12, 5))

        if has_baro_rate:
            vrate = df["baro_rate"].fillna(0)

            # Fill areas
            ax.fill_between(df["datetime"], 0, vrate,
                          where=vrate > 0, color="green", alpha=0.4, label="Climb")
            ax.fill_between(df["datetime"], 0, vrate,
                          where=vrate < 0, color="red", alpha=0.4, label="Descent")

            # Line on top
            ax.plot(df["datetime"], vrate, "b-", linewidth=1, alpha=0.7, label="Baro Rate")

        if has_geom_rate:
            ax.plot(df["datetime"], df["geom_rate"], "g--", linewidth=1,
                   alpha=0.6, label="Geom Rate")

        ax.axhline(y=0, color="gray", linestyle="-", linewidth=1)
        ax.set_ylabel("Vertical Rate (ft/min)")
        ax.set_xlabel("Time (UTC)")
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        ax.set_title(self.title)

        # Add reference lines for typical rates
        ax.axhline(y=2000, color="gray", linestyle=":", linewidth=0.5, alpha=0.5)
        ax.axhline(y=-2000, color="gray", linestyle=":", linewidth=0.5, alpha=0.5)

        self._format_time_axis(ax)
        plt.tight_layout()
        return fig

    def _create_plotly_figure(self) -> Optional['go.Figure']:
        if not HAS_PLOTLY or self.df is None:
            return None

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_baro_rate = "baro_rate" in df.columns and df["baro_rate"].notna().any()
        has_geom_rate = "geom_rate" in df.columns and df["geom_rate"].notna().any()

        if not has_baro_rate and not has_geom_rate:
            return None

        fig = go.Figure()

        if has_baro_rate:
            vrate = df["baro_rate"].fillna(0)

            # Climb fill
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=vrate.where(vrate > 0, 0),
                    name="Climb",
                    fill="tozeroy",
                    fillcolor="rgba(0, 200, 0, 0.3)",
                    line=dict(color="green", width=1),
                    hovertemplate="<b>+%{y:.0f} ft/min</b><extra></extra>"
                )
            )

            # Descent fill
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=vrate.where(vrate < 0, 0),
                    name="Descent",
                    fill="tozeroy",
                    fillcolor="rgba(200, 0, 0, 0.3)",
                    line=dict(color="red", width=1),
                    hovertemplate="<b>%{y:.0f} ft/min</b><extra></extra>"
                )
            )

            # Main line
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["baro_rate"],
                    name="Baro Rate",
                    line=dict(color="blue", width=1.5),
                    hovertemplate="<b>%{y:.0f} ft/min</b><extra></extra>"
                )
            )

        if has_geom_rate:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["geom_rate"],
                    name="Geom Rate",
                    line=dict(color="green", width=1, dash="dash"),
                    opacity=0.7,
                    hovertemplate="<b>%{y:.0f} ft/min</b><extra></extra>"
                )
            )

        # Zero line and reference lines
        fig.add_hline(y=0, line_color="gray", line_width=1)
        fig.add_hline(y=2000, line_color="gray", line_width=0.5, line_dash="dot",
                     annotation_text="2000 ft/min", annotation_position="right")
        fig.add_hline(y=-2000, line_color="gray", line_width=0.5, line_dash="dot",
                     annotation_text="-2000 ft/min", annotation_position="right")

        fig.update_layout(
            title=self.title,
            hovermode="x unified",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=400,
            yaxis_title="Vertical Rate (ft/min)",
            xaxis_title="Time (UTC)",
        )

        return fig
