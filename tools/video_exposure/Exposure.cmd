@echo off
rem 焼き込み録画の露出を見る・切り替える（録画プログラムが決める／カメラ任せ／明るく／暗く）。手順書5-21
rem   --status で見るだけ、--own・--camera・--brighter・--darker で選ばずに切り替え、--adb でUSB直結のadb
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
python exposure_apply.py %*
pause
