@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo === Store ===

REM Run from this directory
set "REPO_DIR=%~dp0"
cd /d "%REPO_DIR%"

REM Load env from D:\records\.env (existing workflow)
set "ENV_FILE=D:\records\.env"
if not exist "%ENV_FILE%" (
  echo ERROR: .env not found at %ENV_FILE%
  exit /b 2
)

REM Load KEY=VALUE lines; ignore blanks and #comments
for /f "usebackq tokens=1* delims==" %%A in ("%ENV_FILE%") do (
  set "k=%%A"
  set "v=%%B"
  if not "!k!"=="" (
    set "first=!k:~0,1!"
    if not "!first!"=="#" (
      set "k=!k: =!"
      set "!k!=!v!"
    )
  )
)

REM Defaults if missing
if "!RECORDS_HOME!"=="" set "RECORDS_HOME=D:\records"
if "!RECORDS_OUT!"=="" set "RECORDS_OUT=!RECORDS_HOME!\outputs"

echo Repo folder: %REPO_DIR%
echo RECORDS_HOME=!RECORDS_HOME!
echo RECORDS_OUT=!RECORDS_OUT!
echo DISCOGS_USERNAME=!DISCOGS_USERNAME!
echo DISCOGS_USER=!DISCOGS_USER!

py -3 -u store.py
set "RC=%ERRORLEVEL%"

echo Exit code: %RC%
pause
exit /b %RC%
