#!/usr/bin/env bash
#
# ADS-B Comprehensive Health Check
# Monitors all services, docker containers, timers, and sends alerts
#
set -euo pipefail

# Configuration
LOG_DIR="/opt/adsb-logs"
ALERT_EMAIL="marcoculver@gmail.com"
MAX_LOG_AGE_MINUTES=5
LOG_TAG="adsb-health"

# Telegram Configuration
TELEGRAM_BOT_TOKEN="8279120117:AAGy7o3LdvTgB8jUTtluYbw_kxuBD_AFx9o"
TELEGRAM_CHAT_ID="1269568755"

# State file to avoid repeated alerts
STATE_FILE="/var/run/adsb-health-state"

# Services to monitor
SERVICES=(
    "adsb-logger.service"
    "adsb-callsign-monitor.service"
    "adsb-flight-bot.service"
    "callsign-monitor.service"
    "callsign-tracker-bot.service"
)

# Timers to monitor
TIMERS=(
    "adsb-dropbox-sync.timer"
    "adsb-health-check.timer"
    "adsb-log-organize.timer"
    "adsb-pipeline.timer"
)

# Docker containers to monitor
DOCKER_CONTAINERS=(
    "piaware"
    "skystats"
    "skystats-db"
    "fr24feed"
    "ultrafeeder"
)

# Logging helper
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$1] $2"
    logger -t "$LOG_TAG" -p "user.$1" "$2" 2>/dev/null || true
}

log_info() { log "info" "$1"; }
log_warn() { log "warn" "$1"; }
log_error() { log "err" "$1"; }

# Send Telegram message
send_telegram() {
    local message="$1"
    local parse_mode="${2:-HTML}"

    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${message}" \
        -d "parse_mode=${parse_mode}" \
        -d "disable_web_page_preview=true" \
        >/dev/null 2>&1 || log_error "Failed to send Telegram message"
}

# Send email alert
send_email() {
    local subject="$1"
    local body="$2"

    # Check if mail is available
    if command -v mail >/dev/null 2>&1; then
        echo "$body" | mail -s "$subject" "$ALERT_EMAIL"
        log_info "Email sent: $subject"
    elif command -v msmtp >/dev/null 2>&1; then
        {
            echo "Subject: $subject"
            echo "To: $ALERT_EMAIL"
            echo ""
            echo "$body"
        } | msmtp "$ALERT_EMAIL"
        log_info "Email sent via msmtp: $subject"
    else
        log_warn "No mail command available for email alert"
    fi
}

