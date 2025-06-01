# This script runs the patched v4 version of the Qt File Classifier application
# This version adds time estimation and scan resume capability

# Activate virtual environment if it exists
if (Test-Path -Path ".\venv\Scripts\Activate.ps1") {
    & .\venv\Scripts\Activate.ps1
} else {
    Write-Host "Virtual environment not found. Please run 'create Venv.ps1' first."
    exit
}

# Run the patched v4 application with improved thread handling
python -c "from qt_file_classifier_patched_v4 import start_app; start_app()"

# Deactivate virtual environment
deactivate
