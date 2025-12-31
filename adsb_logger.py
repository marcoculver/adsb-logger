#!/usr/bin/env python3
"""
High-fidelity ADS-B state logger (tar1090/readsb aircraft.json) -> segmented JSONL(.gz)

Design goals:
- Poll aircraft.json at fixed interval (default 1.0s)
- Log *all* aircraft, keep your old "extras", and keep full _raw record
- Robust segmented files:
    * Current hour writes to a plain .jsonl (always readable while running)
    * When the hour rolls over, we compress that hour to .jsonl.gz and delete the plain file
  This avoids the "gzip: unexpected end of file" issue when you try to read while the logger is still writing.
- Rolling retention (keep last N days of segments; default 30)

Output files (UTC):
  /opt/adsb-logs/adsb_state_YYYY-MM-DD_HH.jsonl        (active hour)
  /opt/adsb-logs/adsb_state_YYYY-MM-DD_HH.jsonl.gz     (finalized hours)
"""

import argparse
import gzip
import json
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen


# ---- Fields to keep (matches your previous "old extras" list) ----
KEEP_FIELDS = [
    "hex","flight",
    "lat","lon",
    "alt_baro","alt_geom",
    "gs","ias","tas","mach",
    "track","track_rate",
    "mag_heading","true_heading","calc_track",
    "roll",
    "baro_rate","geom_rate",
    "wd","ws","oat","tat",
    "squawk","category","emergency",
    "nav_qnh","nav_heading","nav_altitude_mcp","nav_altitude_fms",
    "nic","nac_p","nac_v","sil","gva","sda",
    "rssi","seen","seen_pos","messages",
    "r_dst","r_dir",
    "mlat","tisb",

    # aircraft identity fields
    "t",      # ICAO type designator (e.g. B738)
    "r",      # registration
    "desc",   # description
    "ownOp"   # sometimes present
]


STOP = False


def utc_now():
    return datetime.now(timezone.utc)


def hour_key(dt: datetime) -> str:
    # dt must be UTC
    return dt.strftime("%Y-%m-%d_%H")


def active_jsonl_path(outdir: str, key: str) -> str:
    return os.path.join(outdir, f"adsb_state_{key}.jsonl")


def finalized_gz_path(outdir: str, key: str) -> str:
    return os.path.join(outdir, f"adsb_state_{key}.jsonl.gz")


