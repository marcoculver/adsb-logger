# Telegram Bots Guide

You now have **two separate bots** for different purposes:

## 🛩️ Bot 1: ADSB Flight Extractor

**Purpose:** Extract and analyze ANY flight from ADSB logs

**Token:** Set `FLIGHT_BOT_TOKEN` in `.env` file (see `.env.example`)

**Commands:**
- `/extract <callsign> <date>` - Extract flight with charts, CSV, KML
- `/list <date>` - List all flights on a date
- `/status` - Bot status

**Launch:**
```bash
# Windows
run_bot.bat

# Linux/WSL
./run_bot.sh
```

**Example Usage:**
```
/extract DAL123 2024-12-31
/extract UAE456 2025-01-01
/list 2024-12-31
```

---

## 📡 Bot 2: Callsign Tracker (@callsignloggerbot)

**Purpose:** Track Emirates/Flydubai flights (schedule patterns, database queries)

**Token:** Set `CALLSIGN_BOT_TOKEN` in `.env` file (see `.env.example`)

**Username:** @callsignloggerbot

**URL:** https://t.me/callsignloggerbot

**Commands:**
- `/callsigns [airline]` - List tracked Emirates/Flydubai callsigns
- `/schedule <callsign>` - Show schedule pattern by day/hour
- `/lookup <callsign>` - Live FR24 API lookup
- `/csexport` - Export database to CSV
- `/stats` - Database statistics

**Launch:**
```bash
# Windows
run_callsign_bot.bat

# Linux/WSL
./run_callsign_bot.sh
```

**Example Usage:**
```
/callsigns Emirates
/schedule UAE123
/lookup FDB4CE
/stats
```

---

## Running Both Bots Together

Yes! You can run both bots simultaneously since they use different tokens.

**Windows - Open TWO PowerShell windows:**

Window 1:
```powershell
cd M:\Dropbox\ADSBPi-Base\adsb-logger
.\run_bot.bat
```

Window 2:
```powershell
cd M:\Dropbox\ADSBPi-Base\adsb-logger
.\run_callsign_bot.bat
```

**Linux/WSL - Open TWO terminals:**

Terminal 1:
```bash
cd /path/to/adsb-logger
./run_bot.sh
```

Terminal 2:
```bash
cd /path/to/adsb-logger
./run_callsign_bot.sh
```

---

## Setup Requirements

### Install Dependencies (Once)

```bash
pip install python-telegram-bot numpy pandas matplotlib plotly simplekml
```

Or:
```bash
pip install -r requirements.txt
```

### Configuration

**Authorized Users:** Both bots are configured with user ID `1269568755`

To add more users:
1. Have them message `@userinfobot` to get their user ID
2. Edit the respective `.bat` or `.sh` file
3. Add user IDs comma-separated: `1269568755,987654321,555666777`

**Data Paths (Windows):**
- ADSB Bot: `M:\Dropbox\ADSBPi-Base\raw` (logs), `M:\Dropbox\ADSBPi-Base\analyses` (output)
- Callsign Bot: `M:\Dropbox\ADSBPi-Base\callsigns.db`

**Data Paths (Linux):**
- ADSB Bot: `/opt/adsb-logs` (logs), `/opt/adsb-logs/analyses` (output)
- Callsign Bot: `/opt/adsb-logs/callsigns.db`

---

## Integration with Callsign Monitor

For the **Callsign Bot** to have data, you need to run the monitor:

```bash
python3 -m callsign_logger.monitor
```

This continuously scans ADSB logs and populates the callsign database that the bot queries.

**Recommended Setup:**
1. Run callsign monitor in background (collects data)
2. Run Callsign Bot (provides Telegram interface to query data)
3. Run ADSB Bot as needed (extracts specific flights on demand)

---

## Quick Reference

| Task | Bot | Command |
|------|-----|---------|
| Extract any flight | ADSB Bot | `/extract DAL123 2024-12-31` |
| List all flights on date | ADSB Bot | `/list 2024-12-31` |
| Show tracked callsigns | Callsign Bot | `/callsigns` |
| Show schedule pattern | Callsign Bot | `/schedule UAE123` |
| Live flight lookup | Callsign Bot | `/lookup UAE123` |
| Export callsign DB | Callsign Bot | `/csexport` |

---

## Troubleshooting

### Wrong bot responding
- Make sure you're chatting with the correct bot
- ADSB Bot has general name
- Callsign Bot is @callsignloggerbot

### "Conflict" error
- Only one instance of each bot can run at a time
- Stop the bot (Ctrl+C) before restarting
- Make sure environment variable `TELEGRAM_BOT_TOKEN` is not set to old value

### Bot doesn't respond
- Check bot is running (see "Starting..." in terminal)
- Verify your user ID is in `TELEGRAM_ALLOWED_USERS`
- Try `/start` command first

### "No callsigns found"
- The callsign monitor needs to be running to collect data
- Run: `python3 -m callsign_logger.monitor`
- Give it time to scan logs and populate database

---

## Security Notes

- Keep bot tokens private!
- Always use `TELEGRAM_ALLOWED_USERS` whitelist
- Don't commit tokens to git
- Each bot has its own token - don't mix them up
