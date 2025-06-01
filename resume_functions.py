"""
This file contains functions to handle resume functionality for qt_file_classifier_patched_v3.py
"""

def add_resume_functions():
    """Add these functions to qt_file_classifier_patched_v3.py after save_database function"""
    return """
def save_resume_state(drive_paths, scan_mode, processed_count, total_count):
    \"\"\"Save the current scan state for possible resume later\"\"\"
    try:
        resume_data = {
            "drive_paths": drive_paths,
            "scan_mode": scan_mode,
            "processed_files_count": processed_count,
            "total_files_count": total_count,
            "timestamp": time.time()
        }
        
        with open(RESUME_FILE, "w") as f:
            json.dump(resume_data, f)
    except Exception as e:
        print(f"Error saving resume state: {e}")

def load_resume_state():
    \"\"\"Load the previous scan state if available\"\"\"
    try:
        if os.path.exists(RESUME_FILE):
            with open(RESUME_FILE, "r") as f:
                resume_data = json.load(f)
            
            # Check if the resume data is recent (less than 24 hours old)
            if time.time() - resume_data.get("timestamp", 0) < 86400:  # 24 hours in seconds
                return resume_data
    except Exception as e:
        print(f"Error loading resume state: {e}")
    
    return None

def clear_resume_state():
    \"\"\"Clear the resume state file when scan completes\"\"\"
    try:
        if os.path.exists(RESUME_FILE):
            os.remove(RESUME_FILE)
    except Exception as e:
        print(f"Error clearing resume state: {e}")
"""