def fetch_json(url: str, timeout: float) -> dict:
    req = Request(url, headers={"Cache-Control": "no-cache"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def compress_file_to_gz(src_path: str, dst_path: str) -> None:
    """
    Compress src_path -> dst_path atomically:
      write to dst_path.part then rename
    """
    if not os.path.exists(src_path):
        return

    tmp = dst_path + ".part"
    # Make sure destination directory exists
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    with open(src_path, "rb") as fin, gzip.open(tmp, "wb", compresslevel=6) as fout:
        while True:
            chunk = fin.read(1024 * 1024)
            if not chunk:
                break
            fout.write(chunk)

    os.replace(tmp, dst_path)
    os.remove(src_path)


def parse_key_from_name(name: str) -> str | None:
    # adsb_state_YYYY-MM-DD_HH.jsonl(.gz)
    if not name.startswith("adsb_state_"):
        return None
    if name.endswith(".jsonl.gz"):
        core = name[len("adsb_state_") : -len(".jsonl.gz")]
    elif name.endswith(".jsonl"):
        core = name[len("adsb_state_") : -len(".jsonl")]
    else:
        return None

    # sanity: "2025-12-21_23"
    if len(core) != 13 or core[4] != "-" or core[7] != "-" or core[10] != "_":
        return None
    return core


def key_to_datetime_utc(key: str) -> datetime | None:
    try:
        return datetime.strptime(key, "%Y-%m-%d_%H").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def prune_old(outdir: str, keep_days: int) -> None:
    cutoff = utc_now() - timedelta(days=keep_days)
    for name in os.listdir(outdir):
        key = parse_key_from_name(name)
        if not key:
            continue
        dt = key_to_datetime_utc(key)
        if not dt:
            continue
        if dt < cutoff:
            try:
                os.remove(os.path.join(outdir, name))
            except FileNotFoundError:
                pass


def handle_stop(signum, frame):
    global STOP
    STOP = True


def build_record(a: dict, ts_epoch: int, ts_iso: str, poll_idx: int) -> dict:
    rec = {
        "_ts": ts_epoch,
        "_ts_iso": ts_iso,
        "_poll": poll_idx,
    }

    # Preserve tar1090/readsb "type" but rename to src (your old behavior)
    if "type" in a:
        rec["src"] = a.get("type")

    # Keep normal fields
    for k in KEEP_FIELDS:
        if k in a:
            rec[k] = a.get(k)

    # Keep full raw object for later pandas/KML/CSV etc
    rec["_raw"] = a
    return rec


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8080/data/aircraft.json",
                   help="tar1090/readsb aircraft.json URL")
    p.add_argument("--outdir", default="/opt/adsb-logs",
                   help="output directory")
    p.add_argument("--tick", type=float, default=1.0,
                   help="poll interval seconds (default 1.0)")
    p.add_argument("--keep-days", type=int, default=30,
                   help="how many days of segments to keep (default 30)")
    p.add_argument("--timeout", type=float, default=2.0,
                   help="HTTP timeout seconds (default 2.0)")
    p.add_argument("--fsync-every", type=float, default=1.0,
                   help="fsync interval seconds (default 1.0)")
    p.add_argument("--prune-every", type=float, default=3600.0,
                   help="how often to prune old segments seconds (default 3600)")
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Signals
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    current_key = None
    f = None
    last_fsync = time.monotonic()
    last_prune = time.monotonic()
    poll_idx = 0

    def open_for_key(key: str):
        nonlocal f
        path = active_jsonl_path(args.outdir, key)
        # line buffered
        f = open(path, "a", buffering=1, encoding="utf-8")

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

        # Compress the finished hour .jsonl -> .jsonl.gz
        src = active_jsonl_path(args.outdir, key)
        dst = finalized_gz_path(args.outdir, key)
        compress_file_to_gz(src, dst)

    try:
        while not STOP:
            loop_start = time.monotonic()
            now_dt = utc_now()
            ts_epoch = int(now_dt.timestamp())
            ts_iso = now_dt.isoformat().replace("+00:00", "Z")
            key = hour_key(now_dt)

            # roll to new hour
            if current_key is None:
                current_key = key
                open_for_key(current_key)
            elif key != current_key:
                close_and_finalize(current_key)
                current_key = key
                open_for_key(current_key)
                # When hour rolls, prune (cheap + sensible)
                prune_old(args.outdir, args.keep_days)
                last_prune = time.monotonic()

            poll_idx += 1

            try:
                blob = fetch_json(args.url, args.timeout)
                aircraft = blob.get("aircraft", [])
            except Exception:
                aircraft = []

            # Write one line per aircraft per poll
            if aircraft and f:
                for a in aircraft:
                    hx = (a.get("hex") or "").strip().lower()
                    if not hx:
                        continue
                    rec = build_record(a, ts_epoch, ts_iso, poll_idx)
                    f.write(json.dumps(rec, separators=(",", ":")) + "\n")

            # fsync pacing
            now_m = time.monotonic()
            if f and (now_m - last_fsync) >= args.fsync_every:
                try:
                    f.flush()
                    os.fsync(f.fileno())
                except Exception:
                    pass
                last_fsync = now_m

            # prune pacing (in case you want it independent of hour roll)
            if (now_m - last_prune) >= args.prune_every:
                prune_old(args.outdir, args.keep_days)
                last_prune = now_m

            # maintain tick
            elapsed = time.monotonic() - loop_start
            if elapsed < args.tick:
                time.sleep(args.tick - elapsed)

    finally:
        # finalize the active hour on exit (so you always get a closed .gz)
        if current_key:
            close_and_finalize(current_key)


if __name__ == "__main__":
    main()
