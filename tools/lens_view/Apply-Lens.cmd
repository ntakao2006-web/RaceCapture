@echo off
rem Lens-View.cmd で決めた歪みの補正＋ズームの値（lens.json）を本体の録画へ送る。
rem   --off で補正をやめて元の映像に戻す、--status で今の状態を見るだけ、--adb でUSB直結のadb
chcp 65001 >nul
cd /d "%~dp0"
python lens_apply.py %*
pause
