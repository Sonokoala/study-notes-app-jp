@echo off
chcp 65001 >nul
rem 初回のセットアップ: .venv にこのアプリ専用の Python 環境を作り、必要なライブラリを入れる。
cd /d "%~dp0"
where python >nul 2>nul || (echo Python が入っていません。https://www.python.org/downloads/ からインストールし、「Add python.exe to PATH」にチェックを入れてください。 & pause & exit /b 1)
python -m venv .venv || (pause & exit /b 1)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt || (pause & exit /b 1)
echo.
echo セットアップが終わりました。start.bat をダブルクリックすると Study Notes JP が開きます。
pause
