"""Signal quality chart."""
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


class SignalChart(BaseChart):
    """
    Signal quality chart showing receiver performance.

    Features:
    - RSSI (Received Signal Strength Indicator)
    - Message count rate
    - Position update frequency (based on seen_pos)
    """

    @property
    def name(self) -> str:
        return "signal_quality"

    @property
    def title(self) -> str:
        return f"{self.callsign} - Signal Quality"

    def _create_matplotlib_figure(self) -> Optional['plt.Figure']:
        if not HAS_MATPLOTLIB or self.df is None:
            return None

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_rssi = "rssi" in df.columns and df["rssi"].notna().any()
        has_messages = "messages" in df.columns and df["messages"].notna().any()
        has_distance = "r_dst" in df.columns and df["r_dst"].notna().any()

        if not has_rssi and not has_messages:
            log.warning("No signal data for chart")
            return None

        # Create subplots
        n_plots = sum([has_rssi, has_messages or has_distance])
        if n_plots == 0:
            return None

        fig, axes = plt.subplots(n_plots, 1, figsize=(12, 4 * n_plots), sharex=True)
        if n_plots == 1:
            axes = [axes]

        plot_idx = 0

        # RSSI
        if has_rssi:
            ax = axes[plot_idx]
            ax.plot(df["datetime"], df["rssi"], "b-", linewidth=1, alpha=0.7)
            ax.fill_between(df["datetime"], df["rssi"].min(), df["rssi"],
                          alpha=0.3, color="blue")
            ax.set_ylabel("RSSI (dBFS)")
            ax.grid(True, alpha=0.3)
            ax.set_title("Signal Strength (RSSI)")

            # Add signal quality bands
            ax.axhline(y=-10, color="green", linestyle=":", alpha=0.5)
            ax.axhline(y=-20, color="yellow", linestyle=":", alpha=0.5)
            ax.axhline(y=-30, color="red", linestyle=":", alpha=0.5)

            plot_idx += 1

        # Message count and distance
        if has_messages or has_distance:
            ax = axes[plot_idx]

            if has_messages:
                ax.plot(df["datetime"], df["messages"], "g-", linewidth=1,
                       alpha=0.8, label="Message Count")
                ax.set_ylabel("Messages")

            if has_distance:
                ax2 = ax.twinx() if has_messages else ax
                ax2.plot(df["datetime"], df["r_dst"], "m-", linewidth=1,
                        alpha=0.7, label="Distance")
                ax2.set_ylabel("Distance (nm)", color="magenta")
                ax2.tick_params(axis="y", labelcolor="magenta")

            ax.grid(True, alpha=0.3)
            ax.set_title("Message Count & Distance")

            if has_messages:
                ax.legend(loc="upper left")

        # Format time axis on bottom plot
        self._format_time_axis(axes[-1])
        axes[-1].set_xlabel("Time (UTC)")

        plt.suptitle(self.title, y=1.02)
        plt.tight_layout()
        return fig

    def _create_plotly_figure(self) -> Optional['go.Figure']:
        if not HAS_PLOTLY or self.df is None:
            return None

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_rssi = "rssi" in df.columns and df["rssi"].notna().any()
        has_messages = "messages" in df.columns and df["messages"].notna().any()
        has_distance = "r_dst" in df.columns and df["r_dst"].notna().any()

        if not has_rssi and not has_messages:
            return None

        # Determine subplot configuration
        n_rows = sum([has_rssi, has_messages or has_distance])
        if n_rows == 0:
            return None

        specs = [[{"secondary_y": True}]] * n_rows
        fig = make_subplots(
            rows=n_rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            specs=specs
        )

        row_idx = 1

        # RSSI
        if has_rssi:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["rssi"],
                    name="RSSI",
                    fill="tozeroy",
                    fillcolor="rgba(0, 100, 255, 0.3)",
                    line=dict(color="blue", width=1),
                    hovertemplate="<b>RSSI: %{y:.1f} dBFS</b><extra></extra>"
                ),
                row=row_idx, col=1
            )

            # Signal quality reference lines
            fig.add_hline(y=-10, line_color="green", line_dash="dot",
                         annotation_text="Strong", row=row_idx, col=1)
            fig.add_hline(y=-25, line_color="orange", line_dash="dot",
                         annotation_text="Weak", row=row_idx, col=1)

            fig.update_yaxes(title_text="RSSI (dBFS)", row=row_idx, col=1)
            row_idx += 1

        # Messages and distance
        if has_messages or has_distance:
            if has_messages:
                fig.add_trace(
                    go.Scatter(
                        x=df["datetime"],
                        y=df["messages"],
                        name="Messages",
                        line=dict(color="green", width=1.5),
                        hovertemplate="<b>%{y} msgs</b><extra></extra>"
                    ),
                    row=row_idx, col=1, secondary_y=False
                )
                fig.update_yaxes(title_text="Message Count", row=row_idx, col=1, secondary_y=False)

            if has_distance:
                fig.add_trace(
                    go.Scatter(
                        x=df["datetime"],
                        y=df["r_dst"],
                        name="Distance",
                        line=dict(color="magenta", width=1.5),
                        hovertemplate="<b>%{y:.1f} nm</b><extra></extra>"
                    ),
                    row=row_idx, col=1, secondary_y=True
                )
                fig.update_yaxes(title_text="Distance (nm)", row=row_idx, col=1, secondary_y=True)

        # Layout
        fig.update_layout(
            title=self.title,
            hovermode="x unified",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=300 * n_rows,
        )

        fig.update_xaxes(title_text="Time (UTC)", row=n_rows, col=1)

        return fig
