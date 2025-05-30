# Activate virtual environment and run the application

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

try {
    # Verify Ollama is running
    Write-Host "Checking Ollama status..." -ForegroundColor Yellow
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -Method Get -ErrorAction SilentlyContinue
        Write-Host "Ollama is running. Version: $($response.version)" -ForegroundColor Green
    } catch {
        Write-Host "Warning: Ollama does not appear to be running. Please start Ollama before using the file classifier." -ForegroundColor Red
        Write-Host "Download Ollama from https://ollama.com/ if you haven't installed it yet." -ForegroundColor Yellow
        $shouldContinue = Read-Host "Continue anyway? (y/n)"
        if ($shouldContinue -ne "y" -and $shouldContinue -ne "Y") {
            exit
        }
    }

    # Run the application
    Write-Host "Starting File Classifier & Search..." -ForegroundColor Green
    python file_classifier.py
}
finally {
    # Deactivate virtual environment when the app closes
    deactivate
    Write-Host "Environment deactivated. Goodbye!" -ForegroundColor Green
}