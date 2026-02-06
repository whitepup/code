@echo off
setlocal
echo.
echo === Apply Store Prices (from pricing_overrides.csv) ===
echo This updates store_inventory.json in your OUTPUT site.
echo.

set "RECORDS_HOME=D:\records"
set "RECORDS_OUT=D:\records\outputs"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

pushd "%~dp0"
py -3 -u "apply_store_prices.py"
set "EC=%ERRORLEVEL%"
popd

echo Exit code: %EC%
pause
exit /b %EC%
