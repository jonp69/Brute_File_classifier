@echo off
REM This script runs the patched v4 version of the Qt File Classifier application
REM This version adds time estimation and scan resume capability

REM Activate virtual environment if it exists
if exist .\venv\Scripts\activate.bat (
    call .\venv\Scripts\activate
) else (
    echo Virtual environment not found. Please run "create Venv.ps1" first.
    exit /b
)

REM Run the patched v4 application with improved thread handling
python -c "from qt_file_classifier_patched_v4 import start_app; start_app()"

REM Deactivate virtual environment
deactivate
