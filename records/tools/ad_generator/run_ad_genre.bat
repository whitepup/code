@echo off
setlocal
REM === Per-Artist Majority Genre Grids ===
REM Uses:
REM   - Pop preference
REM   - Country preferred over Folk when both present
REM   - Folk, World, & Country split
REM   - Tiny genres (<36) -> Misc
REM   - Per-artist majority genre bucket

set STORE=C:\Users\David\Documents\GitHub\store
set IMAGES=%STORE%\images
set INV=%STORE%\store_inventory.json

cd /d "%~dp0"
py -3 ad_generator.py genre --images-dir "%IMAGES%" --inventory-json "%INV%" --output-dir "ads_by_genre" --tile 192

echo.
pause
