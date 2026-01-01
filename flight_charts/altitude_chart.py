"""Altitude profile chart."""
import logging
from pathlib import Path
from typing import Optional

from .base import BaseChart, HAS_MATPLOTLIB, HAS_PLOTLY, HAS_PANDAS

if HAS_MATPLOTLIB:
    import matplotlib.pyplot as plt
if HAS_PLOTLY:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

log = logging.getLogger(__name__)


class AltitudeChart(BaseChart):
    """
    Altitude profile chart showing altitude vs time.

    Features:
    - Barometric and geometric altitude overlay
    - Vertical rate subplot
    - Climb/descent phase coloring
    """

    @property
    def name(self) -> str:
        return "altitude_profile"

    @property
    def title(self) -> str:
        return f"{self.callsign} - Altitude Profile"

    def _create_matplotlib_figure(self) -> Optional['plt.Figure']:
        if not HAS_MATPLOTLIB or self.df is None:
            return None

        df = self.df

        # Check for required columns
        if "datetime" not in df.columns:
            log.warning("No datetime column for altitude chart")
            return None

        has_alt_baro = "alt_baro" in df.columns and df["alt_baro"].notna().any()
        has_alt_geom = "alt_geom" in df.columns and df["alt_geom"].notna().any()
        has_vrate = "baro_rate" in df.columns and df["baro_rate"].notna().any()

        if not has_alt_baro and not has_alt_geom:
            log.warning("No altitude data for chart")
            return None

        # Create figure with subplots
        if has_vrate:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                            gridspec_kw={"height_ratios": [3, 1]})
        else:
            fig, ax1 = plt.subplots(1, 1, figsize=(12, 5))
            ax2 = None

        # Plot altitudes
        if has_alt_baro:
            ax1.plot(df["datetime"], df["alt_baro"], "b-", linewidth=1.5,
                    label="Baro Altitude", alpha=0.9)
        if has_alt_geom:
            ax1.plot(df["datetime"], df["alt_geom"], "g--", linewidth=1,
                    label="Geom Altitude", alpha=0.7)

        ax1.set_ylabel("Altitude (ft)")
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)
        ax1.set_title(self.title)

        # Format y-axis to show thousands
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x/1000:.0f}k" if x >= 1000 else f"{x:.0f}"))

        # Plot vertical rate
        if ax2 is not None and has_vrate:
            vrate = df["baro_rate"].fillna(0)
            ax2.fill_between(df["datetime"], 0, vrate,
                           where=vrate > 0, color="green", alpha=0.5, label="Climb")
            ax2.fill_between(df["datetime"], 0, vrate,
                           where=vrate < 0, color="red", alpha=0.5, label="Descent")
            ax2.axhline(y=0, color="gray", linestyle="-", linewidth=0.5)
            ax2.set_ylabel("Vertical Rate (ft/min)")
            ax2.legend(loc="upper right")
            ax2.grid(True, alpha=0.3)

        # Format time axis
        if ax2 is not None:
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

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_alt_baro = "alt_baro" in df.columns and df["alt_baro"].notna().any()
        has_alt_geom = "alt_geom" in df.columns and df["alt_geom"].notna().any()
        has_vrate = "baro_rate" in df.columns and df["baro_rate"].notna().any()

        if not has_alt_baro and not has_alt_geom:
            return None

        # Create subplots
        if has_vrate:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.08,
                row_heights=[0.7, 0.3],
                subplot_titles=("Altitude", "Vertical Rate")
            )
        else:
            fig = make_subplots(rows=1, cols=1)

        # Altitude traces
        if has_alt_baro:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["alt_baro"],
                    name="Baro Altitude",
                    line=dict(color="blue", width=2),
                    hovertemplate="<b>%{y:.0f} ft</b><br>%{x}<extra></extra>"
                ),
                row=1, col=1
            )

        if has_alt_geom:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["alt_geom"],
                    name="Geom Altitude",
                    line=dict(color="green", width=1, dash="dash"),
                    opacity=0.7,
                    hovertemplate="<b>%{y:.0f} ft</b><br>%{x}<extra></extra>"
                ),
                row=1, col=1
            )

        # Vertical rate
        if has_vrate:
            vrate = df["baro_rate"].fillna(0)

            # Positive (climb)
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=vrate.where(vrate > 0, 0),
                    name="Climb",
                    fill="tozeroy",
                    fillcolor="rgba(0, 255, 0, 0.3)",
                    line=dict(color="green", width=1),
                    hovertemplate="<b>+%{y:.0f} ft/min</b><extra></extra>"
                ),
                row=2, col=1
            )

            # Negative (descent)
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=vrate.where(vrate < 0, 0),
                    name="Descent",
                    fill="tozeroy",
                    fillcolor="rgba(255, 0, 0, 0.3)",
                    line=dict(color="red", width=1),
                    hovertemplate="<b>%{y:.0f} ft/min</b><extra></extra>"
                ),
                row=2, col=1
            )

        # Layout
        fig.update_layout(
            title=self.title,
            hovermode="x unified",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=600 if has_vrate else 400,
        )

        fig.update_yaxes(title_text="Altitude (ft)", row=1, col=1)
        if has_vrate:
            fig.update_yaxes(title_text="ft/min", row=2, col=1)
            fig.update_xaxes(title_text="Time (UTC)", row=2, col=1)
        else:
            fig.update_xaxes(title_text="Time (UTC)", row=1, col=1)

        return fig
