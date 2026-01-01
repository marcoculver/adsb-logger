@echo off
REM Backfill missing route data from FR24 API
REM
REM This will query the FR24 API for callsigns that are missing
REM flight numbers and routes, and update the database.
REM
REM Usage:
REM   backfill_routes.bat           - Update callsigns missing route data
REM   backfill_routes.bat --all     - Update ALL callsigns
REM   backfill_routes.bat --dry-run - Show what would be updated

echo ============================================================
echo   FR24 Route Data Backfill Tool
echo ============================================================
echo.
echo This will query the FlightRadar24 API to fill in missing
echo flight numbers and routes for tracked callsigns.
echo.

python -m callsign_logger.backfill_routes %*

if errorlevel 1 (
    echo.
    echo Script exited with error.
    pause
)
