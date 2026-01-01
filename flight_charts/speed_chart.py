"""Speed profile chart."""
import logging
from pathlib import Path
from typing import Optional

from .base import BaseChart, HAS_MATPLOTLIB, HAS_PLOTLY

if HAS_MATPLOTLIB:
    import matplotlib.pyplot as plt
if HAS_PLOTLY:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

log = logging.getLogger(__name__)


class SpeedChart(BaseChart):
    """
    Speed profile chart showing various speed measurements vs time.

    Features:
    - Ground speed
    - Indicated airspeed (IAS)
    - True airspeed (TAS)
    - Mach number (secondary axis)
    """

    @property
    def name(self) -> str:
        return "speed_profile"

    @property
    def title(self) -> str:
        return f"{self.callsign} - Speed Profile"

    def _create_matplotlib_figure(self) -> Optional['plt.Figure']:
        if not HAS_MATPLOTLIB or self.df is None:
            return None

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_gs = "gs" in df.columns and df["gs"].notna().any()
        has_ias = "ias" in df.columns and df["ias"].notna().any()
        has_tas = "tas" in df.columns and df["tas"].notna().any()
        has_mach = "mach" in df.columns and df["mach"].notna().any()

        if not any([has_gs, has_ias, has_tas]):
            log.warning("No speed data for chart")
            return None

        fig, ax1 = plt.subplots(1, 1, figsize=(12, 5))

        # Speed traces
        if has_gs:
            ax1.plot(df["datetime"], df["gs"], "b-", linewidth=1.5,
                    label="Ground Speed", alpha=0.9)
        if has_ias:
            ax1.plot(df["datetime"], df["ias"], "g-", linewidth=1.5,
                    label="IAS", alpha=0.8)
        if has_tas:
            ax1.plot(df["datetime"], df["tas"], "r--", linewidth=1,
                    label="TAS", alpha=0.7)

        ax1.set_ylabel("Speed (kts)")
        ax1.set_xlabel("Time (UTC)")
        ax1.grid(True, alpha=0.3)
        ax1.set_title(self.title)

        # Mach on secondary axis
        if has_mach:
            ax2 = ax1.twinx()
            ax2.plot(df["datetime"], df["mach"], "m:", linewidth=1.5,
                    label="Mach", alpha=0.7)
            ax2.set_ylabel("Mach", color="magenta")
            ax2.tick_params(axis="y", labelcolor="magenta")

            # Combined legend
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
        else:
            ax1.legend(loc="upper right")

        self._format_time_axis(ax1)
        plt.tight_layout()
        return fig

    def _create_plotly_figure(self) -> Optional['go.Figure']:
        if not HAS_PLOTLY or self.df is None:
            return None

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_gs = "gs" in df.columns and df["gs"].notna().any()
        has_ias = "ias" in df.columns and df["ias"].notna().any()
        has_tas = "tas" in df.columns and df["tas"].notna().any()
        has_mach = "mach" in df.columns and df["mach"].notna().any()

        if not any([has_gs, has_ias, has_tas]):
            return None

        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Speed traces
        if has_gs:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["gs"],
                    name="Ground Speed",
                    line=dict(color="blue", width=2),
                    hovertemplate="<b>GS: %{y:.0f} kts</b><extra></extra>"
                ),
                secondary_y=False
            )

        if has_ias:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["ias"],
                    name="IAS",
                    line=dict(color="green", width=2),
                    hovertemplate="<b>IAS: %{y:.0f} kts</b><extra></extra>"
                ),
                secondary_y=False
            )

        if has_tas:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["tas"],
                    name="TAS",
                    line=dict(color="red", width=1, dash="dash"),
                    hovertemplate="<b>TAS: %{y:.0f} kts</b><extra></extra>"
                ),
                secondary_y=False
            )

        if has_mach:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["mach"],
                    name="Mach",
                    line=dict(color="magenta", width=2, dash="dot"),
                    hovertemplate="<b>M%{y:.3f}</b><extra></extra>"
                ),
                secondary_y=True
            )

        # Layout
        fig.update_layout(
            title=self.title,
            hovermode="x unified",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=400,
        )

        fig.update_yaxes(title_text="Speed (kts)", secondary_y=False)
        if has_mach:
            fig.update_yaxes(title_text="Mach", secondary_y=True)
        fig.update_xaxes(title_text="Time (UTC)")

        return fig
