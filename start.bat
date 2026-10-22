@echo off
chcp 65001 >nul
rem Study Notes JP を開く。
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (echo 先に setup.bat を実行してください。 & pause & exit /b 1)
start "" .venv\Scripts\pythonw.exe run.py
