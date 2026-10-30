@echo off
rem Show the burned-in video HUD (hud.ini) in the browser. It redraws every time hud.ini is saved. Close this window to stop.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0hud_preview.py" %*
echo.
pause
