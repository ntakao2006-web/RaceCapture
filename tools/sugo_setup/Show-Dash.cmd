@echo off
rem SUGO: show EcoCapture DASH on the HDMI screen (stops the RaceCapture app). Needs ssh unoq (Pixel tethering).
rem Logging is not touched. Add --boot to make it the screen at power-on as well.
chcp 65001 >nul
ssh -o ConnectTimeout=8 unoq /opt/logger-v2-racecapture/dash_switch.sh dash %*
echo.
pause
