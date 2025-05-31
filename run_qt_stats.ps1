# Run the PyQt5 version of File Classifier with improved statistics and filtering
Write-Host "Running PyQt5 File Classifier with improved statistics and filtering..." -ForegroundColor Green

# Get the current directory
$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = Split-Path -Parent $scriptPath

# Activate virtual environment
& "$scriptDir\venv\Scripts\activate.ps1"

# Run the improved PyQt5 version
python "$scriptDir\qt_file_classifier_patched_v2.py"
