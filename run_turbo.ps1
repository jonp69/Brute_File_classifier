# Stop on errors
$ErrorActionPreference = "Stop"

Write-Host "Running File Classifier in TURBO mode (parallel scanning + offline mode)..." -ForegroundColor Green

# Temporarily set offline mode in config
$config = Get-Content -Raw "config.json" | ConvertFrom-Json
$originalOfflineMode = $config.offline_mode
$config.offline_mode = $true
$config | ConvertTo-Json | Set-Content "config.json"

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
    # Restore original offline mode setting
    $config = Get-Content -Raw "config.json" | ConvertFrom-Json
    $config.offline_mode = $originalOfflineMode
    $config | ConvertTo-Json | Set-Content "config.json"
    
    Write-Host "Configuration restored to original mode." -ForegroundColor Green
    
    # Deactivate virtual environment if it's active
    if ($env:VIRTUAL_ENV) {
        deactivate
    }
}
