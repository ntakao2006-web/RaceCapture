@echo off
rem SUGO: clear the Ver.2 lap record before the final (after qualifying). Needs ssh unoq (Pixel tethering). The lines stay.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python "%~dp0sugo_setup.py" --reset %*
echo.
pause
