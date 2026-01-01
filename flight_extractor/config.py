"""Configuration for flight data extraction system."""
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Detect platform and set default paths
if sys.platform == "win32":
    DEFAULT_LOG_DIR = Path(r"M:\Dropbox\ADSBPi-Base\raw")
    DEFAULT_OUTPUT_DIR = Path(r"M:\Dropbox\ADSBPi-Base\analyses")
else:
    DEFAULT_LOG_DIR = Path("/opt/adsb-logs")
    DEFAULT_OUTPUT_DIR = Path("/opt/adsb-analyses")

# File naming patterns
FILE_PREFIX = "adsb_state_"
FILE_SUFFIX_JSONL = ".jsonl"
FILE_SUFFIX_GZ = ".jsonl.gz"

# Midnight crossover settings
MAX_CROSSOVER_HOURS = 6  # Max hours to look ahead/behind for continuing flight
FLIGHT_GAP_THRESHOLD_SECONDS = 300  # 5 minutes - gap to consider flight ended
MIDNIGHT_WINDOW_HOURS = 3  # Hours before/after midnight to check for crossover

# CSV column groups - ordered for logical reading
CSV_COLUMN_GROUPS: Dict[str, List[str]] = {
    "timestamp": ["_ts", "_ts_iso"],
    "identity": ["hex", "flight", "squawk", "category", "t", "r", "desc", "ownOp"],
    "position": ["lat", "lon", "alt_baro", "alt_geom"],
    "velocity": ["gs", "ias", "tas", "mach", "baro_rate", "geom_rate"],
    "direction": ["track", "true_heading", "mag_heading", "calc_track", "track_rate", "roll"],
    "atmospheric": ["wd", "ws", "oat", "tat"],
    "navigation": ["nav_altitude_mcp", "nav_altitude_fms", "nav_heading", "nav_qnh"],
    "data_quality": ["nic", "nac_p", "nac_v", "sil", "gva", "sda", "rssi"],
    "signal": ["messages", "seen", "seen_pos", "r_dst", "r_dir"],
    "source": ["src", "mlat", "tisb", "_poll"],
}

# Flattened column order for CSV export
CSV_COLUMN_ORDER: List[str] = []
for group_cols in CSV_COLUMN_GROUPS.values():
    CSV_COLUMN_ORDER.extend(group_cols)

# All fields that might appear in records (from adsb_logger.py KEEP_FIELDS + metadata)
ALL_FIELDS = [
    # Metadata
    "_ts", "_ts_iso", "_poll", "src",
    # Identity
    "hex", "flight", "t", "r", "desc", "ownOp",
    # Position
    "lat", "lon", "alt_baro", "alt_geom",
    # Velocity
    "gs", "ias", "tas", "mach",
    # Rates
    "baro_rate", "geom_rate",
    # Direction
    "track", "track_rate", "mag_heading", "true_heading", "calc_track", "roll",
    # Atmospheric
    "wd", "ws", "oat", "tat",
    # Transponder
    "squawk", "category", "emergency",
    # Navigation
    "nav_qnh", "nav_heading", "nav_altitude_mcp", "nav_altitude_fms",
    # Quality
    "nic", "nac_p", "nac_v", "sil", "gva", "sda",
    # Signal
    "rssi", "seen", "seen_pos", "messages", "r_dst", "r_dir",
    # Source
    "mlat", "tisb",
]

# KML altitude color scale (altitude_ft, KML color in aabbggrr format)
KML_ALTITUDE_COLORS = [
    (0, "ff0000ff"),       # Red: ground level
    (10000, "ff00a5ff"),   # Orange: 0-10k ft
    (20000, "ff00ffff"),   # Yellow: 10k-20k ft
    (30000, "ff00ff00"),   # Green: 20k-30k ft
    (40000, "ffff7f00"),   # Cyan: 30k-40k ft
    (50000, "ffff0000"),   # Blue: 40k+ ft
]

# Telegram bot settings
TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_ALLOWED_USERS_ENV = "TELEGRAM_ALLOWED_USERS"


@dataclass
class Config:
    """Runtime configuration for the extraction system."""

    log_dir: Path = field(default_factory=lambda: DEFAULT_LOG_DIR)
    output_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR)

    # Crossover detection
    max_crossover_hours: int = MAX_CROSSOVER_HOURS
    flight_gap_threshold: int = FLIGHT_GAP_THRESHOLD_SECONDS
    midnight_window_hours: int = MIDNIGHT_WINDOW_HOURS

    # Chart generation
    generate_png: bool = True
    generate_html: bool = True
    chart_dpi: int = 150
    max_chart_points: int = 10000  # Decimate if more points

    # Telegram
    telegram_token: Optional[str] = None
    allowed_user_ids: List[int] = field(default_factory=list)

    def __post_init__(self):
        """Load from environment variables if not set."""
        if self.telegram_token is None:
            self.telegram_token = os.environ.get(TELEGRAM_TOKEN_ENV)

        if not self.allowed_user_ids:
            users_str = os.environ.get(TELEGRAM_ALLOWED_USERS_ENV, "")
            if users_str:
                self.allowed_user_ids = [
                    int(uid.strip())
                    for uid in users_str.split(",")
                    if uid.strip().isdigit()
                ]

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        config = cls()

        # Override paths from env if set
        if log_dir := os.environ.get("ADSB_LOG_DIR"):
            config.log_dir = Path(log_dir)
        if output_dir := os.environ.get("ADSB_OUTPUT_DIR"):
            config.output_dir = Path(output_dir)

        return config
