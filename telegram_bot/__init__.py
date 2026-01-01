"""Telegram bots for ADSB flight tracking and callsign logging.

Use:
    from telegram_bot.flight_bot import FlightExtractionBot
    from telegram_bot.callsign_bot import CallsignBot

Note: The old combined bot (bot.py) is deprecated.
"""

# Don't import anything by default to avoid loading heavy dependencies
# when only one bot is needed
__all__ = []
