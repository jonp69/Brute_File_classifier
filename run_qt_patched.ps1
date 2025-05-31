# Run the PyQt5 version of File Classifier
Write-Host "Running PyQt5 File Classifier with improved thread safety..." -ForegroundColor Green

# Get the current directory
$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = Split-Path -Parent $scriptPath

# Activate virtual environment
& "$scriptDir\venv\Scripts\activate.ps1"

# Run the PyQt5 version
python "$scriptDir\qt_file_classifier_patched.py"
