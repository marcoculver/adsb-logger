#!/usr/bin/env bash
set -euo pipefail

BASE="/opt/adsb-logs"

# Only move CLOSED files (gzipped). Never touch the active .jsonl.
shopt -s nullglob
for f in "$BASE"/adsb_state_*.jsonl.gz; do
  bn="$(basename "$f")"

  # Match: adsb_state_YYYY-MM-DD_HH.jsonl.gz  OR  adsb_state_YYYY-MM-DD.jsonl.gz
  if [[ "$bn" =~ ^adsb_state_([0-9]{4})-([0-9]{2})-([0-9]{2})(_[0-9]{2})?\.jsonl\.gz$ ]]; then
    Y="${BASH_REMATCH[1]}"
    M="${BASH_REMATCH[2]}"
    D="${BASH_REMATCH[3]}"

    dest="$BASE/$Y/$M/$D"
    mkdir -p "$dest"

    # Move only if not already there
    if [[ ! -e "$dest/$bn" ]]; then
      mv "$f" "$dest/$bn"
    fi
  fi
done
