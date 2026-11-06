@echo off
rem SUGO: put the RaceCapture app back on the HDMI screen instead of EcoCapture DASH. Needs ssh unoq (Pixel tethering).
rem Logging is not touched. Add --boot to make it the screen at power-on as well (Show-Dash.cmd --boot undoes it).
rem If uno-q.local does not resolve, unoq_ssh.py finds the UNO Q by IP on the same network.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0..\collect_logs\unoq_ssh.py" /opt/logger-v2-racecapture/dash_switch.sh racecapture %*
echo.
pause
