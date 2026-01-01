"""Flight phase detection and visualization."""
import logging
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np

from .base import BaseChart, HAS_MATPLOTLIB, HAS_PLOTLY, HAS_PANDAS

if HAS_MATPLOTLIB:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
if HAS_PLOTLY:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
if HAS_PANDAS:
    import pandas as pd

log = logging.getLogger(__name__)


# Flight phase definitions
PHASE_COLORS = {
    "ground": "#808080",      # Gray
    "takeoff": "#00FF00",     # Green
    "climb": "#32CD32",       # Lime green
    "cruise": "#1E90FF",      # Dodger blue
    "descent": "#FFA500",     # Orange
    "approach": "#FF6347",    # Tomato
    "landing": "#FF0000",     # Red
    "unknown": "#CCCCCC",     # Light gray
}

PHASE_ORDER = ["ground", "takeoff", "climb", "cruise", "descent", "approach", "landing"]


def detect_flight_phases(df: 'pd.DataFrame') -> 'pd.Series':
    """
    Detect flight phases based on altitude and vertical rate.

    Phases:
    - ground: altitude < 500 ft and low speed
    - takeoff: altitude < 5000 ft and climbing rapidly from ground
    - climb: positive vertical rate > 500 ft/min
    - cruise: stable altitude (vertical rate < 300 ft/min)
    - descent: negative vertical rate < -500 ft/min
    - approach: altitude < 5000 ft and descending
    - landing: altitude < 500 ft and descending/slowing

    Returns:
        Series with phase labels
    """
    phases = pd.Series(index=df.index, dtype=str)
    phases[:] = "unknown"

    # Get required columns
    alt = df.get("alt_baro", df.get("alt_geom", pd.Series()))
    vrate = df.get("baro_rate", df.get("geom_rate", pd.Series()))
    gs = df.get("gs", pd.Series())

    if alt.isna().all():
        return phases

    # Fill NaN values for calculations
    alt = pd.to_numeric(alt, errors='coerce').fillna(method='ffill').fillna(method='bfill')
    vrate = pd.to_numeric(vrate, errors='coerce').fillna(0)
    gs = pd.to_numeric(gs, errors='coerce').fillna(0)

    # Smooth the data to reduce noise
    if len(alt) > 10:
        alt_smooth = alt.rolling(window=10, center=True, min_periods=1).mean()
        vrate_smooth = vrate.rolling(window=10, center=True, min_periods=1).mean()
    else:
        alt_smooth = alt
        vrate_smooth = vrate

    # Determine max altitude for this flight
    max_alt = alt_smooth.max()
    cruise_threshold = max_alt * 0.85 if max_alt > 10000 else max_alt * 0.7

    # Classify each point
    for i in range(len(df)):
        a = alt_smooth.iloc[i]
        v = vrate_smooth.iloc[i]
        s = gs.iloc[i] if len(gs) > i else 0

        # Ground
        if a < 500 and s < 50:
            phases.iloc[i] = "ground"
        # Takeoff
        elif a < 3000 and v > 500 and i < len(df) * 0.2:
            phases.iloc[i] = "takeoff"
        # Landing
        elif a < 500 and v < 0 and i > len(df) * 0.7:
            phases.iloc[i] = "landing"
        # Approach
        elif a < 5000 and v < -200 and i > len(df) * 0.6:
            phases.iloc[i] = "approach"
        # Climb
        elif v > 300:
            phases.iloc[i] = "climb"
        # Descent
        elif v < -300:
            phases.iloc[i] = "descent"
        # Cruise
        elif a > cruise_threshold and abs(v) < 500:
            phases.iloc[i] = "cruise"
        # Default to climb or descent based on vertical rate
        elif v > 0:
            phases.iloc[i] = "climb"
        elif v < 0:
            phases.iloc[i] = "descent"
        else:
            phases.iloc[i] = "cruise"

    return phases


def get_phase_summary(phases: 'pd.Series', df: 'pd.DataFrame') -> List[dict]:
    """
    Get summary of each flight phase with timing and statistics.
    """
    if "datetime" not in df.columns:
        return []

    summary = []
    current_phase = None
    phase_start = None
    phase_start_idx = None

    for i, phase in enumerate(phases):
        if phase != current_phase:
            # End previous phase
            if current_phase is not None:
                phase_end = df["datetime"].iloc[i-1]
                duration = (phase_end - phase_start).total_seconds() / 60

                # Get altitude stats for this phase
                phase_alt = df["alt_baro"].iloc[phase_start_idx:i] if "alt_baro" in df.columns else None

                summary.append({
                    "phase": current_phase,
                    "start": phase_start,
                    "end": phase_end,
                    "duration_min": duration,
                    "start_alt": phase_alt.iloc[0] if phase_alt is not None and len(phase_alt) > 0 else None,
                    "end_alt": phase_alt.iloc[-1] if phase_alt is not None and len(phase_alt) > 0 else None,
                })

            # Start new phase
            current_phase = phase
            phase_start = df["datetime"].iloc[i]
            phase_start_idx = i

    # End final phase
    if current_phase is not None:
        phase_end = df["datetime"].iloc[-1]
        duration = (phase_end - phase_start).total_seconds() / 60
        phase_alt = df["alt_baro"].iloc[phase_start_idx:] if "alt_baro" in df.columns else None

        summary.append({
            "phase": current_phase,
            "start": phase_start,
            "end": phase_end,
            "duration_min": duration,
            "start_alt": phase_alt.iloc[0] if phase_alt is not None and len(phase_alt) > 0 else None,
            "end_alt": phase_alt.iloc[-1] if phase_alt is not None and len(phase_alt) > 0 else None,
        })

    return summary


