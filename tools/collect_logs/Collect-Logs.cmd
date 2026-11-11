@echo off
rem Opens the collector page (same as Collect-Video.cmd): one "collect" button takes new drive logs, videos and SD cards. Nothing is deleted.
rem With arguments it runs the old text-only collector (python collect_logs.py --help).
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
if "%~1"=="" (
  python "%~dp0..\video_collect\video_collect.py"
) else (
  python "%~dp0collect_logs.py" %*
)
echo.
pause
