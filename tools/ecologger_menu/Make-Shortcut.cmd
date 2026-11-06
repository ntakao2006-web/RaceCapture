@echo off
rem Put "EcoLogger Ver.2" on the desktop (opens ecologger_menu.py with pythonw). Run again after moving the repository.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcut.ps1"
pause
