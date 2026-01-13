
@echo off
REM === hunt: build top-sellers spreadsheets via Discogs ===
SETLOCAL ENABLEDELAYEDEXPANSION

echo === hunt: build top-sellers spreadsheets (Discogs-driven) ===
echo Folder: %~dp0

where py >nul 2>nul
IF %ERRORLEVEL% EQU 0 (
    SET _PY=py -3
) ELSE (
    SET _PY=python
)

cd /d "%~dp0"
echo Using: %_PY%
echo.

%_PY% hunt_build_top_sellers.py %*
echo.
echo Done.
pause
