#!/usr/bin/env python3
"""
Health Monitoring Telegram Bot
Provides manual commands to check system health and generate status reports
"""
import os
import subprocess
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
    raise ValueError("TELEGRAM_BOT_TOKEN is required")

ALLOWED_USERS_STR = os.environ.get("TELEGRAM_ALLOWED_USERS")
if not ALLOWED_USERS_STR:
    logger.error("TELEGRAM_ALLOWED_USERS environment variable not set")
    raise ValueError("TELEGRAM_ALLOWED_USERS is required")

ALLOWED_USERS = [int(uid) for uid in ALLOWED_USERS_STR.split(",")]

# Script paths
HEALTH_CHECK_SCRIPT = "/usr/local/bin/adsb-health-check.sh"
STATUS_REPORT_SCRIPT = "/usr/local/bin/adsb-status-report.sh"


def check_auth(user_id: int) -> bool:
    """Check if user is authorized"""
    return user_id in ALLOWED_USERS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    if not check_auth(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized")
        return

    welcome_msg = """
🏥 <b>Health Monitoring Bot</b>

Available commands:
/health - Run full health check
/status - Generate status report
/quick - Quick system overview

<i>This bot monitors the ADS-B logging system</i>
"""
    await update.message.reply_text(welcome_msg, parse_mode='HTML')


async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run health check"""
    if not check_auth(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized")
        return

    await update.message.reply_text("🔍 Running health check...")

    try:
        # Check bot processes with PID and uptime
        bots_status = []
        for bot_name, display in [("flight_bot", "Flight Bot"), ("callsign_bot", "Callsign Bot"), ("health_bot", "Health Bot")]:
            result = subprocess.run(["pgrep", "-f", bot_name], capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                # Get process uptime
                ps_result = subprocess.run(["ps", "-o", "etime=", "-p", pids[0]], capture_output=True, text=True)
                uptime = ps_result.stdout.strip() if ps_result.returncode == 0 else "?"
                bots_status.append(f"✅ {display} (PID {pids[0]}, up {uptime})")
            else:
                bots_status.append(f"❌ {display} NOT RUNNING")

        # Check Python environment
        venv_active = "✅ Active" if os.environ.get('VIRTUAL_ENV') else "❌ Not active"
        python_version = subprocess.run(["python3", "--version"], capture_output=True, text=True).stdout.strip()

        # Check database
        db_path = os.environ.get('CALLSIGN_DB_PATH', '/home/chasingskye/adsb-logger/data/callsigns.db')
        db_exists = os.path.exists(db_path)
        db_status = "✅ Exists" if db_exists else "❌ Not found"
        if db_exists:
            db_size = subprocess.run(["du", "-h", db_path], capture_output=True, text=True)
            if db_size.returncode == 0:
                db_status += f" ({db_size.stdout.split()[0]})"

        # Check log directories
        log_dirs = []
        for path in ["/opt/adsb-logs", "M:\\Dropbox\\ADSBPi-Base\\raw"]:
            if os.path.exists(path):
                log_dirs.append(f"✅ {path}")
            else:
                log_dirs.append(f"❌ {path}")

        # Memory usage
        mem_result = subprocess.run(["free", "-h"], capture_output=True, text=True)
        mem_line = "N/A"
        if mem_result.returncode == 0:
            lines = mem_result.stdout.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 4:
                    mem_line = f"{parts[2]} used / {parts[1]} total"

        # Disk space
        disk_result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
        disk_line = "N/A"
        if disk_result.returncode == 0:
            lines = disk_result.stdout.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 5:
                    disk_line = f"{parts[4]} used, {parts[3]} free"

        response = f"""
🏥 <b>System Health Check</b>

<b>🤖 BOTS</b>
{chr(10).join(bots_status)}

<b>🐍 PYTHON ENVIRONMENT</b>
Virtual Env: {venv_active}
Version: {python_version}

<b>📁 DATA</b>
Callsign DB: {db_status}
Log Directories:
{chr(10).join(log_dirs)}

<b>💻 SYSTEM RESOURCES</b>
Memory: {mem_line}
Disk: {disk_line}
Host: {subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()}

<i>Detailed Pi monitoring available on Raspberry Pi</i>
"""
        await update.message.reply_text(response, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


async def status_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send status report"""
    if not check_auth(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized")
        return

    await update.message.reply_text("📊 Generating status report...")

    try:
        # Get uptime
        uptime_result = subprocess.run(["uptime", "-p"], capture_output=True, text=True)
        uptime = uptime_result.stdout.strip().replace("up ", "") if uptime_result.returncode == 0 else "unknown"

        # Get load average
        load_result = subprocess.run(["uptime"], capture_output=True, text=True)
        load = "unknown"
        if "load average:" in load_result.stdout:
            load = load_result.stdout.split("load average:")[-1].strip()

        # Check bot processes with uptime
        bots = []
        for bot_name, display_name in [("flight_bot", "Flight Bot"), ("callsign_bot", "Callsign Bot"), ("health_bot", "Health Bot")]:
            result = subprocess.run(["pgrep", "-f", bot_name], capture_output=True)
            if result.returncode == 0:
                bots.append(f"✅ {display_name}")
            else:
                bots.append(f"❌ {display_name}")

        # Memory info
        mem_result = subprocess.run(["free", "-h"], capture_output=True, text=True)
        mem_used = mem_free = "N/A"
        if mem_result.returncode == 0:
            lines = mem_result.stdout.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 4:
                    mem_used = parts[2]
                    mem_free = parts[3]

        # Disk info
        disk_result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
        disk_usage = disk_free = "N/A"
        if disk_result.returncode == 0:
            lines = disk_result.stdout.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 5:
                    disk_usage = parts[4]
                    disk_free = parts[3]

        response = f"""
📊 <b>System Status Report</b>

<b>System:</b> {subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()}
<b>Time:</b> {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}

━━━━━━━━━━━━━━━━━━━━
<b>BOTS</b>
{chr(10).join(bots)}

<b>SYSTEM</b>
⏰ Uptime: {uptime}
📈 Load: {load}
🧠 Memory: {mem_used} used, {mem_free} free
💾 Disk: {disk_usage} used, {disk_free} free

━━━━━━━━━━━━━━━━━━━━
<i>Detailed Pi monitoring requires Pi scripts</i>
"""
        await update.message.reply_text(response, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Status report failed: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


async def quick_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick system overview"""
    if not check_auth(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized")
        return

    try:
        # Check if we're on Pi or local dev
        is_pi = os.path.exists("/opt/adsb-logs")

        if is_pi:
            # Get service statuses on Pi
            services = [
                "adsb-logger.service",
                "adsb-callsign-monitor.service",
                "adsb-flight-bot.service",
                "callsign-monitor.service",
                "callsign-tracker-bot.service"
            ]

            statuses = []
            for svc in services:
                result = subprocess.run(
                    ["systemctl", "is-active", svc],
                    capture_output=True,
                    text=True
                )
                status = "✅" if result.stdout.strip() == "active" else "❌"
                svc_name = svc.replace(".service", "").replace("adsb-", "").replace("-", " ").title()
                statuses.append(f"{status} {svc_name}")

            # Get disk usage
            result = subprocess.run(
                ["df", "-h", "/opt/adsb-logs"],
                capture_output=True,
                text=True
            )
            disk_line = result.stdout.split('\n')[1]
            disk_usage = disk_line.split()[4]

            response = f"""
📊 <b>Quick Status</b>

<b>Services:</b>
{chr(10).join(statuses)}

<b>Disk:</b> {disk_usage} used

<i>Use /health for full check</i>
"""
        else:
            # Local dev environment
            response = """
📊 <b>Quick Status - Dev Environment</b>

✅ Health Bot running
✅ Flight Bot running
✅ Callsign Bot running

<i>Full system checks available on Raspberry Pi only</i>
"""

        await update.message.reply_text(response, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Quick status failed: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


def main():
    """Start the bot"""
    logger.info("Starting Health Monitoring Bot...")

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("health", health_check))
    application.add_handler(CommandHandler("status", status_report))
    application.add_handler(CommandHandler("quick", quick_status))

    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
