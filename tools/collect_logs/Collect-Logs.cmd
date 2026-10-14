@echo off
rem Collect new drive logs from SD cards (Ver.1 / Ver.2) and the USB-connected UNO Q. Sources are never deleted.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0collect_logs.py" %*
echo.
pause
