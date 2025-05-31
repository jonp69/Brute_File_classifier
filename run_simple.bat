@echo off
REM Run the simple unified File Classifier

echo Running Simple Unified File Classifier...
cd /d "%~dp0"

REM Activate virtual environment
call venv\Scripts\activate.bat || (
    echo Virtual environment not found. Make sure you've run 'create Venv.ps1' first.
    exit /b 1
)

REM Run the unified version
python simple_unified_app.py

if errorlevel 1 (
    echo Error running unified application.
) else (
    echo Application closed.
)

pause
