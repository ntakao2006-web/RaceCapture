@echo off
rem SUGO: show EcoCapture DASH on the HDMI screen (stops the RaceCapture app). Needs ssh unoq (Pixel tethering).
rem Logging is not touched. Add --boot to make it the screen at power-on as well.
rem If uno-q.local does not resolve, unoq_ssh.py finds the UNO Q by IP on the same network.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0..\collect_logs\unoq_ssh.py" /opt/logger-v2-racecapture/dash_switch.sh dash %*
echo.
pause
