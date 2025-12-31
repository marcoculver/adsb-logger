#!/usr/bin/env python3
"""
High-fidelity ADS-B state logger (tar1090/readsb aircraft.json) -> segmented JSONL(.gz)

Design goals:
- Poll aircraft.json at fixed interval (default 1.0s)
- Log all aircraft with selected fields (no _raw duplication for storage efficiency)
- Robust segmented files:
    * Current hour writes to a plain .jsonl (always readable while running)
    * When the hour rolls over, we compress that hour to .jsonl.gz and delete the plain file
  This avoids the "gzip: unexpected end of file" issue when you try to read while the logger is still writing.

Note: Pruning is handled by the external adsb-pipeline.sh script, not by this logger.

Output files (UTC):
  /opt/adsb-logs/adsb_state_YYYY-MM-DD_HH.jsonl        (active hour)
  /opt/adsb-logs/adsb_state_YYYY-MM-DD_HH.jsonl.gz     (finalized hours)
"""

import argparse
import gzip
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("adsb_logger")


# ---- Fields to keep ----
KEEP_FIELDS = [
    "hex", "flight",
    "lat", "lon",
    "alt_baro", "alt_geom",
    "gs", "ias", "tas", "mach",
    "track", "track_rate",
    "mag_heading", "true_heading", "calc_track",
    "roll",
    "baro_rate", "geom_rate",
    "wd", "ws", "oat", "tat",
    "squawk", "category", "emergency",
    "nav_qnh", "nav_heading", "nav_altitude_mcp", "nav_altitude_fms",
    "nic", "nac_p", "nac_v", "sil", "gva", "sda",
    "rssi", "seen", "seen_pos", "messages",
    "r_dst", "r_dir",
    "mlat", "tisb",
    # aircraft identity fields
    "t",       # ICAO type designator (e.g. B738)
    "r",       # registration
    "desc",    # description
    "ownOp",   # owner/operator
]


STOP = False


def utc_now():
    return datetime.now(timezone.utc)


def hour_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d_%H")


def active_jsonl_path(outdir: str, key: str) -> str:
    return os.path.join(outdir, f"adsb_state_{key}.jsonl")


def finalized_gz_path(outdir: str, key: str) -> str:
    return os.path.join(outdir, f"adsb_state_{key}.jsonl.gz")


