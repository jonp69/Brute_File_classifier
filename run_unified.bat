@echo off
REM Run the File Classifier with unified interface (all modes in one app)

echo Running Unified File Classifier...
cd /d "%~dp0"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the unified version
python unified_app.py

pause
