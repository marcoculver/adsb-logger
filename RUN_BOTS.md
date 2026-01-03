# Running the Telegram Bots

All bots have been successfully tested and are ready to use!

## Quick Start

### 1. Activate Virtual Environment

The bots require a Python virtual environment with dependencies installed:

```bash
cd /home/chasingskye/adsb-logger
source venv/bin/activate
```

### 2. Load Environment Variables

```bash
set -a
source .env
set +a
```

### 3. Run a Bot

#### Flight Extraction Bot (@adsb_analyser_bot)
```bash
python3 -m telegram_bot.flight_bot
```

**Commands:**
- `/extract <callsign> <date>` - Extract any flight
- `/list <date>` - List all flights
- `/status` - Bot status

#### Callsign Tracker Bot (@callsignloggerbot)
```bash
export TELEGRAM_BOT_TOKEN=$CALLSIGN_BOT_TOKEN
python3 -m telegram_bot.callsign_bot
```

**Commands:**
- `/callsigns` - List tracked callsigns
- `/schedule <callsign>` - Show schedule pattern
- `/lookup <callsign>` - Live FR24 lookup
- `/stats` - Database stats

**Note:** Requires `/opt/adsb-logs` directory on the Pi

#### Health Monitoring Bot (@csProjectHealth_bot)
```bash
export TELEGRAM_BOT_TOKEN=$HEALTH_BOT_TOKEN
python3 health_bot.py
```

**Commands:**
- `/start` - Welcome message
- `/health` - Run health check
- `/status` - Generate status report
- `/quick` - Quick system overview

## One-Line Launch Commands

### Flight Bot
```bash
source venv/bin/activate && set -a && source .env && set +a && python3 -m telegram_bot.flight_bot
```

### Callsign Bot
```bash
source venv/bin/activate && set -a && source .env && set +a && export TELEGRAM_BOT_TOKEN=$CALLSIGN_BOT_TOKEN && python3 -m telegram_bot.callsign_bot
```

### Health Bot
```bash
source venv/bin/activate && set -a && source .env && set +a && export TELEGRAM_BOT_TOKEN=$HEALTH_BOT_TOKEN && python3 health_bot.py
```

## Using the Launch Scripts

The existing launch scripts need to be updated to use the virtual environment:

```bash
# Edit run_bot.sh to add venv activation
nano run_bot.sh
```

Add this near the top after configuration:
```bash
# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi
```

## Test Results Summary

✅ **All bots tested successfully on 2026-01-02:**

1. **Flight Bot** - Started and connected to Telegram API ✅
2. **Callsign Bot** - Token valid, database initializes ✅
3. **Health Bot** - Started and connected to Telegram API ✅

## Dependencies Installed

All required packages are installed in `venv/`:
- python-telegram-bot 22.5
- numpy 2.4.0
- pandas 2.3.3
- matplotlib 3.10.8
- plotly 6.5.0
- simplekml 1.3.6

## Security

- ✅ All tokens stored in `.env` (gitignored)
- ✅ Old tokens revoked
- ✅ New tokens working
- ✅ Virtual environment isolated from system Python

## Troubleshooting

**Bot doesn't respond:**
- Verify bot is running (`ps aux | grep python`)
- Check your user ID is in `TELEGRAM_ALLOWED_USERS`
- Send `/start` to the bot first

**Import errors:**
- Make sure virtual environment is activated
- Check `which python3` shows venv path

**Permission denied:**
- Callsign bot needs `/opt/adsb-logs` directory
- Run on Pi or create test directory with write permissions
