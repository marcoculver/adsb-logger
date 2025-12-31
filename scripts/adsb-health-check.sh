#!/usr/bin/env bash
#
# ADS-B Logger Health Check
# Checks logger status and sends email alerts if issues detected
#
set -euo pipefail

# Configuration
LOG_DIR="/opt/adsb-logs"
SERVICE_NAME="adsb-logger"
ALERT_EMAIL="marcoculver@gmail.com"
MAX_LOG_AGE_MINUTES=5
LOG_TAG="adsb-health"

# State file to avoid repeated alerts
STATE_FILE="/var/run/adsb-health-state"

# Logging helper
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$1] $2"
    logger -t "$LOG_TAG" -p "user.$1" "$2" 2>/dev/null || true
}

log_info() { log "info" "$1"; }
log_warn() { log "warn" "$1"; }
log_error() { log "err" "$1"; }

# Send email alert
send_alert() {
    local subject="$1"
    local body="$2"

    # Check if mail is available
    if command -v mail >/dev/null 2>&1; then
        echo "$body" | mail -s "$subject" "$ALERT_EMAIL"
        log_info "Alert sent: $subject"
    elif command -v msmtp >/dev/null 2>&1; then
        {
            echo "Subject: $subject"
            echo "To: $ALERT_EMAIL"
            echo ""
            echo "$body"
        } | msmtp "$ALERT_EMAIL"
        log_info "Alert sent via msmtp: $subject"
    else
        log_error "No mail command available! Alert: $subject - $body"
    fi
}

# Check if we already alerted for this issue (avoid spam)
already_alerted() {
    local issue_key="$1"
    if [ -f "$STATE_FILE" ]; then
        grep -q "^$issue_key$" "$STATE_FILE" 2>/dev/null && return 0
    fi
    return 1
}

mark_alerted() {
    local issue_key="$1"
    echo "$issue_key" >> "$STATE_FILE"
}

clear_alert() {
    local issue_key="$1"
    if [ -f "$STATE_FILE" ]; then
        sed -i "/^$issue_key$/d" "$STATE_FILE" 2>/dev/null || true
    fi
}

# Initialize
issues_found=0
hostname=$(hostname)

log_info "Running health check..."

# ------------------------------------------------------------------------------
# Check 1: Is the service running?
# ------------------------------------------------------------------------------
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log_info "Service $SERVICE_NAME is running"
    clear_alert "service_down"
else
    log_error "Service $SERVICE_NAME is NOT running!"
    if ! already_alerted "service_down"; then
        send_alert "[$hostname] ADS-B Logger DOWN" \
            "The $SERVICE_NAME service is not running on $hostname.

Status:
$(systemctl status $SERVICE_NAME 2>&1 | head -20)

Recent logs:
$(journalctl -u $SERVICE_NAME -n 20 --no-pager 2>&1)

To restart:
  sudo systemctl restart $SERVICE_NAME

Time: $(date)"
        mark_alerted "service_down"
    fi
    ((issues_found++)) || true
fi

# ------------------------------------------------------------------------------
# Check 2: Is the current log file being updated?
# ------------------------------------------------------------------------------
current_hour=$(date -u '+%Y-%m-%d_%H')
current_log="$LOG_DIR/adsb_state_${current_hour}.jsonl"

if [ -f "$current_log" ]; then
    # Get file age in minutes
    file_age=$(( ($(date +%s) - $(stat -c %Y "$current_log")) / 60 ))

    if [ "$file_age" -gt "$MAX_LOG_AGE_MINUTES" ]; then
        log_error "Log file hasn't been updated in $file_age minutes!"
        if ! already_alerted "log_stale"; then
            send_alert "[$hostname] ADS-B Logger Not Writing" \
                "The current log file hasn't been updated in $file_age minutes.

File: $current_log
Last modified: $(stat -c '%y' "$current_log")

Service status:
$(systemctl status $SERVICE_NAME 2>&1 | head -10)

This could mean:
- The ultrafeeder/tar1090 is not responding
- The logger is stuck
- There's a disk issue

Time: $(date)"
            mark_alerted "log_stale"
        fi
        ((issues_found++)) || true
    else
        log_info "Log file is current (age: ${file_age}m)"
        clear_alert "log_stale"
    fi
else
    log_warn "Current log file not found: $current_log"
    # This might be normal at the start of an hour, wait a bit
fi

# ------------------------------------------------------------------------------
# Check 3: Check for repeated fetch errors in recent logs
# ------------------------------------------------------------------------------
error_count=$(journalctl -u "$SERVICE_NAME" --since "5 minutes ago" --no-pager 2>/dev/null \
    | grep -c "Fetch failed\|Fetch has failed\|Fetch still failing" 2>/dev/null || echo "0")
error_count=$(echo "$error_count" | tr -d '[:space:]')
[ -z "$error_count" ] && error_count=0

if [ "$error_count" -gt 10 ]; then
    log_warn "High number of fetch errors: $error_count in last 5 minutes"
    if ! already_alerted "fetch_errors"; then
        send_alert "[$hostname] ADS-B Logger Fetch Errors" \
            "The logger has experienced $error_count fetch errors in the last 5 minutes.

This usually means the ultrafeeder/tar1090 container is:
- Not running
- Overloaded
- Network issues

Recent log entries:
$(journalctl -u $SERVICE_NAME -n 30 --no-pager 2>&1 | tail -20)

Check docker containers:
  docker ps

Time: $(date)"
        mark_alerted "fetch_errors"
    fi
    ((issues_found++)) || true
else
    clear_alert "fetch_errors"
fi

# ------------------------------------------------------------------------------
# Check 4: Disk space
# ------------------------------------------------------------------------------
disk_usage=$(df "$LOG_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$disk_usage" -gt 90 ]; then
    log_error "Disk usage is at ${disk_usage}%!"
    if ! already_alerted "disk_full"; then
        send_alert "[$hostname] ADS-B Logger Disk Space Low" \
            "Disk usage for $LOG_DIR is at ${disk_usage}%.

Disk status:
$(df -h "$LOG_DIR")

Largest log directories:
$(du -sh "$LOG_DIR"/*/ 2>/dev/null | sort -rh | head -5)

Consider:
- Running the prune manually
- Reducing keep-days
- Adding more storage

Time: $(date)"
        mark_alerted "disk_full"
    fi
    ((issues_found++)) || true
else
    log_info "Disk usage: ${disk_usage}%"
    clear_alert "disk_full"
fi

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
if [ "$issues_found" -eq 0 ]; then
    log_info "Health check passed - all systems normal"
    # Clear state file if everything is OK
    [ -f "$STATE_FILE" ] && rm -f "$STATE_FILE"
else
    log_warn "Health check found $issues_found issue(s)"
fi

exit 0
