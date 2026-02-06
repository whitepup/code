@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "RECORDS_HOME=D:\records"
set "RECORDS_OUT=D:\records\outputs"
set "PUBLISH_REPO=C:\Users\David\Documents\GitHub\store"

echo === Store (TEST BUILD) ===
echo Repo folder: %~dp0
echo RECORDS_HOME=%RECORDS_HOME%
echo RECORDS_OUT=%RECORDS_OUT%

set "OUTDIR=%RECORDS_OUT%\store"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

set "LOG=%OUTDIR%\store.log"
echo Writing log to: %LOG%

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

pushd "%~dp0"
powershell -NoProfile -Command "py -3 -u 'store.py' 2>&1 | Tee-Object -FilePath '%LOG%'; exit $LASTEXITCODE"
set "EC=%ERRORLEVEL%"
popd

echo Exit code: %EC%
pause
exit /b %EC%
