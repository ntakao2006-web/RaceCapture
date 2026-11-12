@echo off
rem Stop the course-walk LTE radio log and copy it to drive_logs. See radio_walk_pc.py.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0radio_walk_pc.py" fetch %*
echo.
pause