class FlightPhaseChart(BaseChart):
    """
    Flight phase visualization showing altitude colored by phase.

    Features:
    - Altitude profile colored by detected phase
    - Phase timeline bar
    - Phase duration summary
    """

    @property
    def name(self) -> str:
        return "flight_phases"

    @property
    def title(self) -> str:
        return f"{self.callsign} - Flight Phases"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.df is not None and HAS_PANDAS:
            self.phases = detect_flight_phases(self.df)
            self.phase_summary = get_phase_summary(self.phases, self.df)
        else:
            self.phases = None
            self.phase_summary = []

    def _create_matplotlib_figure(self) -> Optional['plt.Figure']:
        if not HAS_MATPLOTLIB or self.df is None or self.phases is None:
            return None

        df = self.df
        phases = self.phases

        if "datetime" not in df.columns:
            return None

        has_alt = "alt_baro" in df.columns and df["alt_baro"].notna().any()
        if not has_alt:
            return None

        # Create figure with altitude plot and phase bar
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7),
                                        gridspec_kw={"height_ratios": [4, 1]},
                                        sharex=True)

        # Plot altitude colored by phase
        for phase in PHASE_ORDER:
            mask = phases == phase
            if mask.any():
                ax1.scatter(df.loc[mask, "datetime"],
                           df.loc[mask, "alt_baro"],
                           c=PHASE_COLORS[phase],
                           s=2, alpha=0.7, label=phase.capitalize())

        ax1.set_ylabel("Altitude (ft)")
        ax1.set_title(self.title)
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc="upper right", ncol=4, fontsize=8)

        # Format y-axis
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(
            lambda x, p: f"{x/1000:.0f}k" if x >= 1000 else f"{x:.0f}"))

        # Phase timeline bar
        for i, (phase, x) in enumerate(zip(phases, df["datetime"])):
            ax2.axvline(x=x, color=PHASE_COLORS.get(phase, "#CCCCCC"),
                       linewidth=2, alpha=0.8)

        ax2.set_ylim(0, 1)
        ax2.set_yticks([])
        ax2.set_xlabel("Time (UTC)")

        # Create legend patches
        patches = [mpatches.Patch(color=PHASE_COLORS[p], label=p.capitalize())
                   for p in PHASE_ORDER if (phases == p).any()]
        ax2.legend(handles=patches, loc="upper center", ncol=len(patches),
                   fontsize=8, framealpha=0.9)

        self._format_time_axis(ax2)
        plt.tight_layout()

        return fig

    def _create_plotly_figure(self) -> Optional['go.Figure']:
        if not HAS_PLOTLY or self.df is None or self.phases is None:
            return None

        df = self.df
        phases = self.phases

        if "datetime" not in df.columns:
            return None

        has_alt = "alt_baro" in df.columns and df["alt_baro"].notna().any()
        if not has_alt:
            return None

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.85, 0.15],
            subplot_titles=(self.title, "Flight Phase")
        )

        # Plot altitude for each phase
        for phase in PHASE_ORDER:
            mask = phases == phase
            if mask.any():
                fig.add_trace(
                    go.Scatter(
                        x=df.loc[mask, "datetime"],
                        y=df.loc[mask, "alt_baro"],
                        mode="markers",
                        marker=dict(color=PHASE_COLORS[phase], size=4),
                        name=phase.capitalize(),
                        hovertemplate=f"<b>{phase.capitalize()}</b><br>Alt: %{{y:.0f}} ft<extra></extra>"
                    ),
                    row=1, col=1
                )

        # Phase timeline
        for phase in PHASE_ORDER:
            mask = phases == phase
            if mask.any():
                fig.add_trace(
                    go.Scatter(
                        x=df.loc[mask, "datetime"],
                        y=[0.5] * mask.sum(),
                        mode="markers",
                        marker=dict(color=PHASE_COLORS[phase], size=10, symbol="square"),
                        name=phase.capitalize(),
                        showlegend=False,
                        hovertemplate=f"<b>{phase.capitalize()}</b><extra></extra>"
                    ),
                    row=2, col=1
                )

        fig.update_layout(
            height=500,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )

        fig.update_yaxes(title_text="Altitude (ft)", row=1, col=1)
        fig.update_yaxes(visible=False, row=2, col=1)
        fig.update_xaxes(title_text="Time (UTC)", row=2, col=1)

        return fig
