@echo off
REM Run the File Classifier with PyQt5 interface

echo Running PyQt5 File Classifier...
cd /d "%~dp0"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the PyQt5 version
python qt_file_classifier.py

pause
