#!/usr/bin/env bash
#
# ADS-B 12-Hourly Status Report
# Sends a comprehensive health status report via Telegram
#
set -euo pipefail

# Configuration
LOG_DIR="/opt/adsb-logs"
LOG_TAG="adsb-status"

# Telegram Configuration
# Set these environment variables before running
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables must be set"
    exit 1
fi

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

# Send Telegram message
send_telegram() {
    local message="$1"
    local parse_mode="${2:-HTML}"

    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${message}" \
        -d "parse_mode=${parse_mode}" \
        -d "disable_web_page_preview=true" \
        >/dev/null 2>&1 || log "error" "Failed to send Telegram message"
}

# Initialize
hostname=$(hostname)
all_ok=true
services_status=""
timers_status=""
containers_status=""

log_info "Generating 12-hourly status report..."

# ==============================================================================
# Check Services
# ==============================================================================
services_ok=0
services_down=0
for service in "${SERVICES[@]}"; do
    service_name=$(basename "$service" .service)
    if systemctl is-active --quiet "$service"; then
        services_status+="✅ <code>$service_name</code>\n"
        ((services_ok++)) || true
    else
        services_status+="❌ <code>$service_name</code>\n"
        ((services_down++)) || true
        all_ok=false
    fi
done

# ==============================================================================
# Check Timers
# ==============================================================================
timers_ok=0
timers_down=0
for timer in "${TIMERS[@]}"; do
    timer_name=$(basename "$timer" .timer)
    if systemctl is-active --quiet "$timer"; then
        # Get next trigger time
        next_trigger=$(systemctl status "$timer" 2>/dev/null | grep -oP 'Trigger: \K.*' | head -1 || echo "unknown")
        if [ "$next_trigger" = "unknown" ]; then
            timers_status+="✅ <code>$timer_name</code>\n"
        else
            timers_status+="✅ <code>$timer_name</code> (next: $next_trigger)\n"
        fi
        ((timers_ok++)) || true
    else
        timers_status+="⏱️ <code>$timer_name</code>\n"
        ((timers_down++)) || true
        all_ok=false
    fi
done

# ==============================================================================
# Check Docker Containers
# ==============================================================================
containers_ok=0
containers_down=0
if command -v docker >/dev/null 2>&1; then
    for container in "${DOCKER_CONTAINERS[@]}"; do
        if docker ps --filter "name=^${container}$" --filter "status=running" --format '{{.Names}}' | grep -q "^${container}$"; then
            # Get uptime
            uptime=$(docker ps --filter "name=^${container}$" --format '{{.Status}}' 2>/dev/null || echo "unknown")
            containers_status+="✅ <code>$container</code> ($uptime)\n"
            ((containers_ok++)) || true
        else
            containers_status+="❌ <code>$container</code>\n"
            ((containers_down++)) || true
            all_ok=false
        fi
    done
else
    containers_status="⚠️ Docker not available\n"
fi

# ==============================================================================
# System Stats
# ==============================================================================
# Disk usage
disk_usage=$(df "$LOG_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
disk_free=$(df -h "$LOG_DIR" | tail -1 | awk '{print $4}')

# Memory usage
mem_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100}')
mem_free=$(free -h | grep Mem | awk '{print $4}')

# Uptime
system_uptime=$(uptime -p | sed 's/up //')

# Load average
load_avg=$(uptime | grep -oP 'load average: \K.*')

# Log file count (last 24 hours)
recent_logs=$(find "$LOG_DIR" -name "*.jsonl*" -mtime -1 -type f 2>/dev/null | wc -l)

# Database size
db_size="unknown"
if [ -f "$LOG_DIR/callsigns.db" ]; then
    db_size=$(du -h "$LOG_DIR/callsigns.db" | cut -f1)
fi

# ==============================================================================
# Build Status Message
# ==============================================================================
if [ "$all_ok" = true ]; then
    status_icon="✅"
    status_text="<b>ALL SYSTEMS OPERATIONAL</b>"
else
    status_icon="⚠️"
    status_text="<b>ISSUES DETECTED</b>"
fi

message="$status_icon <b>ADS-B Status Report</b>

$status_text
<b>Host:</b> $hostname
<b>Time:</b> $(date '+%Y-%m-%d %H:%M:%S %Z')

━━━━━━━━━━━━━━━━━━━━
<b>📊 SERVICES</b> ($services_ok/$((services_ok + services_down)) running)
$services_status
<b>⏱️ TIMERS</b> ($timers_ok/$((timers_ok + timers_down)) active)
$timers_status
<b>🐳 CONTAINERS</b> ($containers_ok/$((containers_ok + containers_down)) running)
$containers_status
━━━━━━━━━━━━━━━━━━━━
<b>💻 SYSTEM STATS</b>
💾 Disk: ${disk_usage}% used (${disk_free} free)
🧠 Memory: ${mem_usage}% used (${mem_free} free)
⏰ Uptime: $system_uptime
📈 Load: $load_avg
📝 Recent logs (24h): $recent_logs files
🗄️ Database: $db_size

━━━━━━━━━━━━━━━━━━━━
Next report in 12 hours"

# Send the report
send_telegram "$message"

log_info "Status report sent successfully"

exit 0
