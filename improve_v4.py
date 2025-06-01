"""
Improve qt_file_classifier_patched_v4.py with specific edits
- Update global processed_files_count in sequential_scan_files
- Ensure clear_resume_state is called at the end of scan
"""
import re

def improve_v4_file():
    file_path = "qt_file_classifier_patched_v4.py"
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find the section where we need to update processed_files_count in sequential_scan_files
    pattern1 = r"finally:\s*processed_files \+= 1\s*self\.update_progress\.emit\(f\"Scanning \{drive\}\",\s*processed_files / total_files if total_files > 0 else 0,\s*processed_files, total_files\)"
    replacement1 = """finally:
                                processed_files += 1
                                global processed_files_count
                                processed_files_count = processed_files  # Update global count for time estimation
                                
                                # Update progress display
                                self.update_progress.emit(f"Scanning {drive}", 
                                                       processed_files / total_files if total_files > 0 else 0,
                                                       processed_files, total_files)"""
    
    # Replace the pattern
    modified_content = re.sub(pattern1, replacement1, content)
    
    # Add clear_resume_state() at the end of scan
    pattern2 = r"# Final save of the database\s*save_database\(\)\s*print_file_stats\(\)\s*# Print final stats\s*self\.update_progress\.emit\(\"Scan complete\", 1\.0, processed_files, total_files\)"
    replacement2 = """# Final save of the database
        save_database()
        print_file_stats()  # Print final stats
        self.update_progress.emit("Scan complete", 1.0, processed_files, total_files)
        # Clear resume state on successful completion
        clear_resume_state()"""
    
    # Replace the pattern
    modified_content = re.sub(pattern2, replacement2, modified_content)
    
    # Write the modified content back
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(modified_content)
    
    print("Improved v4 file with time estimation and resume functionality")

if __name__ == "__main__":
    improve_v4_file()
