@echo off
cd /d "%~dp0"

echo Checking dependencies...
pip install -r requirements.txt

echo Opening browser...
start app\index.html

timeout /t 1 /nobreak > nul

echo Starting Python server...
cd app
python server.py
pause