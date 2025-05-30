# Stop on errors
$ErrorActionPreference = "Stop"

Write-Host "Running Unified File Classifier..." -ForegroundColor Green

# Activate virtual environment
& .\venv\Scripts\Activate.ps1

try {
    # Run the unified version
    python unified_app.py
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
