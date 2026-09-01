@echo off
powershell.exe -NoProfile -File "%~dp0start_racecapture_guard.ps1"
if errorlevel 1 pause
