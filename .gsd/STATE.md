# GSD STATE

## Current Phase
Phase 7: Regional Context & Specialized Time Display (COMPLETED)

## Wave 1 Summary
**Objective:** Update database and UI for regional tracking.
**Changes:**
- Updated `database.py` with `region` column and migration logic.
- Updated `fetcher.py` to use regional RSS feeds.
- Updated `app.py` with IST conversion, Relative Time column, and Region selection.
**Verification:**
- Ran `test_regional_fetch.py` and successfully fetched India-specific news for SBI.
- Articles in dashboard now show "Time (IST)" and "Relative Time".
**Next Wave TODO:**
- Monitor for any edge cases in relative time display.
