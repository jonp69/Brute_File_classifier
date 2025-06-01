"""
Fix specific indentation issues in the sequential_scan_files method
"""

def fix_sequential_scan_file():
    file_path = "qt_file_classifier_patched_v4.py"
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Fix indentation issue with sequential_scan_files method
    # Replace the incorrectly indented method declaration
    content = content.replace(
        'self.is_cancelled = True\n          def sequential_scan_files(self):',
        'self.is_cancelled = True\n    \n    def sequential_scan_files(self):'
    )
    
    # Write the modified content back
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print("Fixed sequential_scan_files indentation")

if __name__ == "__main__":
    fix_sequential_scan_file()
