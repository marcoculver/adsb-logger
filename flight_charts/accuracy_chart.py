"""Position accuracy chart (NIC/NAC quality indicators)."""
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


class AccuracyChart(BaseChart):
    """
    Position accuracy chart showing ADS-B quality indicators.

    Features:
    - NIC (Navigation Integrity Category)
    - NAC_p (Navigational Accuracy Category - Position)
    - NAC_v (Navigational Accuracy Category - Velocity)
    - SIL (Surveillance Integrity Level)
    """

    @property
    def name(self) -> str:
        return "position_accuracy"

    @property
    def title(self) -> str:
        return f"{self.callsign} - Position Accuracy (NIC/NAC)"

    def _create_matplotlib_figure(self) -> Optional['plt.Figure']:
        if not HAS_MATPLOTLIB or self.df is None:
            return None

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_nic = "nic" in df.columns and df["nic"].notna().any()
        has_nac_p = "nac_p" in df.columns and df["nac_p"].notna().any()
        has_nac_v = "nac_v" in df.columns and df["nac_v"].notna().any()
        has_sil = "sil" in df.columns and df["sil"].notna().any()

        metrics = [(has_nic, "nic", "NIC", "blue"),
                   (has_nac_p, "nac_p", "NAC_p", "green"),
                   (has_nac_v, "nac_v", "NAC_v", "red"),
                   (has_sil, "sil", "SIL", "purple")]

        available = [(col, label, color) for has, col, label, color in metrics if has]

        if not available:
            log.warning("No accuracy data for chart")
            return None

        fig, ax = plt.subplots(1, 1, figsize=(12, 5))

        for col, label, color in available:
            ax.plot(df["datetime"], df[col], "-", linewidth=1.5,
                   label=label, color=color, alpha=0.8)

        ax.set_ylabel("Value")
        ax.set_xlabel("Time (UTC)")
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        ax.set_title(self.title)

        # NIC typically ranges 0-11, NAC 0-11, SIL 0-3
        # Set reasonable y-axis limits
        ax.set_ylim(-0.5, 12)

        # Add quality guidance
        ax.axhspan(8, 12, alpha=0.1, color="green", label="High accuracy")
        ax.axhspan(4, 8, alpha=0.1, color="yellow")
        ax.axhspan(0, 4, alpha=0.1, color="red")

        self._format_time_axis(ax)
        plt.tight_layout()
        return fig

    def _create_plotly_figure(self) -> Optional['go.Figure']:
        if not HAS_PLOTLY or self.df is None:
            return None

        df = self.df

        if "datetime" not in df.columns:
            return None

        has_nic = "nic" in df.columns and df["nic"].notna().any()
        has_nac_p = "nac_p" in df.columns and df["nac_p"].notna().any()
        has_nac_v = "nac_v" in df.columns and df["nac_v"].notna().any()
        has_sil = "sil" in df.columns and df["sil"].notna().any()

        metrics = [(has_nic, "nic", "NIC", "blue"),
                   (has_nac_p, "nac_p", "NAC_p", "green"),
                   (has_nac_v, "nac_v", "NAC_v", "red"),
                   (has_sil, "sil", "SIL", "purple")]

        available = [(col, label, color) for has, col, label, color in metrics if has]

        if not available:
            return None

        fig = go.Figure()

        # Quality bands
        fig.add_hrect(y0=8, y1=12, fillcolor="green", opacity=0.1,
                     annotation_text="High accuracy", annotation_position="right")
        fig.add_hrect(y0=4, y1=8, fillcolor="yellow", opacity=0.1,
                     annotation_text="Medium", annotation_position="right")
        fig.add_hrect(y0=0, y1=4, fillcolor="red", opacity=0.1,
                     annotation_text="Low", annotation_position="right")

        for col, label, color in available:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df[col],
                    name=label,
                    line=dict(color=color, width=2),
                    hovertemplate=f"<b>{label}: %{{y}}</b><extra></extra>"
                )
            )

        fig.update_layout(
            title=self.title,
            hovermode="x unified",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=400,
            yaxis=dict(title="Value", range=[-0.5, 12]),
            xaxis=dict(title="Time (UTC)"),
        )

        return fig

    def get_accuracy_summary(self) -> dict:
        """Get summary statistics for accuracy indicators."""
        if self.df is None:
            return {}

        summary = {}

        for col in ["nic", "nac_p", "nac_v", "sil"]:
            if col in self.df.columns and self.df[col].notna().any():
                summary[col] = {
                    "min": int(self.df[col].min()),
                    "max": int(self.df[col].max()),
                    "mean": round(self.df[col].mean(), 1),
                    "mode": int(self.df[col].mode().iloc[0]) if len(self.df[col].mode()) > 0 else None,
                }

        return summary
