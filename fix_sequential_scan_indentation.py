"""
Fix specific indentation issues in the sequential_scan_files method
"""
import os
import re

def fix_indentation_issue():
    file_path = "qt_file_classifier_patched_v3.py"
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.readlines()
    
    # Look for the specific indentation issue
    for i in range(len(content)):
        if "def cancel(self):" in content[i] and i+2 < len(content):
            if "def sequential_scan_files(self):" in content[i+2] and content[i+2].startswith("          def"):
                # Fix the indentation
                content[i+2] = "    def sequential_scan_files(self):\n"
                print(f"Fixed indentation on line {i+3}")
                
        # Fix another indentation issue with "# Count files first"
        if "full_exclude_extensions" in content[i] and i+1 < len(content):
            if "# Count files first" in content[i+1] and content[i+1].startswith("          #"):
                content[i+1] = "        # Count files first\n"
                print(f"Fixed indentation on line {i+2}")
        
        # Fix syntax error with missing newline
        if "total_files += 1" in content[i] and "except Exception" in content[i]:
            content[i] = content[i].replace("total_files += 1            except", "total_files += 1\n            except")
            print(f"Fixed syntax error on line {i+1}")
    
    # Write the fixed content back
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(content)
    
    print("Indentation issues fixed.")

if __name__ == "__main__":
    fix_indentation_issue()
