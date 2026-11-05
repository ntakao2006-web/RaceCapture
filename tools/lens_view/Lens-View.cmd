@echo off
rem USBカメラの映像を、歪みを補正してズームして見る。Windowsの「カメラ」アプリは先に閉じておく。
chcp 65001 >nul
cd /d "%~dp0"
python lens_view.py %*
if errorlevel 1 pause
