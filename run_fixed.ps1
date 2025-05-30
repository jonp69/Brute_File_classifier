# Stop on errors
$ErrorActionPreference = "Stop"

Write-Host "Running File Classifier with display surface and UI layout fixes..." -ForegroundColor Green

# Activate virtual environment
& .\venv\Scripts\Activate.ps1

try {
    # Run fixed version
    python run_file_classifier.py
}
finally {
    # Deactivate virtual environment when the app closes
    deactivate
    Write-Host "Application closed." -ForegroundColor Green
}
