@echo off
rem SUGO: put the RaceCapture app back on the HDMI screen instead of EcoCapture DASH. Needs ssh unoq (Pixel tethering).
rem Logging is not touched. Add --boot to make it the screen at power-on as well (Show-Dash.cmd --boot undoes it).
chcp 65001 >nul
ssh -o ConnectTimeout=8 unoq /opt/logger-v2-racecapture/dash_switch.sh racecapture %*
echo.
pause
