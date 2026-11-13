@echo off
rem Show a QR code that hands the LTE command secret from this PC to a phone (opens the pit cover page with #k=<secret>).
rem The QR is drawn locally (qr.py); the secret is never printed or sent anywhere. The window closes itself after 2 minutes.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
python phone_key.py %*
if errorlevel 1 pause
