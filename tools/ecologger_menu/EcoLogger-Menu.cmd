@echo off
rem Ver.2 (UNO Q) menu: device status and buttons for the other tools. USB adb first, then Pixel tethering (ssh unoq).
rem The desktop shortcut opens this with pythonw (no console). Make-Shortcut.cmd puts it on the desktop.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
python ecologger_menu.py %*
if errorlevel 1 pause
