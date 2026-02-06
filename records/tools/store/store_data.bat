@echo off
setlocal
echo === Store Data ===
echo Repo folder: %~dp0
py -3 -u "%~dp0store_data.py"
set EC=%ERRORLEVEL%
echo Exit code: %EC%
pause
exit /b %EC%
