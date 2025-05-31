@echo off
:: This batch file runs the patched v3 version of the Qt File Classifier application
:: This version fixes the threading issues with task_done() being called too many times

:: Activate virtual environment
if exist ".\venv\Scripts\activate.bat" (
    call .\venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Please run 'create Venv.ps1' first.
    exit /b
)

:: Run the patched v3 application with improved thread handling
python -c "from qt_file_classifier_patched_v3 import start_app; start_app()"

:: Deactivate virtual environment
call deactivate
