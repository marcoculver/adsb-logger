# Telegram Bots Separation - Complete

## What Was Done

Successfully separated the Telegram bot functionality into two independent bots:

### 1. ✅ ADSB Flight Extractor Bot
- **File:** `telegram_bot/flight_bot.py`
- **Purpose:** Extract ANY flight from ADSB logs
- **Commands:** `/extract`, `/list`, `/status`
- **Launch:** `run_bot.bat` (Windows) or `run_bot.sh` (Linux)
- **Token:** Set `FLIGHT_BOT_TOKEN` in `.env` file

### 2. ✅ Callsign Tracker Bot (@callsignloggerbot)
- **File:** `telegram_bot/callsign_bot.py`
- **Purpose:** Track Emirates/Flydubai only (schedules, patterns)
- **Commands:** `/callsigns`, `/schedule`, `/lookup`, `/csexport`, `/stats`
- **Launch:** `run_callsign_bot.bat` (Windows) or `run_callsign_bot.sh` (Linux)
- **Token:** Set `CALLSIGN_BOT_TOKEN` in `.env` file

## Files Created/Modified

### New Files
- `telegram_bot/flight_bot.py` - Flight extraction bot (ADSB)
- `telegram_bot/callsign_bot.py` - Callsign tracking bot
- `run_callsign_bot.bat` - Windows launcher for callsign bot
- `run_callsign_bot.sh` - Linux launcher for callsign bot
- `TELEGRAM_BOTS_GUIDE.md` - Complete guide for both bots

### Modified Files
- `run_bot.bat` - Updated to launch flight_bot.py
- `run_bot.sh` - Updated to launch flight_bot.py

### Original Files (kept for reference)
- `telegram_bot/bot.py` - Original combined bot (not used anymore)

## How to Use

### On Windows

**Terminal 1 - ADSB Bot:**
```powershell
cd M:\Dropbox\ADSBPi-Base\adsb-logger
.\run_bot.bat
```

**Terminal 2 - Callsign Bot:**
```powershell
cd M:\Dropbox\ADSBPi-Base\adsb-logger
.\run_callsign_bot.bat
```

### On Linux/WSL

**Terminal 1 - ADSB Bot:**
```bash
./run_bot.sh
```

**Terminal 2 - Callsign Bot:**
```bash
./run_callsign_bot.sh
```

## Key Differences

| Feature | ADSB Bot | Callsign Bot |
|---------|----------|--------------|
| Extract any flight | ✅ | ❌ |
| List flights by date | ✅ | ❌ |
| Generate charts/KML | ✅ | ❌ |
| Track Emirates/Flydubai | ❌ | ✅ |
| Schedule patterns | ❌ | ✅ |
| FR24 API lookup | ❌ | ✅ |
| Database export | ❌ | ✅ |
| Uses FlightExtractor | ✅ | ❌ |
| Uses CallsignDatabase | ❌ | ✅ |

## Data Sources

**ADSB Bot:**
- Reads: ADSB JSONL log files
- Writes: Flight analyses (CSV, KML, PNG charts)
- Database: None

**Callsign Bot:**
- Reads: Callsign SQLite database
- Writes: Nothing (read-only queries)
- Database: `callsigns.db` (populated by callsign monitor)

## Testing Status

- ✅ Bot modules created and separated
- ✅ Launch scripts updated
- ✅ Documentation created
- ⏳ Live testing needed (requires dependencies on target machine)

## Next Steps

1. On your Windows machine, test both bots can run simultaneously
2. Verify ADSB bot can extract flights
3. Verify Callsign bot can query database (needs monitor running first)
4. Both bots should work independently without conflicts

## Rollback Plan

If you need to go back to the old combined bot:
- Edit launch scripts to use `telegram_bot.bot` instead
- The original `telegram_bot/bot.py` is still present

## Notes

- Both bots can run at the same time (different tokens)
- No shared state between bots
- Each bot focuses on its specific purpose
- Cleaner separation of concerns
