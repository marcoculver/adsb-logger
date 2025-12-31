#!/usr/bin/env bash
set -euo pipefail

SRC="/opt/adsb-logs"
DST="dropbox:ADSBPi-Base/raw"

rclone copy "$SRC" "$DST" \
  --filter "+ **/*.jsonl.gz" \
  --filter "- **/*" \
  --transfers=4 \
  --checkers=8 \
  --log-level INFO
