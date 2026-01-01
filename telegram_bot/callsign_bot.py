#!/usr/bin/env python3
"""
Telegram bot for Emirates/Flydubai callsign tracking.

This bot focuses on callsign database queries and schedule analysis.
For flight extraction, use the ADSB bot instead.

Usage:
    Set environment variables:
        TELEGRAM_BOT_TOKEN=your_bot_token
        TELEGRAM_ALLOWED_USERS=123456789,987654321

    Run:
        python -m telegram_bot.callsign_bot
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

try:
    from telegram import Update, Bot
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
    )
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from callsign_logger import CallsignDatabase, FlightRadar24API

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


class CallsignBot:
    """Telegram bot for callsign tracking (Emirates/Flydubai only)."""

    def __init__(
        self,
        token: Optional[str] = None,
        allowed_users: Optional[List[int]] = None,
    ):
        if not HAS_TELEGRAM:
            raise ImportError("python-telegram-bot is required. Install with: pip install python-telegram-bot")

        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

        # Parse allowed users from env if not provided
        if allowed_users is None:
            users_str = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
            if users_str:
                self.allowed_users = [
                    int(uid.strip())
                    for uid in users_str.split(",")
                    if uid.strip().isdigit()
                ]
            else:
                self.allowed_users = []
        else:
            self.allowed_users = allowed_users

        self.app: Optional[Application] = None

        # Callsign logger components
        self.callsign_db = CallsignDatabase()
        self.fr24_api = FlightRadar24API()

    def is_authorized(self, user_id: int) -> bool:
        """Check if a user is authorized to use the bot."""
        if not self.allowed_users:
            return True  # No whitelist = allow all (not recommended)
        return user_id in self.allowed_users

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        log.info(f"Start command from user {user.id} ({user.username})")

        if not self.is_authorized(user.id):
            await update.message.reply_text(
                f"Unauthorized. Your user ID is: {user.id}\n"
                "Add this ID to TELEGRAM_ALLOWED_USERS to enable access."
            )
            return

        await update.message.reply_text(
            "Emirates/Flydubai Callsign Tracker Bot\n\n"
            "Commands:\n"
            "/callsigns [airline] - List tracked callsigns\n"
            "/schedule <callsign> - Show schedule pattern\n"
            "/lookup <callsign> - Look up via FR24 API\n"
            "/csexport - Export callsigns to CSV\n"
            "/stats - Database statistics\n"
            "/help - Show help\n\n"
            "Example: /schedule UAE123"
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        await update.message.reply_text(
            "Emirates/Flydubai Callsign Tracker\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📡 /callsigns [airline]\n"
            "   List tracked Emirates/Flydubai callsigns\n"
            "   Example: /callsigns Emirates\n\n"
            "📅 /schedule <callsign>\n"
            "   Show schedule pattern for a callsign\n"
            "   Example: /schedule UAE123\n\n"
            "🔍 /lookup <callsign>\n"
            "   Look up via FlightRadar24 API\n\n"
            "📤 /csexport\n"
            "   Export callsigns to CSV\n\n"
            "📊 /stats - Database statistics\n\n"
            "This bot tracks Emirates and Flydubai flights only."
        )

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized")
            return

        try:
            cs_stats = self.callsign_db.get_stats()

            status = "📊 Callsign Database Statistics\n"
            status += "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            status += f"Total callsigns: {cs_stats['total_callsigns']}\n"
            status += f"Total sightings: {cs_stats['total_sightings']:,}\n\n"

            status += "By airline:\n"
            for airline, count in cs_stats['by_airline'].items():
                status += f"  {airline}: {count}\n"

            await update.message.reply_text(status)
        except Exception as e:
            log.exception(f"Stats error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_callsigns(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /callsigns command - list tracked callsigns."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized")
            return

        args = context.args
        airline = args[0] if args else None

        try:
            callsigns = self.callsign_db.get_all_callsigns(airline)

            if not callsigns:
                await update.message.reply_text(
                    "No callsigns found in database.\n"
                    "Make sure the callsign monitor is running to collect data."
                )
                return

            response = "📡 Tracked Callsigns\n"
            response += "━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            # Show first 30
            for cs in callsigns[:30]:
                route = cs.get('route') or '-'
                flight = cs.get('flight_number') or '-'
                count = cs['sighting_count']
                response += f"{cs['callsign']:<8} {flight:<6} {route:<10} ({count}x)\n"

            if len(callsigns) > 30:
                response += f"\n... and {len(callsigns) - 30} more"

            response += f"\n\nTotal: {len(callsigns)} callsigns"

            await update.message.reply_text(response)

        except Exception as e:
            log.exception(f"Callsigns error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /schedule command - show schedule pattern for a callsign."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized")
            return

        args = context.args
        if not args:
            await update.message.reply_text("Usage: /schedule <callsign>\nExample: /schedule UAE123")
            return

        callsign = args[0].upper()

        try:
            cs_data = self.callsign_db.get_callsign(callsign)
            if not cs_data:
                await update.message.reply_text(f"Callsign {callsign} not found in database.")
                return

            schedule = self.callsign_db.get_schedule(callsign)

            response = f"📅 Schedule for {callsign}\n"
            response += "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            response += f"Flight: {cs_data.get('flight_number') or 'Unknown'}\n"
            response += f"Route: {cs_data.get('route') or 'Unknown'}\n"
            response += f"Total sightings: {schedule['total_sightings']}\n\n"

            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            response += "By day:\n"
            for i, day in enumerate(days):
                count = schedule['by_day_of_week'].get(i, 0)
                bar = "█" * min(count, 10)
                response += f"  {day}: {bar} ({count})\n"

            response += "\nBy hour (UTC):\n"
            for hour in range(24):
                count = schedule['by_hour'].get(hour, 0)
                if count > 0:
                    bar = "█" * min(count, 8)
                    response += f"  {hour:02d}:00 {bar} ({count})\n"

            await update.message.reply_text(response)

        except Exception as e:
            log.exception(f"Schedule error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_lookup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /lookup command - look up callsign via FR24 API."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized")
            return

        args = context.args
        if not args:
            await update.message.reply_text("Usage: /lookup <callsign>\nExample: /lookup UAE123")
            return

        callsign = args[0].upper()

        msg = await update.message.reply_text(f"🔍 Looking up {callsign}...")

        try:
            route_data = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.fr24_api.lookup_route(callsign)
            )

            if route_data:
                response = f"🔍 {callsign}\n"
                response += "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                response += f"Flight: {route_data.get('flight_number') or 'Unknown'}\n"
                response += f"Route: {route_data.get('route') or 'Unknown'}\n"
                response += f"Origin: {route_data.get('origin') or 'Unknown'}\n"
                response += f"Destination: {route_data.get('destination') or 'Unknown'}\n"
                response += f"Aircraft: {route_data.get('aircraft_type') or 'Unknown'}\n"
                response += f"Registration: {route_data.get('registration') or 'Unknown'}\n"
                await msg.edit_text(response)
            else:
                await msg.edit_text(f"No data found for {callsign}\n(Flight may not be currently active)")

        except Exception as e:
            log.exception(f"Lookup error: {e}")
            await msg.edit_text(f"❌ Error: {e}")

    async def cmd_csexport(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /csexport command - export callsigns to CSV."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized")
            return

        try:
            import tempfile

            # Export to temp file
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
                temp_path = Path(f.name)

            self.callsign_db.export_csv(temp_path)

            # Send file
            await update.message.reply_document(
                document=open(temp_path, "rb"),
                filename="callsigns_export.csv",
                caption="Callsign database export"
            )

            # Cleanup
            temp_path.unlink()

        except Exception as e:
            log.exception(f"Export error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    def run(self):
        """Run the bot (blocking)."""
        self.app = Application.builder().token(self.token).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("stats", self.cmd_stats))
        self.app.add_handler(CommandHandler("callsigns", self.cmd_callsigns))
        self.app.add_handler(CommandHandler("schedule", self.cmd_schedule))
        self.app.add_handler(CommandHandler("lookup", self.cmd_lookup))
        self.app.add_handler(CommandHandler("csexport", self.cmd_csexport))

        log.info("Starting Callsign Tracker Bot...")
        log.info(f"Allowed users: {self.allowed_users or 'ALL (not recommended)'}")

        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point."""
    if not HAS_TELEGRAM:
        print("Error: python-telegram-bot not installed")
        print("Install with: pip install python-telegram-bot")
        sys.exit(1)

    bot = CallsignBot()
    bot.run()


if __name__ == "__main__":
    main()
