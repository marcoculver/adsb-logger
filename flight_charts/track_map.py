"""Ground track map visualization."""
import logging
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

from .base import BaseChart, HAS_MATPLOTLIB, HAS_PLOTLY

if HAS_MATPLOTLIB:
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize
    import matplotlib.cm as cm
if HAS_PLOTLY:
    import plotly.graph_objects as go

log = logging.getLogger(__name__)


class TrackMapChart(BaseChart):
    """
    Ground track map showing the flight path colored by altitude.

    Features:
    - Flight path on lat/lon coordinates
    - Color coding by altitude
    - Start/end markers
    - Distance scale
    """

    @property
    def name(self) -> str:
        return "ground_track"

    @property
    def title(self) -> str:
        return f"{self.callsign} - Ground Track"

    def _create_matplotlib_figure(self) -> Optional['plt.Figure']:
        if not HAS_MATPLOTLIB or self.df is None:
            return None

        df = self.df

        has_lat = "lat" in df.columns and df["lat"].notna().any()
        has_lon = "lon" in df.columns and df["lon"].notna().any()

        if not has_lat or not has_lon:
            log.warning("No position data for track map")
            return None

        # Filter to rows with valid positions
        mask = df["lat"].notna() & df["lon"].notna()
        df_pos = df[mask].copy()

        if len(df_pos) < 2:
            return None

        lat = df_pos["lat"].values
        lon = df_pos["lon"].values

        # Get altitude for coloring
        if "alt_baro" in df_pos.columns:
            alt = df_pos["alt_baro"].fillna(0).values
        else:
            alt = np.zeros(len(df_pos))

        fig, ax = plt.subplots(1, 1, figsize=(10, 10))

        # Create line segments colored by altitude
        points = np.array([lon, lat]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)

        # Normalize altitude for colormap
        alt_min, alt_max = alt.min(), alt.max()
        if alt_max == alt_min:
            alt_max = alt_min + 1

        norm = Normalize(vmin=alt_min, vmax=alt_max)
        lc = LineCollection(segments, cmap='plasma', norm=norm, linewidth=2, alpha=0.8)
        lc.set_array(alt[:-1])
        ax.add_collection(lc)

        # Add colorbar
        cbar = plt.colorbar(lc, ax=ax, shrink=0.8, pad=0.02)
        cbar.set_label('Altitude (ft)')

        # Mark start and end
        ax.plot(lon[0], lat[0], 'go', markersize=12, label='Start', zorder=5)
        ax.plot(lon[-1], lat[-1], 'ro', markersize=12, label='End', zorder=5)

        # Mark max altitude point
        max_alt_idx = np.argmax(alt)
        ax.plot(lon[max_alt_idx], lat[max_alt_idx], 'b^', markersize=10,
               label=f'Max Alt ({alt[max_alt_idx]:.0f} ft)', zorder=5)

        # Set axis limits with padding
        lon_range = lon.max() - lon.min()
        lat_range = lat.max() - lat.min()
        padding = max(lon_range, lat_range) * 0.1

        ax.set_xlim(lon.min() - padding, lon.max() + padding)
        ax.set_ylim(lat.min() - padding, lat.max() + padding)

        # Equal aspect ratio
        ax.set_aspect('equal')

        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.set_title(self.title)
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        # Add distance info
        total_dist = self._calculate_distance(lat, lon)
        ax.text(0.02, 0.02, f'Total distance: {total_dist:.0f} nm',
               transform=ax.transAxes, fontsize=10,
               verticalalignment='bottom',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        plt.tight_layout()
        return fig

    def _create_plotly_figure(self) -> Optional['go.Figure']:
        if not HAS_PLOTLY or self.df is None:
            return None

        df = self.df

        has_lat = "lat" in df.columns and df["lat"].notna().any()
        has_lon = "lon" in df.columns and df["lon"].notna().any()

        if not has_lat or not has_lon:
            return None

        # Filter to rows with valid positions
        mask = df["lat"].notna() & df["lon"].notna()
        df_pos = df[mask].copy()

        if len(df_pos) < 2:
            return None

        lat = df_pos["lat"].values
        lon = df_pos["lon"].values

        # Get altitude for coloring
        if "alt_baro" in df_pos.columns:
            alt = df_pos["alt_baro"].fillna(0).values
        else:
            alt = np.zeros(len(df_pos))

        fig = go.Figure()

        # Main track colored by altitude
        fig.add_trace(go.Scattergeo(
            lon=lon,
            lat=lat,
            mode='lines+markers',
            marker=dict(
                size=4,
                color=alt,
                colorscale='Plasma',
                colorbar=dict(title='Altitude (ft)'),
                showscale=True
            ),
            line=dict(width=2, color='rgba(100,100,100,0.3)'),
            name='Flight Path',
            hovertemplate='<b>Position</b><br>Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<br>Alt: %{marker.color:.0f} ft<extra></extra>'
        ))

        # Start marker
        fig.add_trace(go.Scattergeo(
            lon=[lon[0]],
            lat=[lat[0]],
            mode='markers',
            marker=dict(size=15, color='green', symbol='circle'),
            name='Start',
            hovertemplate='<b>Start</b><br>Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<extra></extra>'
        ))

        # End marker
        fig.add_trace(go.Scattergeo(
            lon=[lon[-1]],
            lat=[lat[-1]],
            mode='markers',
            marker=dict(size=15, color='red', symbol='circle'),
            name='End',
            hovertemplate='<b>End</b><br>Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<extra></extra>'
        ))

        # Max altitude marker
        max_alt_idx = np.argmax(alt)
        fig.add_trace(go.Scattergeo(
            lon=[lon[max_alt_idx]],
            lat=[lat[max_alt_idx]],
            mode='markers',
            marker=dict(size=12, color='blue', symbol='triangle-up'),
            name=f'Max Alt ({alt[max_alt_idx]:.0f} ft)',
            hovertemplate=f'<b>Max Altitude</b><br>{alt[max_alt_idx]:.0f} ft<extra></extra>'
        ))

        # Calculate bounds
        lat_center = (lat.min() + lat.max()) / 2
        lon_center = (lon.min() + lon.max()) / 2

        fig.update_layout(
            title=self.title,
            geo=dict(
                projection_type='mercator',
                showland=True,
                landcolor='rgb(243, 243, 243)',
                countrycolor='rgb(204, 204, 204)',
                showocean=True,
                oceancolor='rgb(230, 245, 255)',
                showlakes=True,
                lakecolor='rgb(200, 230, 255)',
                showcountries=True,
                center=dict(lat=lat_center, lon=lon_center),
                lonaxis=dict(range=[lon.min() - 1, lon.max() + 1]),
                lataxis=dict(range=[lat.min() - 1, lat.max() + 1]),
            ),
            height=600,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )

        return fig

    def _calculate_distance(self, lat: np.ndarray, lon: np.ndarray) -> float:
        """Calculate total distance in nautical miles using haversine formula."""
        total_nm = 0.0

        for i in range(len(lat) - 1):
            lat1, lon1 = np.radians(lat[i]), np.radians(lon[i])
            lat2, lon2 = np.radians(lat[i+1]), np.radians(lon[i+1])

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            c = 2 * np.arcsin(np.sqrt(a))

            # Earth radius in nautical miles
            r_nm = 3440.065
            total_nm += r_nm * c

        return total_nm
