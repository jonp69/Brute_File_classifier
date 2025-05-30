@echo off
REM Run the File Classifier with the patched fixes for pygame surface and UI layout issues

echo Running File Classifier with display surface and UI layout fixes...
cd /d "%~dp0"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the fixed version
python run_file_classifier.py

REM Deactivate virtual environment
call deactivate
