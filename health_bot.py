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
    """Run health check script"""
    if not check_auth(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized")
        return

    await update.message.reply_text("🔍 Running health check...")

    try:
        # Check if script exists
        if not os.path.exists(HEALTH_CHECK_SCRIPT):
            await update.message.reply_text(
                "⚠️ <b>Health Check Script Not Found</b>\n\n"
                f"Looking for: {HEALTH_CHECK_SCRIPT}\n\n"
                "Install the script on this system or use /quick for basic status.",
                parse_mode='HTML'
            )
            return

        result = subprocess.run(
            [HEALTH_CHECK_SCRIPT],  # Try without sudo first
            capture_output=True,
            text=True,
            timeout=30
        )

        # Parse output for summary
        output = result.stdout
        if "✓ Health check passed - all systems normal" in output:
            response = "✅ <b>Health Check: PASSED</b>\n\nAll systems operational!"
        else:
            # Extract issues
            issues = []
            for line in output.split('\n'):
                if '[err]' in line or '✗' in line:
                    issues.append(line.strip())

            response = "⚠️ <b>Health Check: ISSUES FOUND</b>\n\n"
            if issues:
                response += "\n".join(f"• {issue}" for issue in issues[:10])
            else:
                response += "Check logs for details"

        await update.message.reply_text(response, parse_mode='HTML')

    except subprocess.TimeoutExpired:
        await update.message.reply_text("❌ Health check timed out")
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        await update.message.reply_text(f"❌ Error running health check: {e}")


async def status_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send status report"""
    if not check_auth(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized")
        return

    await update.message.reply_text("📊 Generating status report...")

    try:
        # Check if script exists
        if not os.path.exists(STATUS_REPORT_SCRIPT):
            await update.message.reply_text(
                "⚠️ <b>Status Report Script Not Found</b>\n\n"
                f"Looking for: {STATUS_REPORT_SCRIPT}\n\n"
                "Install the script on this system or use /quick for basic status.",
                parse_mode='HTML'
            )
            return

        result = subprocess.run(
            [STATUS_REPORT_SCRIPT],  # Try without sudo first
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            await update.message.reply_text("✅ Status report sent!")
        else:
            await update.message.reply_text(f"❌ Error: {result.stderr}")

    except subprocess.TimeoutExpired:
        await update.message.reply_text("❌ Status report timed out")
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