def fetch_json(url: str, timeout: float) -> dict:
    req = Request(url, headers={"Cache-Control": "no-cache"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def compress_file_to_gz(src_path: str, dst_path: str) -> bool:
    """
    Compress src_path -> dst_path atomically.
    Returns True on success, False if source doesn't exist.
    """
    if not os.path.exists(src_path):
        return False

    tmp = dst_path + ".part"
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    src_size = os.path.getsize(src_path)

    with open(src_path, "rb") as fin, gzip.open(tmp, "wb", compresslevel=6) as fout:
        while True:
            chunk = fin.read(1024 * 1024)
            if not chunk:
                break
            fout.write(chunk)

    os.replace(tmp, dst_path)
    dst_size = os.path.getsize(dst_path)
    os.remove(src_path)

    return True, src_size, dst_size


def handle_stop(signum, frame):
    global STOP
    log.info("Received signal %d, shutting down gracefully...", signum)
    STOP = True


def build_record(a: dict, ts_epoch: int, ts_iso: str, poll_idx: int) -> dict:
    rec = {
        "_ts": ts_epoch,
        "_ts_iso": ts_iso,
        "_poll": poll_idx,
    }

    # Preserve tar1090/readsb "type" but rename to src
    if "type" in a:
        rec["src"] = a.get("type")

    # Keep selected fields only (no _raw to save storage)
    for k in KEEP_FIELDS:
        if k in a:
            rec[k] = a[k]

    return rec


def main():
    p = argparse.ArgumentParser(
        description="ADS-B aircraft.json logger with hourly rotation and compression"
    )
    p.add_argument("--url", default="http://127.0.0.1:8080/data/aircraft.json",
                   help="tar1090/readsb aircraft.json URL (default: %(default)s)")
    p.add_argument("--outdir", default="/opt/adsb-logs",
                   help="output directory (default: %(default)s)")
    p.add_argument("--tick", type=float, default=1.0,
                   help="poll interval in seconds (default: %(default)s)")
    p.add_argument("--timeout", type=float, default=2.0,
                   help="HTTP timeout in seconds (default: %(default)s)")
    p.add_argument("--fsync-every", type=float, default=1.0,
                   help="fsync interval in seconds (default: %(default)s)")
    p.add_argument("--quiet", action="store_true",
                   help="reduce logging verbosity")
    args = p.parse_args()

    if args.quiet:
        log.setLevel(logging.WARNING)

    os.makedirs(args.outdir, exist_ok=True)

    # Signals
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    log.info("Starting ADS-B logger")
    log.info("  URL: %s", args.url)
    log.info("  Output: %s", args.outdir)
    log.info("  Poll interval: %.1fs", args.tick)

    current_key = None
    f = None
    last_fsync = time.monotonic()
    poll_idx = 0
    consecutive_errors = 0
    hour_aircraft_count = 0
    hour_record_count = 0

    def open_for_key(key: str):
        nonlocal f, hour_aircraft_count, hour_record_count
        path = active_jsonl_path(args.outdir, key)
        f = open(path, "a", buffering=1, encoding="utf-8")
        hour_aircraft_count = 0
        hour_record_count = 0
        log.info("Opened new log file: %s", os.path.basename(path))

    def close_and_finalize(key: str):
        nonlocal f
        if f:
            try:
                f.flush()
                os.fsync(f.fileno())
            except Exception:
                pass
            try:
                f.close()
            except Exception:
                pass
            f = None

        # Compress the finished hour
        src = active_jsonl_path(args.outdir, key)
        dst = finalized_gz_path(args.outdir, key)
        result = compress_file_to_gz(src, dst)

        if result and isinstance(result, tuple):
            _, src_size, dst_size = result
            ratio = (1 - dst_size / src_size) * 100 if src_size > 0 else 0
            log.info("Compressed %s: %.1f MB -> %.1f MB (%.0f%% reduction)",
                     os.path.basename(dst),
                     src_size / 1024 / 1024,
                     dst_size / 1024 / 1024,
                     ratio)

    try:
        while not STOP:
            loop_start = time.monotonic()
            now_dt = utc_now()
            ts_epoch = int(now_dt.timestamp())
            ts_iso = now_dt.isoformat().replace("+00:00", "Z")
            key = hour_key(now_dt)

            # Roll to new hour
            if current_key is None:
                current_key = key
                open_for_key(current_key)
            elif key != current_key:
                log.info("Hour complete: %s - %d records from %d unique aircraft",
                         current_key, hour_record_count, hour_aircraft_count)
                close_and_finalize(current_key)
                current_key = key
                open_for_key(current_key)

            poll_idx += 1

            # Fetch aircraft data
            try:
                blob = fetch_json(args.url, args.timeout)
                aircraft = blob.get("aircraft", [])
                if consecutive_errors > 0:
                    log.info("Connection restored after %d failed attempts", consecutive_errors)
                consecutive_errors = 0
            except (URLError, TimeoutError, OSError) as e:
                consecutive_errors += 1
                if consecutive_errors == 1:
                    log.warning("Fetch failed: %s", e)
                elif consecutive_errors == 10:
                    log.error("Fetch has failed %d times consecutively", consecutive_errors)
                elif consecutive_errors % 60 == 0:
                    log.error("Fetch still failing after %d attempts (%.0f minutes)",
                              consecutive_errors, consecutive_errors * args.tick / 60)
                aircraft = []
            except Exception as e:
                consecutive_errors += 1
                log.exception("Unexpected error fetching data: %s", e)
                aircraft = []

            # Write records
            if aircraft and f:
                seen_hex = set()
                for a in aircraft:
                    hx = (a.get("hex") or "").strip().lower()
                    if not hx:
                        continue
                    seen_hex.add(hx)
                    rec = build_record(a, ts_epoch, ts_iso, poll_idx)
                    f.write(json.dumps(rec, separators=(",", ":")) + "\n")
                    hour_record_count += 1
                hour_aircraft_count = max(hour_aircraft_count, len(seen_hex))

            # Fsync pacing
            now_m = time.monotonic()
            if f and (now_m - last_fsync) >= args.fsync_every:
                try:
                    f.flush()
                    os.fsync(f.fileno())
                except Exception:
                    pass
                last_fsync = now_m

            # Maintain tick interval
            elapsed = time.monotonic() - loop_start
            if elapsed < args.tick:
                time.sleep(args.tick - elapsed)

    except Exception as e:
        log.exception("Fatal error in main loop: %s", e)
        raise
    finally:
        if current_key:
            log.info("Finalizing current hour: %s", current_key)
            close_and_finalize(current_key)
        log.info("Logger stopped")


if __name__ == "__main__":
    main()
