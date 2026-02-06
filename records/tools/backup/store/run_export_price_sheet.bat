@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "RECORDS_HOME=D:\records"
set "RECORDS_OUT=D:\records\outputs"

echo === Export Price Sheet ===
echo Repo folder: %~dp0
echo RECORDS_HOME=%RECORDS_HOME%
echo RECORDS_OUT=%RECORDS_OUT%

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

pushd "%~dp0"
py -3 -u "export_price_sheet.py"
set "EC=%ERRORLEVEL%"
popd

echo Exit code: %EC%
pause
exit /b %EC%