# Send alert via both email and Telegram
send_alert() {
    local subject="$1"
    local body="$2"
    local telegram_msg="$3"

    # Send email
    send_email "$subject" "$body"

    # Send Telegram
    send_telegram "$telegram_msg"

    log_info "Alert sent: $subject"
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
    mkdir -p "$(dirname "$STATE_FILE")"
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
failed_services=()
failed_timers=()
failed_containers=()

log_info "Running comprehensive health check..."

# ==============================================================================
# Check 1: Systemd Services
# ==============================================================================
log_info "Checking ${#SERVICES[@]} systemd services..."
for service in "${SERVICES[@]}"; do
    service_name=$(basename "$service" .service)
    if systemctl is-active --quiet "$service"; then
        log_info "✓ Service $service is running"
        clear_alert "service_${service_name}_down"
    else
        log_error "✗ Service $service is NOT running!"
        failed_services+=("$service")

        if ! already_alerted "service_${service_name}_down"; then
            service_status=$(systemctl status "$service" 2>&1 | head -20 || echo "Unable to get status")
            recent_logs=$(journalctl -u "$service" -n 10 --no-pager 2>&1 || echo "Unable to get logs")

            send_alert \
                "[$hostname] Service DOWN: $service" \
                "Service $service is not running on $hostname.

Status:
$service_status

Recent logs:
$recent_logs

To restart:
  sudo systemctl restart $service

Time: $(date)" \
                "🔴 <b>Service DOWN</b>

<b>Host:</b> $hostname
<b>Service:</b> $service
<b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')

To fix: <code>sudo systemctl restart $service</code>"

            mark_alerted "service_${service_name}_down"
        fi
        ((issues_found++)) || true
    fi
done

# ==============================================================================
# Check 2: Systemd Timers
# ==============================================================================
log_info "Checking ${#TIMERS[@]} systemd timers..."
for timer in "${TIMERS[@]}"; do
    timer_name=$(basename "$timer" .timer)
    if systemctl is-active --quiet "$timer"; then
        log_info "✓ Timer $timer is active"
        clear_alert "timer_${timer_name}_inactive"
    else
        log_error "✗ Timer $timer is NOT active!"
        failed_timers+=("$timer")

        if ! already_alerted "timer_${timer_name}_inactive"; then
            timer_status=$(systemctl status "$timer" 2>&1 | head -15 || echo "Unable to get status")

            send_alert \
                "[$hostname] Timer INACTIVE: $timer" \
                "Timer $timer is not active on $hostname.

Status:
$timer_status

To restart:
  sudo systemctl start $timer

Time: $(date)" \
                "⏱️ <b>Timer INACTIVE</b>

<b>Host:</b> $hostname
<b>Timer:</b> $timer
<b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')

To fix: <code>sudo systemctl start $timer</code>"

            mark_alerted "timer_${timer_name}_inactive"
        fi
        ((issues_found++)) || true
    fi
done

# ==============================================================================
# Check 3: Docker Containers
# ==============================================================================
log_info "Checking ${#DOCKER_CONTAINERS[@]} docker containers..."
if command -v docker >/dev/null 2>&1; then
    for container in "${DOCKER_CONTAINERS[@]}"; do
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            # Check if container is actually running (not just exists)
            if docker ps --filter "name=^${container}$" --filter "status=running" --format '{{.Names}}' | grep -q "^${container}$"; then
                log_info "✓ Container $container is running"
                clear_alert "docker_${container}_down"
            else
                log_error "✗ Container $container exists but is NOT running!"
                failed_containers+=("$container")

                if ! already_alerted "docker_${container}_down"; then
                    container_status=$(docker ps -a --filter "name=^${container}$" --format "table {{.Status}}\t{{.State}}" 2>&1 || echo "Unable to get status")
                    container_logs=$(docker logs "$container" --tail 20 2>&1 || echo "Unable to get logs")

                    send_alert \
                        "[$hostname] Docker Container DOWN: $container" \
                        "Docker container $container is not running on $hostname.

Status:
$container_status

Recent logs:
$container_logs

To restart:
  docker restart $container

Time: $(date)" \
                        "🐳 <b>Container DOWN</b>

<b>Host:</b> $hostname
<b>Container:</b> $container
<b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')

To fix: <code>docker restart $container</code>"

                    mark_alerted "docker_${container}_down"
                fi
                ((issues_found++)) || true
            fi
        else
            log_error "✗ Container $container not found!"
            failed_containers+=("$container")

            if ! already_alerted "docker_${container}_missing"; then
                send_alert \
                    "[$hostname] Docker Container MISSING: $container" \
                    "Docker container $container is not found on $hostname.

Available containers:
$(docker ps -a --format '{{.Names}}')

This container may need to be recreated.

Time: $(date)" \
                    "🐳 <b>Container MISSING</b>

<b>Host:</b> $hostname
<b>Container:</b> $container
<b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')

Container not found in docker ps"

                mark_alerted "docker_${container}_missing"
            fi
            ((issues_found++)) || true
        fi
    done
else
    log_warn "Docker command not available, skipping container checks"
fi

# ==============================================================================
# Check 4: Log File Freshness
# ==============================================================================
log_info "Checking log file freshness..."
current_hour=$(date -u '+%Y-%m-%d_%H')
current_log="$LOG_DIR/adsb_state_${current_hour}.jsonl"

if [ -f "$current_log" ]; then
    file_age=$(( ($(date +%s) - $(stat -c %Y "$current_log")) / 60 ))

    if [ "$file_age" -gt "$MAX_LOG_AGE_MINUTES" ]; then
        log_error "✗ Log file hasn't been updated in $file_age minutes!"

        if ! already_alerted "log_stale"; then
            service_status=$(systemctl status adsb-logger.service 2>&1 | head -10 || echo "Unable to get status")

            send_alert \
                "[$hostname] ADS-B Logger Not Writing" \
                "The current log file hasn't been updated in $file_age minutes.

File: $current_log
Last modified: $(stat -c '%y' "$current_log")

Service status:
$service_status

This could mean:
- The ultrafeeder/tar1090 is not responding
- The logger is stuck
- There's a disk issue

Time: $(date)" \
                "📝 <b>Log File Stale</b>

<b>Host:</b> $hostname
<b>File:</b> $current_log
<b>Age:</b> $file_age minutes
<b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')

Log hasn't been updated recently!"

            mark_alerted "log_stale"
        fi
        ((issues_found++)) || true
    else
        log_info "✓ Log file is current (age: ${file_age}m)"
        clear_alert "log_stale"
    fi
else
    log_warn "Current log file not found: $current_log (might be normal at start of hour)"
fi

# ==============================================================================
# Check 5: Fetch Errors
# ==============================================================================
log_info "Checking for fetch errors..."
error_count=$(journalctl -u "adsb-logger.service" --since "5 minutes ago" --no-pager 2>/dev/null \
    | grep -c "Fetch failed\|Fetch has failed\|Fetch still failing" 2>/dev/null || echo "0")
error_count=$(echo "$error_count" | tr -d '[:space:]')
[ -z "$error_count" ] && error_count=0

if [ "$error_count" -gt 10 ]; then
    log_warn "✗ High number of fetch errors: $error_count in last 5 minutes"

    if ! already_alerted "fetch_errors"; then
        recent_logs=$(journalctl -u adsb-logger.service -n 20 --no-pager 2>&1 | tail -15 || echo "Unable to get logs")

        send_alert \
            "[$hostname] ADS-B Logger Fetch Errors" \
            "The logger has experienced $error_count fetch errors in the last 5 minutes.

This usually means the ultrafeeder/tar1090 container is:
- Not running
- Overloaded
- Network issues

Recent log entries:
$recent_logs

Check docker containers:
  docker ps

Time: $(date)" \
            "⚠️ <b>Fetch Errors</b>

<b>Host:</b> $hostname
<b>Errors:</b> $error_count in 5 min
<b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')

Check ultrafeeder container!"

        mark_alerted "fetch_errors"
    fi
    ((issues_found++)) || true
else
    log_info "✓ No excessive fetch errors"
    clear_alert "fetch_errors"
fi

# ==============================================================================
# Check 6: Disk Space
# ==============================================================================
log_info "Checking disk space..."
disk_usage=$(df "$LOG_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$disk_usage" -gt 90 ]; then
    log_error "✗ Disk usage is at ${disk_usage}%!"

    if ! already_alerted "disk_full"; then
        disk_status=$(df -h "$LOG_DIR")
        largest_dirs=$(du -sh "$LOG_DIR"/*/ 2>/dev/null | sort -rh | head -5 || echo "Unable to get sizes")

        send_alert \
            "[$hostname] Disk Space Low" \
            "Disk usage for $LOG_DIR is at ${disk_usage}%.

Disk status:
$disk_status

Largest log directories:
$largest_dirs

Consider:
- Running the prune manually
- Reducing keep-days
- Adding more storage

Time: $(date)" \
            "💾 <b>Disk Space Low</b>

<b>Host:</b> $hostname
<b>Usage:</b> ${disk_usage}%
<b>Path:</b> $LOG_DIR
<b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S')

Consider running cleanup!"

        mark_alerted "disk_full"
    fi
    ((issues_found++)) || true
else
    log_info "✓ Disk usage: ${disk_usage}%"
    clear_alert "disk_full"
fi

# ==============================================================================
# Summary
# ==============================================================================
if [ "$issues_found" -eq 0 ]; then
    log_info "✓ Health check passed - all systems normal"
    # Clear state file if everything is OK
    [ -f "$STATE_FILE" ] && rm -f "$STATE_FILE"
else
    log_warn "✗ Health check found $issues_found issue(s)"

    # Build summary message
    summary="Health Check Summary:\n"
    summary+="Issues found: $issues_found\n\n"

    if [ ${#failed_services[@]} -gt 0 ]; then
        summary+="Failed Services (${#failed_services[@]}):\n"
        for svc in "${failed_services[@]}"; do
            summary+="  - $svc\n"
        done
        summary+="\n"
    fi

    if [ ${#failed_timers[@]} -gt 0 ]; then
        summary+="Inactive Timers (${#failed_timers[@]}):\n"
        for tmr in "${failed_timers[@]}"; do
            summary+="  - $tmr\n"
        done
        summary+="\n"
    fi

    if [ ${#failed_containers[@]} -gt 0 ]; then
        summary+="Failed Containers (${#failed_containers[@]}):\n"
        for cnt in "${failed_containers[@]}"; do
            summary+="  - $cnt\n"
        done
    fi

    log_warn "$summary"
fi

exit 0
