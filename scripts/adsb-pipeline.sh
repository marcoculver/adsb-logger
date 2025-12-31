#!/usr/bin/env bash
#
# ADS-B Log Pipeline
# Runs hourly to: organize -> verify Dropbox -> prune -> sync
#
set -euo pipefail

# Configuration
LOG_DIR="/opt/adsb-logs"
DROPBOX_REMOTE="dropbox:ADSBPi-Base/raw"
KEEP_DAYS=180
LOCK_FILE="/var/run/adsb-pipeline.lock"
LOG_TAG="adsb-pipeline"

# Logging helper
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$1] $2"
    logger -t "$LOG_TAG" -p "user.$1" "$2" 2>/dev/null || true
}

log_info() { log "info" "$1"; }
log_warn() { log "warn" "$1"; }
log_error() { log "err" "$1"; }

# Cleanup on exit
cleanup() {
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

# Prevent concurrent runs
if [ -e "$LOCK_FILE" ]; then
    pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "unknown")
    if [ "$pid" != "unknown" ] && kill -0 "$pid" 2>/dev/null; then
        log_warn "Pipeline already running (PID $pid), exiting"
        exit 0
    fi
    log_warn "Stale lock file found, removing"
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"

log_info "=== Starting ADS-B pipeline ==="

# ------------------------------------------------------------------------------
# Step 1: Organize files into YYYY/MM/DD structure
# ------------------------------------------------------------------------------
log_info "Step 1: Organizing files into date directories"

organized_count=0
shopt -s nullglob
for f in "$LOG_DIR"/adsb_state_*.jsonl.gz; do
    bn="$(basename "$f")"

    # Match: adsb_state_YYYY-MM-DD_HH.jsonl.gz
    if [[ "$bn" =~ ^adsb_state_([0-9]{4})-([0-9]{2})-([0-9]{2})(_[0-9]{2})?\.jsonl\.gz$ ]]; then
        Y="${BASH_REMATCH[1]}"
        M="${BASH_REMATCH[2]}"
        D="${BASH_REMATCH[3]}"

        dest="$LOG_DIR/$Y/$M/$D"
        mkdir -p "$dest"

        if [[ ! -e "$dest/$bn" ]]; then
            mv "$f" "$dest/$bn"
            ((organized_count++)) || true
        fi
    fi
done
shopt -u nullglob

if [ "$organized_count" -gt 0 ]; then
    log_info "Organized $organized_count file(s) into date directories"
else
    log_info "No files to organize"
fi

# ------------------------------------------------------------------------------
# Step 2: Sync to Dropbox (before pruning, so files are backed up)
# ------------------------------------------------------------------------------
log_info "Step 2: Syncing to Dropbox"

sync_start=$(date +%s)
if rclone copy "$LOG_DIR" "$DROPBOX_REMOTE" \
    --include "*.jsonl.gz" \
    --include "**/*.jsonl.gz" \
    --exclude "*" \
    --transfers=4 \
    --checkers=8 \
    --log-level ERROR 2>&1; then
    sync_end=$(date +%s)
    sync_duration=$((sync_end - sync_start))
    log_info "Dropbox sync completed in ${sync_duration}s"
else
    log_error "Dropbox sync failed! Skipping prune step for safety"
    exit 1
fi

# ------------------------------------------------------------------------------
# Step 3: Verify and Prune old files (only if verified in Dropbox)
# ------------------------------------------------------------------------------
log_info "Step 3: Pruning files older than $KEEP_DAYS days (with Dropbox verification)"

prune_count=0
prune_failed=0
prune_skipped=0

# Find files older than KEEP_DAYS
while IFS= read -r -d '' local_file; do
    # Get relative path from LOG_DIR
    rel_path="${local_file#$LOG_DIR/}"
    remote_path="$DROPBOX_REMOTE/$rel_path"

    # Check if file exists in Dropbox
    if rclone lsf "$remote_path" --max-depth 1 >/dev/null 2>&1; then
        # File exists in Dropbox, safe to delete locally
        if rm "$local_file" 2>/dev/null; then
            ((prune_count++)) || true
        else
            log_warn "Failed to delete: $local_file"
            ((prune_failed++)) || true
        fi
    else
        # File NOT in Dropbox, skip deletion
        log_warn "Skipping prune (not in Dropbox): $rel_path"
        ((prune_skipped++)) || true
    fi
done < <(find "$LOG_DIR" -name "adsb_state_*.jsonl.gz" -type f -mtime +$KEEP_DAYS -print0 2>/dev/null)

if [ "$prune_count" -gt 0 ]; then
    log_info "Pruned $prune_count file(s)"
fi
if [ "$prune_skipped" -gt 0 ]; then
    log_warn "Skipped $prune_skipped file(s) not found in Dropbox"
fi
if [ "$prune_failed" -gt 0 ]; then
    log_error "Failed to prune $prune_failed file(s)"
fi

# ------------------------------------------------------------------------------
# Step 4: Clean up empty directories
# ------------------------------------------------------------------------------
log_info "Step 4: Cleaning up empty directories"

# Remove empty day/month/year directories
find "$LOG_DIR" -mindepth 1 -type d -empty -delete 2>/dev/null || true

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
total_files=$(find "$LOG_DIR" -name "*.jsonl.gz" -type f 2>/dev/null | wc -l)
total_size=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)

log_info "=== Pipeline complete ==="
log_info "Total files on disk: $total_files ($total_size)"

exit 0
