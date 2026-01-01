#!/usr/bin/env python3
"""
Telegram bot for ADS-B flight data extraction.

Usage:
    Set environment variables:
        TELEGRAM_BOT_TOKEN=your_bot_token
        TELEGRAM_ALLOWED_USERS=123456789,987654321

    Run:
        python -m telegram_bot.bot
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional

try:
    from telegram import Update, Bot
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flight_extractor import FlightExtractor, Config
from flight_export import CSVExporter, KMLGenerator
from flight_charts import generate_all_charts, generate_dashboard
from callsign_logger import CallsignDatabase, FlightRadar24API

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


class FlightBot:
    """Telegram bot for flight data extraction."""

    def __init__(
        self,
        token: Optional[str] = None,
        allowed_users: Optional[List[int]] = None,
        config: Optional[Config] = None
    ):
        if not HAS_TELEGRAM:
            raise ImportError("python-telegram-bot is required. Install with: pip install python-telegram-bot")

        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

        self.config = config or Config.from_env()
        self.extractor = FlightExtractor(self.config)

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
            "ADS-B Flight Extractor Bot\n\n"
            "Flight Extraction:\n"
            "/extract <callsign> <date> - Extract flight data\n"
            "/list <date> - List flights on a date\n\n"
            "Callsign Tracking:\n"
            "/callsigns - List tracked callsigns\n"
            "/schedule <callsign> - Show schedule pattern\n"
            "/lookup <callsign> - Look up via FR24 API\n"
            "/csexport - Export callsigns to CSV\n\n"
            "/status - Show bot status\n"
            "/help - Show help\n\n"
            "Example: /extract FDB8876 2024-12-31"
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        await update.message.reply_text(
            "ADS-B Flight Extractor Bot\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "FLIGHT EXTRACTION\n"
            "📍 /extract <callsign> <date>\n"
            "   Extract flight data with charts\n"
            "   Example: /extract FDB8876 2024-12-31\n\n"
            "📋 /list <date>\n"
            "   List all flights on a date\n\n"
            "CALLSIGN TRACKING\n"
            "📡 /callsigns [airline]\n"
            "   List tracked Emirates/Flydubai callsigns\n"
            "   Example: /callsigns Emirates\n\n"
            "📅 /schedule <callsign>\n"
            "   Show schedule pattern for a callsign\n"
            "   Example: /schedule FDB4CE\n\n"
            "🔍 /lookup <callsign>\n"
            "   Look up via FlightRadar24 API\n\n"
            "📤 /csexport\n"
            "   Export callsigns to CSV\n\n"
            "📊 /status - Bot status\n\n"
            "Date formats: YYYY-MM-DD or YYYYMMDD"
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized")
            return

        log_dir = self.config.log_dir
        output_dir = self.config.output_dir

        log_exists = log_dir.exists()
        output_exists = output_dir.exists()

        status = (
            "Bot Status\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Log Directory: {log_dir}\n"
            f"  Status: {'✅ Found' if log_exists else '❌ Not found'}\n"
            f"Output Directory: {output_dir}\n"
            f"  Status: {'✅ Found' if output_exists else '❌ Not found'}\n"
        )

        # Count recent extractions
        if output_exists:
            extractions = list(output_dir.glob("*_*"))
            status += f"  Extractions: {len(extractions)}\n"

        # Callsign database stats
        try:
            cs_stats = self.callsign_db.get_stats()
            status += f"\nCallsign Database:\n"
            status += f"  Total callsigns: {cs_stats['total_callsigns']}\n"
            status += f"  Total sightings: {cs_stats['total_sightings']}\n"
            for airline, count in cs_stats['by_airline'].items():
                status += f"  {airline}: {count}\n"
        except Exception:
            status += f"\nCallsign Database: Not initialized\n"

        await update.message.reply_text(status)

    async def cmd_extract(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /extract command."""
        user = update.effective_user
        if not self.is_authorized(user.id):
            await update.message.reply_text("Unauthorized")
            return

        # Parse arguments
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /extract <callsign> <date>\n"
                "Example: /extract FDB8876 2024-12-31"
            )
            return

        callsign = args[0].upper()
        date_str = args[1]

        # Parse date
        try:
            target_date = self._parse_date(date_str)
        except ValueError as e:
            await update.message.reply_text(f"Invalid date: {e}")
            return

        log.info(f"Extract request: {callsign} on {target_date} from user {user.id}")

        # Send processing message
        msg = await update.message.reply_text(
            f"🔍 Processing {callsign} for {target_date}...\n"
            "This may take a moment."
        )

        try:
            # Run extraction in thread pool
            flight_data = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._run_extraction(callsign, target_date)
            )

            if not flight_data or not flight_data.records:
                await msg.edit_text(f"❌ No data found for {callsign} on {target_date}")
                return

            # Format response
            m = flight_data.metadata
            response = (
                f"✅ Flight: {callsign}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            )

            if m.aircraft_type or m.registration:
                response += f"Aircraft: {m.aircraft_type or 'Unknown'} ({m.registration or 'N/A'})\n"

            if m.first_seen and m.last_seen:
                response += f"Time: {m.first_seen.strftime('%H:%M')} - {m.last_seen.strftime('%H:%M')} UTC\n"

            response += f"Duration: {m.duration_minutes:.0f} min\n"

            if m.max_altitude_ft:
                response += f"Max Alt: {m.max_altitude_ft:,.0f} ft\n"
            if m.max_ground_speed_kts:
                response += f"Max Speed: {m.max_ground_speed_kts:.0f} kts\n"

            response += f"Records: {m.records_extracted:,}\n"

            if m.crossover_detected:
                response += f"⚠️ Midnight crossover detected\n"

            response += f"\n📁 Output: {flight_data.output_dir}"

            await msg.edit_text(response)

            # Send altitude chart if available
            altitude_png = flight_data.output_dir / "charts" / "altitude_profile.png"
            if altitude_png.exists():
                await update.message.reply_photo(
                    photo=open(altitude_png, "rb"),
                    caption="Altitude Profile"
                )

            # Send CSV file
            csv_path = flight_data.output_dir / "flight_data.csv"
            if csv_path.exists():
                await update.message.reply_document(
                    document=open(csv_path, "rb"),
                    filename=f"{callsign}_{target_date}.csv",
                    caption="Flight data CSV"
                )

            # Send KML file if available
            kml_path = flight_data.output_dir / "flight_path.kml"
            if kml_path.exists():
                await update.message.reply_document(
                    document=open(kml_path, "rb"),
                    filename=f"{callsign}_{target_date}.kml",
                    caption="Flight path for Google Earth"
                )

        except Exception as e:
            log.exception(f"Extraction error: {e}")
            await msg.edit_text(f"❌ Error: {e}")

    async def cmd_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized")
            return

        args = context.args
        if len(args) < 1:
            await update.message.reply_text(
                "Usage: /list <date>\n"
                "Example: /list 2024-12-31"
            )
            return

        try:
            target_date = self._parse_date(args[0])
        except ValueError as e:
            await update.message.reply_text(f"Invalid date: {e}")
            return

        msg = await update.message.reply_text(f"🔍 Scanning flights for {target_date}...")

        try:
            from flight_extractor import FlightScanner
            scanner = FlightScanner(self.config)

            callsigns = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: scanner.get_unique_callsigns(target_date)
            )

            if not callsigns:
                await msg.edit_text(f"No flights found on {target_date}")
                return

            sorted_cs = sorted(callsigns)
            response = f"📋 Flights on {target_date}\n"
            response += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            response += f"Found {len(sorted_cs)} callsigns:\n\n"

            # Show first 50
            for cs in sorted_cs[:50]:
                response += f"• {cs}\n"

            if len(sorted_cs) > 50:
                response += f"\n... and {len(sorted_cs) - 50} more"

            await msg.edit_text(response)

        except Exception as e:
            log.exception(f"List error: {e}")
            await msg.edit_text(f"❌ Error: {e}")

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
                await update.message.reply_text("No callsigns found in database.\nRun the callsign monitor to collect data.")
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
            await update.message.reply_text("Usage: /schedule <callsign>\nExample: /schedule FDB4CE")
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
            await update.message.reply_text("Usage: /lookup <callsign>\nExample: /lookup FDB4CE")
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

    def _parse_date(self, date_str: str) -> date:
        """Parse date string."""
        for fmt in ["%Y-%m-%d", "%Y%m%d", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Could not parse date: {date_str}")

    def _run_extraction(self, callsign: str, target_date: date):
        """Run the full extraction pipeline (blocking)."""
        # Extract data
        flight_data = self.extractor.extract(
            callsign=callsign,
            target_date=target_date,
            check_crossover=True,
            create_output_dir=True
        )

        if not flight_data.records:
            return flight_data

        output_dir = flight_data.output_dir

        # Save metadata and summary
        self.extractor.save_metadata(flight_data)
        self.extractor.save_summary(flight_data)

        # Export CSV
        csv_exporter = CSVExporter()
        csv_exporter.export(flight_data.records, output_dir / "flight_data.csv")

        # Generate KML
        kml_gen = KMLGenerator()
        kml_gen.generate(
            flight_data.records,
            output_dir / "flight_path.kml",
            callsign,
            str(target_date)
        )

        # Generate charts (PNG only for Telegram)
        generate_all_charts(
            records=flight_data.records,
            callsign=callsign,
            output_dir=output_dir,
            generate_png=True,
            generate_html=True
        )

        # Generate dashboard
        generate_dashboard(
            records=flight_data.records,
            callsign=callsign,
            output_dir=output_dir,
            flight_metadata={
                "aircraft_type": flight_data.metadata.aircraft_type,
                "registration": flight_data.metadata.registration,
                "duration_minutes": flight_data.metadata.duration_minutes,
                "max_altitude_ft": flight_data.metadata.max_altitude_ft,
                "records_extracted": flight_data.metadata.records_extracted,
            }
        )

        return flight_data

    def run(self):
        """Run the bot (blocking)."""
        self.app = Application.builder().token(self.token).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("extract", self.cmd_extract))
        self.app.add_handler(CommandHandler("list", self.cmd_list))

        # Callsign tracking commands
        self.app.add_handler(CommandHandler("callsigns", self.cmd_callsigns))
        self.app.add_handler(CommandHandler("schedule", self.cmd_schedule))
        self.app.add_handler(CommandHandler("lookup", self.cmd_lookup))
        self.app.add_handler(CommandHandler("csexport", self.cmd_csexport))

        log.info("Starting bot...")
        log.info(f"Allowed users: {self.allowed_users or 'ALL (not recommended)'}")

        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point."""
    if not HAS_TELEGRAM:
        print("Error: python-telegram-bot not installed")
        print("Install with: pip install python-telegram-bot")
        sys.exit(1)

    bot = FlightBot()
    bot.run()


if __name__ == "__main__":
    main()
