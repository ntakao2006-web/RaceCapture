@echo off
rem Collect onboard videos from the Ver.2 logger (UNO Q) over USB, offline. Opens a page in the browser. Close this window to stop.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0video_collect.py" %*
echo.
pause
