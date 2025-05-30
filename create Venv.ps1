# Stop on errors
$ErrorActionPreference = "Stop"

Write-Host "Setting up File Classifier environment..." -ForegroundColor Green

# Create virtual environment if it doesn't exist
if (-Not (Test-Path ".\venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

try {
    # Upgrade pip first
    Write-Host "Upgrading pip..." -ForegroundColor Yellow
    python -m pip install --upgrade pip
    
    # Install packages from requirements.txt with PyPI index
    Write-Host "Installing packages from PyPI..." -ForegroundColor Yellow
    pip install pygame requests nltk scikit-learn numpy tqdm
    
    # Install PyTorch with CUDA support separately
    Write-Host "Installing PyTorch with CUDA support..." -ForegroundColor Yellow
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    
    # Install sentence-transformers after PyTorch
    Write-Host "Installing sentence-transformers..." -ForegroundColor Yellow
    pip install sentence-transformers
    
    # Verify CUDA is available
    Write-Host "Checking CUDA availability..." -ForegroundColor Yellow
    python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'CUDA Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
    
    # Verify packages are installed
    Write-Host "Verifying package installation..." -ForegroundColor Yellow
    python -c "import pygame; import torch; import numpy; print('Required packages successfully installed!')"
    
    # Verify Ollama is running
    Write-Host "Checking Ollama status..." -ForegroundColor Yellow
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -Method Get -ErrorAction SilentlyContinue
        Write-Host "Ollama is running. Version: $($response.version)" -ForegroundColor Green
    } catch {
        Write-Host "Warning: Ollama does not appear to be running. Please start Ollama before using the file classifier." -ForegroundColor Red
        Write-Host "Download Ollama from https://ollama.com/ if you haven't installed it yet." -ForegroundColor Yellow
    }
    
    # Ask user if they want to run the application
    $runApp = Read-Host "Do you want to run the application now? (y/n)"
    if ($runApp -eq "y" -or $runApp -eq "Y") {
        Write-Host "Starting File Classifier & Search..." -ForegroundColor Green
        python file_classifier.py
    } else {
        Write-Host "Setup complete! You can run the application with 'python file_classifier.py'" -ForegroundColor Green
    }
} catch {
    Write-Host "An error occurred: $_" -ForegroundColor Red
} finally {
    # Deactivate virtual environment when done
    deactivate
    Write-Host "Environment deactivated." -ForegroundColor Green
}