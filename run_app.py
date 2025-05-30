# This script runs the File Classifier application
# It should be executed within the activated virtual environment

import os
import sys
import subprocess

# Check we're running in the virtual environment
venv_path = os.path.dirname(os.path.dirname(sys.executable))
if not os.path.exists(os.path.join(venv_path, 'Scripts', 'activate')):
    print("Error: Not running in the virtual environment!")
    sys.exit(1)

print("Starting File Classifier & Search...")
subprocess.run(["python", "file_classifier.py"])
