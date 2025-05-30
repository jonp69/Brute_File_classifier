# Stop on errors
$ErrorActionPreference = "Stop"

Write-Host "Running File Classifier with parallel scanning (much faster)..." -ForegroundColor Green

# Activate virtual environment
& .\venv\Scripts\Activate.ps1

try {
    # Run fixed version with parallel processing
    python run_file_classifier.py
}
catch {
    Write-Host "Error running File Classifier: $_" -ForegroundColor Red
}
finally {
    # Deactivate virtual environment if it's active
    if ($env:VIRTUAL_ENV) {
        deactivate
    }
}
