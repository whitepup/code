@echo off
setlocal

REM === Ad Generator: Single Collage ===
REM Expected location:
REM   C:\Users\David\Documents\GitHub\code\records\tools\ad_generator
REM Images in:
REM   C:\Users\David\Documents\GitHub\store\images

set IMAGES_DIR=C:\Users\David\Documents\GitHub\store\images

cd /d "%~dp0"
set PYTHON=py -3

%PYTHON% ad_generator.py single --images-dir "%IMAGES_DIR%" --output "ad_all_records.jpg"
if errorlevel 1 (
  echo.
  echo [ERROR] ad_generator.py failed. See messages above.
  echo.
  pause
  exit /b %errorlevel%
)

echo.
echo Done. Output:
echo   %CD%\ad_all_records.jpg
echo.
pause
