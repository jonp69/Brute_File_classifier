# Run the File Classifier with PyQt5 interface

Write-Host "Running PyQt5 File Classifier..." -ForegroundColor Green

# Activate virtual environment
& ./venv/Scripts/Activate.ps1

# Run the PyQt5 version
python qt_file_classifier.py

# Wait for keypress before closing
Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
