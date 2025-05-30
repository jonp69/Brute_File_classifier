@echo off
REM Run the File Classifier with parallel processing for faster scanning

echo Running File Classifier with parallel scanning (much faster)...
cd /d "%~dp0"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the fixed version with parallel processing
python run_file_classifier.py

echo Done.
pause
