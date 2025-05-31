@echo off
REM Run the File Classifier with PyQt5 interface with improved statistics and filtering
echo Running PyQt5 File Classifier with improved statistics and filtering...
cd /d "%~dp0"
REM Activate virtual environment
call venv\Scripts\activate.bat
REM Run the improved PyQt5 version
python qt_file_classifier_patched_v2.py
pause
