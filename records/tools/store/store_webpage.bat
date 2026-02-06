@echo off
setlocal
echo === Store Webpage ===
echo Repo folder: %~dp0
py -3 -u "%~dp0store_webpage.py"
set EC=%ERRORLEVEL%
echo Exit code: %EC%
pause
exit /b %EC%
