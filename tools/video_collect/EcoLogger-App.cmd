@echo off
rem EcoLogger PC app (new entry, work in progress): "Now" tab (logger status with pass/fail) and "Collect" tab. Opens in the browser.
rem Opens even without the logger; it keeps looking (USB, then tethering) and switches by itself. Close this window to stop.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0video_collect.py" --tab now %*
echo.
pause
