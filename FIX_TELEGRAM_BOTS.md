# Telegram Bots - Dependency Issues Fixed

## Problem Diagnosed

Both bots were failing due to missing Python dependencies:

### Issue 1: telegram_bot/__init__.py Loading All Dependencies
The `__init__.py` was auto-importing the old combined bot, which loaded flight_charts and all heavy dependencies (numpy, matplotlib, etc.) even when running the lightweight callsign bot.

**Fixed:** Updated `__init__.py` to not auto-import anything.

### Issue 2: Missing Dependencies
The bots require these Python packages which aren't installed on your system:

**Callsign Bot (lightweight):**
- `python-telegram-bot` ← Missing

**Flight Bot (heavy):**
- `python-telegram-bot` ← Missing
- `numpy` ← Missing
- `pandas` ← Missing
- `matplotlib` ← Missing
- `plotly` ← Missing
- `simplekml` ← Missing

## Solution

### Quick Fix - Install All Dependencies

```bash
pip install python-telegram-bot numpy pandas matplotlib plotly simplekml
```

Or use requirements file:
```bash
pip install -r requirements.txt
```

### Minimal Fix - Just Run Callsign Bot

If you only want the callsign tracker bot (no flight extraction):

```bash
# Only install telegram library
pip install python-telegram-bot

# Run callsign bot
python -m telegram_bot.callsign_bot
```

The callsign bot is lightweight and doesn't need numpy/pandas/matplotlib!

## Testing

### Test Callsign Bot
```bash
python3 -c "
from telegram_bot.callsign_bot import CallsignBot
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8380442252:AAHhJd8vHDGEDHZK0-F7k7LY3fwmnINqGbw'
os.environ['TELEGRAM_ALLOWED_USERS'] = '1269568755'
bot = CallsignBot()
print('✓ Callsign bot OK')
"
```

### Test Flight Bot
```bash
python3 -c "
from telegram_bot.flight_bot import FlightExtractionBot
import os
os.environ['TELEGRAM_BOT_TOKEN'] = '8230471568:AAHuAf9uYkd9S5ZngkZ7PBo2aXEd4QrttsA'
os.environ['TELEGRAM_ALLOWED_USERS'] = '1269568755'
bot = FlightExtractionBot()
print('✓ Flight bot OK')
"
```

## On Raspberry Pi

If you're running on your Pi:

```bash
# SSH to Pi
ssh pi@your-pi-address

# Navigate to project
cd /path/to/adsb-logger

# Pull latest fixes
git pull

# Install dependencies
pip3 install python-telegram-bot numpy pandas matplotlib plotly simplekml

# Or just telegram if you only want callsign bot
pip3 install python-telegram-bot

# Run setup again
sudo ./setup_pi_bots.sh
```

## Summary of Changes

**File Updated:** `telegram_bot/__init__.py`
- Removed auto-import of old combined bot
- Prevents loading heavy dependencies when not needed
- Each bot now loads only its required dependencies

**Result:**
- Callsign bot is now lightweight (only needs python-telegram-bot)
- Flight bot still needs all visualization libraries
- Both bots work independently

## Next Steps

1. **Install dependencies** (see above)
2. **Test bots work** (see testing section)
3. **Run bots** via:
   - Windows: `run_bot.bat` / `run_callsign_bot.bat`
   - Linux: `./run_bot.sh` / `./run_callsign_bot.sh`
   - Pi services: `sudo systemctl start adsb-flight-bot callsign-tracker-bot`

The fix has been committed to git - just `git pull` and install dependencies!
