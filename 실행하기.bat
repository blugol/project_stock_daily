@echo off
:: 실행 위치를 현재 폴더(stock)로 강제 고정
cd /d "%~dp0"

echo Opening browser...
start app\index.html

timeout /t 1 /nobreak > nul

echo Starting Python server...
cd app
python server.py
