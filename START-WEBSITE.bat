@echo off
title Srash - Website Server
cd /d "%~dp0"
echo.
echo   Starting Srash website...
echo   The public link will appear shortly.
echo   It is also saved to: Desktop\CURRENT-URL.txt
echo   KEEP THIS WINDOW OPEN while the site is public.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "srash-supervisor.ps1"
pause