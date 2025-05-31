# Run the simple unified File Classifier
Write-Host "Running Unified File Classifier..." -ForegroundColor Green

# Activate virtual environment
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
} else {
    Write-Host "Virtual environment not found. Make sure you've run 'create Venv.ps1' first." -ForegroundColor Red
    exit
}

# Run the unified application
try {
    python simple_unified_app.py
} catch {
    Write-Host "Error running unified application: $_" -ForegroundColor Red
}

Write-Host "Application closed." -ForegroundColor Green
