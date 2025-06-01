"""
Fix indentation issues and add resume functionality to qt_file_classifier_patched_v3.py
"""
import os
import re

def fix_file():
    file_path = "qt_file_classifier_patched_v3.py"
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Fix the indentation issues in sequential_scan_files method
    content = content.replace("""    def cancel(self):
        """Cancel the scan operation"""
        self.is_cancelled = True
          def sequential_scan_files(self):""", 
    """    def cancel(self):
        """Cancel the scan operation"""
        self.is_cancelled = True
        
    def sequential_scan_files(self):""")
    
    # Fix the indentation in the following part
    content = content.replace("""        # Full list of excluded extensions
        full_exclude_extensions = exclude_extensions + ADDITIONAL_EXCLUDE_EXTENSIONS
          # Count files first""",
    """        # Full list of excluded extensions
        full_exclude_extensions = exclude_extensions + ADDITIONAL_EXCLUDE_EXTENSIONS
        
        # Count files first""")
    
    # Fix the syntax error with missing newline
    content = content.replace("""                            total_files += 1            except Exception as e:""",
    """                            total_files += 1
            except Exception as e:""")
    
    # Add save_resume_state call in the sequential_scan_files method after the progress update
    content = content.replace("""                                self.update_progress.emit(f"Scanning {drive}", 
                                                       processed_files / total_files if total_files > 0 else 0,
                                                       processed_files, total_files)""",
    """                                # Update progress
                                self.update_progress.emit(f"Scanning {drive}", 
                                                       processed_files / total_files if total_files > 0 else 0,
                                                       processed_files, total_files)
                                
                                # Save resume state periodically
                                if processed_files % 200 == 0:
                                    save_resume_state(self.drive_paths, self.scan_mode, processed_files, total_files)""")
    
    # Add resume functions if they don't already exist
    if "def save_resume_state" not in content:
        # Find the position right after save_database function
        save_db_end = content.find("def save_database():") 
        save_db_end = content.find("\n\n", save_db_end) # Find the end of function
        
        if save_db_end > 0:
            # Get resume functions from the other file
            with open("resume_functions.py", "r") as rf:
                resume_content = rf.read()
            
            resume_functions = resume_content.split('return """')[1].split('"""')[0]
            
            # Insert resume functions after save_database
            content = content[:save_db_end] + "\n" + resume_functions + content[save_db_end:]
    
    # Add clear_resume_state to the scan complete handler
    content = content.replace("""        # Final save of the database
        save_database()
        print_file_stats()  # Print final stats
        self.update_progress.emit("Scan complete", 1.0, processed_files, total_files)
        self.scan_complete.emit()""",
    """        # Final save of the database
        save_database()
        print_file_stats()  # Print final stats
        self.update_progress.emit("Scan complete", 1.0, processed_files, total_files)
        # Clear resume state on successful completion
        clear_resume_state()
        self.scan_complete.emit()""")
    
    # Write the fixed content back
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print("File has been fixed with proper indentation and resume functionality.")

if __name__ == "__main__":
    fix_file()
