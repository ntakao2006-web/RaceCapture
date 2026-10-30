@echo off
rem Send hud.ini to the UNO Q (ssh unoq via Pixel tethering). The recorder switches to it within about a second. --default goes back to the original layout.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0hud_apply.py" %*
echo.
pause
