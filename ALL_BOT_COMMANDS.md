# All Bot Commands - Restored and Working

## ✅ All Original Commands Are Back

All restrictions removed - commands will now run and give you helpful error messages if data is missing.

---

## 🛩️ Flight Bot (@adsb_analyser_bot)

### Working Everywhere:
- `/start` - Welcome message
- `/help` - Show all commands
- `/status` - Bot status and log directory info

### Requires ADSB Log Files:
- `/extract <callsign> <date>` - Extract flight (e.g., `/extract UAE123 2024-12-31`)
- `/list <date>` - List all flights on date (e.g., `/list 2024-12-31`)

**Log Directory:**
- Windows: `M:\Dropbox\ADSBPi-Base\raw`
- Linux: `/opt/adsb-logs`

---

## 📡 Callsign Bot (@callsignloggerbot)

### Working Everywhere:
- `/start` - Welcome message
- `/help` - Show all commands
- `/stats` - Database statistics

### Requires Database Data:
- `/callsigns [airline]` - List callsigns (e.g., `/callsigns Emirates`)
- `/schedule <callsign>` - Schedule pattern (e.g., `/schedule UAE123`)
- `/lookup <callsign>` - Live FR24 lookup (e.g., `/lookup UAE123`)
- `/csexport` - Export database to CSV

**Database:**
- Path: `/home/chasingskye/adsb-logger/data/callsigns.db`
- Populated by: `python3 -m callsign_logger.monitor`

---

## 🏥 Health Bot (@csProjectHealth_bot)

### Working Everywhere:
- `/start` - Welcome message
- `/quick` - Quick status (works on any system)

### Requires Health Scripts (Pi Only):
- `/health` - Full system health check
- `/status` - Detailed status report

**Scripts:**
- `/usr/local/bin/adsb-health-check.sh`
- `/usr/local/bin/adsb-status-report.sh`

---

## Current Status

All three bots are running:
- ✅ Flight Bot (PID: 79430)
- ✅ Callsign Bot (PID: 80984)
- ✅ Health Bot (PID: 123733)

## What Changed

**Before:** Some commands showed "Pi-only" warnings and wouldn't run

**Now:** All commands work! They will:
- ✅ Execute if requirements are met
- ✅ Show helpful error if data/scripts missing
- ✅ Tell you exactly what's needed

## Testing Commands

Try these NOW (they work everywhere):

```
@adsb_analyser_bot → /status
@callsignloggerbot → /stats
@csProjectHealth_bot → /quick
```

Commands that need data will tell you what's missing when you run them.

## Example Responses

### /extract without logs:
```
❌ No logs found for 2024-12-31

Looking in: /opt/adsb-logs
Try checking your log directory is mounted/accessible
```

### /health without scripts:
```
⚠️ Health Check Script Not Found

Looking for: /usr/local/bin/adsb-health-check.sh

Install the script on this system or use /quick for basic status.
```

All your old commands are back and working! 🎉
