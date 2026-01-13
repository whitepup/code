@echo off
setlocal

REM === Ad Generator: 10x10 Grids (padded last page) ===
REM Expected location:
REM   C:\Users\David\Documents\GitHub\code\records\tools\ad_generator
REM Images in:
REM   C:\Users\David\Documents\GitHub\store\images

set IMAGES_DIR=C:\Users\David\Documents\GitHub\store\images

cd /d "%~dp0"
set PYTHON=py -3

%PYTHON% ad_generator.py grid10 --images-dir "%IMAGES_DIR%" --output-dir "ads_10x10"
if errorlevel 1 (
  echo.
  echo [ERROR] ad_generator.py failed. See messages above.
  echo.
  pause
  exit /b %errorlevel%
)

echo.
echo Done. 10x10 images in:
echo   %CD%\ads_10x10
echo.
pause
