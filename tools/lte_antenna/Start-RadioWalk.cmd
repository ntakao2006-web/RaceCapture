@echo off
rem Start the course-walk LTE radio log on the UNO Q (30 min). See radio_walk_pc.py.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0radio_walk_pc.py" start %*
echo.
pause
