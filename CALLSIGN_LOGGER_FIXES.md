# Callsign Logger Fixes

## Issues Fixed

### 1. ✅ Incorrect Flight Number Conversion

**Problem:** Callsigns like `UAE49K` were being converted to `EK49K`, which is incorrect.

**Root Cause:** The heuristic conversion was treating non-numeric suffixes as valid flight numbers. Callsigns with letters (UAE49K, FDB4CE) are typically positioning/ferry flights, not scheduled passenger flights.

**Fix:** Updated `convert_callsign_to_flight_number()` in `callsign_logger/fr24_api.py`:
- Now only converts callsigns with **pure numeric suffixes**
- `UAE123` → `EK123` ✓
- `UAE49K` → `None` (not converted, needs API lookup)
- `FDB4CE` → `None` (not converted, needs API lookup)

### 2. ✅ Missing Routes from FR24 API

**Problem:** Most callsigns in the CSV export had empty route/flight_number fields.

**Root Causes:**
1. Monitor only attempts API lookup once per callsign per session
2. If API is temporarily unavailable, it never retries
3. No way to backfill missing data for existing callsigns

**Fix:** Created backfill tool to query FR24 API for missing route data.

### 3. ✅ Database Duplicates

**Status:** Not an issue - database has `UNIQUE(callsign)` constraint.
The CSV export correctly shows one row per callsign.

## How to Use

### Step 1: Fix Existing Bad Data

The old heuristic put incorrect flight numbers (like EK49K) in your database. Run the backfill tool to correct them:

```powershell
# Windows
cd M:\Dropbox\ADSBPi-Base\adsb-logger
.\backfill_routes.bat --all
```

```bash
# Linux
python3 -m callsign_logger.backfill_routes --all
```

This will:
- Query FR24 API for ALL callsigns (including those with existing data)
- Update flight numbers and routes with correct API data
- Cache results to avoid repeated lookups

**Note:** This queries the API for each callsign, so it may take a while. The script includes rate limiting (1.5 seconds between requests).

### Step 2: Regular Backfills

After running the monitor for a while, you'll have new callsigns without route data. Run backfill periodically:

```powershell
# Update only callsigns missing route data
.\backfill_routes.bat
```

### Step 3: Export Clean CSV

After backfilling, export the updated CSV:

```powershell
python -m callsign_logger.database export
```

Or via Telegram bot:
```
/csexport
```

## Backfill Tool Options

```powershell
# Dry run - see what would be updated
.\backfill_routes.bat --dry-run

# Update only callsigns missing route data (default)
.\backfill_routes.bat

# Update ALL callsigns, even those with existing data
.\backfill_routes.bat --all
```

## Expected Results

### Before Backfill
```
callsign,flight_number,route,origin,destination
UAE123,EK123,,,
UAE456,EK456,,,
UAE49K,EK49K,,,          ← Wrong!
FDB4CE,,,,              ← Missing
```

### After Backfill
```
callsign,flight_number,route,origin,destination
UAE123,EK123,DXB-LHR,DXB,LHR
UAE456,EK456,DXB-JFK,DXB,JFK
UAE49K,EK9049,DXB-DOH,DXB,DOH    ← Corrected via API
FDB4CE,FZ9208,DXB-MCT,DXB,MCT   ← Filled via API
```

## How It Works

### Heuristic Conversion (Fast, but Limited)
1. Monitor sees callsign `UAE123` in ADSB logs
2. Tries FR24 API lookup (if available)
3. If API fails/unavailable, uses heuristic: `UAE123` → `EK123`
4. **NEW:** Only converts pure numeric suffixes
5. **NEW:** Non-numeric callsigns return `None` instead of bad conversion

### API Lookup (Accurate, but Requires Active Flight)
1. Backfill tool queries FR24 API for each callsign
2. Gets actual flight number, route, airports from API
3. Updates database and caches result
4. **Limitation:** Flight must be currently active to get data

### Positioning/Ferry Flights

Callsigns with letters (UAE49K, FDB4CE, UAEHAJ) are often:
- **Positioning flights** - Moving empty aircraft between airports
- **Ferry flights** - Maintenance, delivery, or storage flights
- **Special flights** - Charter, government, or training flights

These have flight numbers assigned, but they're **not regular scheduled flights**. They must be looked up via API.

## Workflow

**Best Practice:**
1. Run callsign monitor continuously (collects data)
2. Run backfill tool daily/weekly (fills missing routes)
3. Export CSV when needed (for analysis)

**Automated Setup (Recommended):**
```powershell
# Terminal 1: Run monitor (always running)
python -m callsign_logger.monitor

# Terminal 2: Run backfill daily
# (use Task Scheduler on Windows or cron on Linux)
.\backfill_routes.bat
```

## API Notes

- **Rate limiting:** Backfill waits 1.5 seconds between requests
- **API availability:** Only queries flights currently in the air
- **Caching:** Route data cached for 24 hours to reduce API calls
- **Positioning flights:** May not always be in FR24 database

## Troubleshooting

### "No data returned" for many callsigns
- Flights might not be currently active
- Try running backfill during peak hours (morning/evening)
- Some positioning flights may never be in FR24 database

### "API connection failed"
- Check your FR24 API token is correct
- Verify API hasn't been rate limited
- Try again later

### Still seeing incorrect flight numbers
- Run `.\backfill_routes.bat --all` to force update ALL callsigns
- Check the monitor isn't running while backfilling
- Restart monitor after backfill completes

## Future Improvements

Potential enhancements:
1. Scheduled backfill in monitor (every X hours)
2. Batch API queries (if FR24 API supports it)
3. Alternative data sources for positioning flights
4. Historical flight data lookup (not just live flights)
