
@echo off
REM === hunt: top-sellers -> Discogs collection + HTML + covers (xlsx-driven) ===
SETLOCAL ENABLEDELAYEDEXPANSION

echo === hunt: build top-sellers-by-decade pages (Discogs-integrated, from .xlsx) ===
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

%_PY% hunt.py %*
echo.
echo Done.
pause
