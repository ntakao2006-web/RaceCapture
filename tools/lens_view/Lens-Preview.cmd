@echo off
rem 本体のモニターに、録画に写る絵（補正・ズーム・計器込み）を出して、マウス・キーボードで画角を決める。
rem   --adb でUSB直結のadb（既定はPixelのテザリングで ssh unoq）
chcp 65001 >nul
cd /d "%~dp0"
python lens_preview_remote.py %*
pause
