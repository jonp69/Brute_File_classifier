@echo off
REM Run the File Classifier in turbo mode - parallel processing + offline mode for maximum speed

echo Running File Classifier in TURBO mode (parallel scanning + offline mode)...
cd /d "%~dp0"

REM Create temporary config with offline mode enabled
powershell -Command "(Get-Content -Raw config.json | ConvertFrom-Json) | ForEach-Object { $_.offline_mode=$true } | ConvertTo-Json | Set-Content config.temp.json"
powershell -Command "Move-Item -Force config.temp.json config.json"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the fixed version with parallel processing
python run_file_classifier.py

REM Reset offline mode
powershell -Command "(Get-Content -Raw config.json | ConvertFrom-Json) | ForEach-Object { $_.offline_mode=$false } | ConvertTo-Json | Set-Content config.temp.json"
powershell -Command "Move-Item -Force config.temp.json config.json"

echo Configuration restored to online mode.
pause
