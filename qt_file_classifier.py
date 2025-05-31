"""
File Classifier with PyQt5 Interface

This is a PyQt5-based version of the file classifier that eliminates PyGame display surface issues.
"""

import os
import sys
import json
import threading
import time
import re
import queue
import requests
from pathlib import Path
from datetime import datetime
import string
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Global lock for database operations
db_lock = threading.Lock()

# PyQt imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QProgressBar, QMessageBox,
    QScrollArea, QListWidget, QListWidgetItem, QCheckBox, QDialog,
    QFrame, QSplitter, QComboBox, QTextBrowser, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon

# Import the original core functionality 
try:
    # Try to import directly first
    import file_classifier
    from file_classifier import (
        load_config, save_config, load_database, save_database,
        get_file_preview, classify_file_with_llm, search_files_by_extension,
        search_files_by_name, search_files_by_content, search_files_by_vector,
        init_embedding_model, get_available_drives
    )
    
    # Import the file database
    file_database = file_classifier.file_database
    
    print("Successfully imported from file_classifier.py")
    # Use original implementation
    USE_ORIGINAL = True
except Exception as e:
    try:
        # Try alternative import method with explicit path
        import os
        import sys
        # Add current directory to path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.append(current_dir)
        
        # Try import again
        import file_classifier
        from file_classifier import (
            load_config, save_config, load_database, save_database,
            get_file_preview, classify_file_with_llm, search_files_by_extension,
            search_files_by_name, search_files_by_content, search_files_by_vector,
            init_embedding_model, get_available_drives
        )
        
        # Import the file database
        file_database = file_classifier.file_database
        
        print("Successfully imported from file_classifier.py using system path")
        # Use original implementation
        USE_ORIGINAL = True
    except Exception as e:
        # Otherwise implement minimal versions for basic functionality
        print(f"Warning: Could not import from file_classifier.py ({str(e)}), using minimal implementation")
        # Use minimal implementation
        USE_ORIGINAL = False
        file_database = {}
    
    # Configuration
    CONFIG_FILE = "config.json"
    DEFAULT_CONFIG = {
        "llm_provider": "ollama",  # or "lmstudio"
        "ollama_url": "http://localhost:11434/api/generate",
        "lmstudio_url": "http://localhost:1234/v1/completions",
        "model_name": "mistral",
        "exclude_dirs": ["Windows", "Program Files", "Program Files (x86)", "$Recycle.Bin"],
        "exclude_extensions": [".exe", ".dll", ".sys", ".bin", ".dat"],
        "max_file_size_mb": 5,
        "database_path": "file_database.json",
        "embedding_model": "all-MiniLM-L6-v2",
        "offline_mode": False,
        "request_timeout": 60,
        "max_retries": 2
    }
    
    # Global variables
    file_database = {}
    embedding_model = None
    
    def load_config():
        """Load configuration from file or create default"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
                return DEFAULT_CONFIG
        else:
            save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
    
    def save_config(config):
        """Save configuration to file"""
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    
    def load_database():
        """Load file database from disk"""
        global file_database
        config = load_config()
        if os.path.exists(config["database_path"]):
            try:
                with open(config["database_path"], "r", encoding="utf-8") as f:
                    file_database = json.load(f)
            except Exception as e:
                print(f"Error loading database: {e}")
                file_database = {}
        else:
            file_database = {}
      def save_database():
        """Save file database to disk"""
        config = load_config()
        # Create a copy of the database to prevent dictionary changed size during iteration errors
        with threading.Lock():  # Use a lock to ensure thread safety
            db_copy = dict(file_database)
        with open(config["database_path"], "w", encoding="utf-8") as f:
            json.dump(db_copy, f, indent=4, ensure_ascii=False)
    
    def get_available_drives():
        """Get all available drives on the system"""
        if os.name == "nt":  # Windows
            drives = []
            for letter in string.ascii_uppercase:
                if os.path.exists(f"{letter}:\\"):
                    drives.append(f"{letter}:\\")
            return drives
        else:  # Unix/Linux/Mac
            return ["/"]
    
    def get_file_preview(file_path):
        """Get a preview of the file content"""
        try:
            _, ext = os.path.splitext(file_path.lower())
            # Binary files
            if ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar"]:
                return f"[Binary file with extension {ext}]"
                
            # Get text preview, limit to 1500 characters
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(1500)
        except Exception as e:
            return f"[Error reading file: {str(e)}]"
    
    def classify_file_with_llm(file_path, content_preview):
        """Classify and summarize a file using a local LLM"""
        config = load_config()
        
        if len(content_preview.strip()) == 0:
            return {
                "classification": "Unknown",
                "summary": "Empty or unreadable file",
                "keywords": []
            }
        
        # Limit content preview length to reduce LLM load
        max_preview_length = 1000
        
        prompt = f"""Please analyze this file content preview and provide:
    1. Classification (document type, programming language, etc.)
    2. Brief summary (1-2 sentences)
    3. Keywords (comma-separated)

    File path: {file_path}
    Content preview:
    ```
    {content_preview[:max_preview_length]}
    ```

    Respond in JSON format:
    {{
        "classification": "your classification",
        "summary": "your summary",
        "keywords": ["keyword1", "keyword2", "..."]
    }}"""

        try:
            # Get timeout settings from config or use defaults
            timeout = config.get("request_timeout", 60)  # Extended default timeout
            max_retries = config.get("max_retries", 2)   # Number of retries on failure
            
            for retry in range(max_retries + 1):
                try:
                    if config["llm_provider"] == "ollama":
                        # Add options to reduce model memory usage and speed up response
                        response = requests.post(
                            config["ollama_url"],
                            json={
                                "model": config["model_name"],
                                "prompt": prompt,
                                "stream": False,
                                # Add options to optimize for lower memory usage
                                "options": {
                                    "num_ctx": 1024,     # Smaller context window
                                    "num_thread": 4      # Limit number of threads
                                }
                            },
                            timeout=timeout
                        )
                        if response.status_code == 200:
                            result = response.json()
                            # Extract JSON from the response
                            text = result.get("response", "")
                            json_match = re.search(r'\{.*\}', text, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(0)
                                try:
                                    return json.loads(json_str)
                                except:
                                    pass
                        else:
                            print(f"LLM request failed with status code: {response.status_code}")
                    
                    elif config["llm_provider"] == "lmstudio":
                        response = requests.post(
                            config["lmstudio_url"],
                            json={
                                "model": config["model_name"],
                                "prompt": prompt,
                                "max_tokens": 500,
                                "temperature": 0.1
                            },
                            timeout=timeout
                        )
                        if response.status_code == 200:
                            result = response.json()
                            text = result.get("choices", [{}])[0].get("text", "")
                            json_match = re.search(r'\{.*\}', text, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(0)
                                try:
                                    return json.loads(json_str)
                                except:
                                    pass
                    
                    # If we reach this point, either the request failed or JSON parsing failed
                    # Break out of retry loop if this is the last attempt
                    if retry == max_retries:
                        break
                    
                    # Wait before retrying with exponential backoff
                    backoff_time = (retry + 1) * 2
                    time.sleep(backoff_time)
                
                except requests.exceptions.Timeout:
                    if retry == max_retries:
                        # If we've exhausted retries, return an error
                        break
                    # Wait before retrying with exponential backoff
                    backoff_time = (retry + 1) * 2
                    time.sleep(backoff_time)
                    
                except Exception as e:
                    print(f"Error in LLM request: {e}")
                    if retry == max_retries:
                        break
                    time.sleep(retry + 1)
        
        except Exception as e:
            print(f"Error classifying file: {e}")
        
        # Default response if all else fails
        return {
            "classification": "Unknown",
            "summary": "Failed to classify with LLM",
            "keywords": ["error", "classification-failed"]
        }
    
    def init_embedding_model():
        """Initialize the embedding model for vector search"""
        # Placeholder that will be implemented if needed
        pass
        
    def search_files_by_extension(ext):
        """Search files by extension"""
        results = []
        for path, info in file_database.items():
            if path.lower().endswith(ext.lower()):
                results.append((info, 1.0, "extension"))
        return sorted(results, key=lambda x: x[1], reverse=True)
        
    def search_files_by_name(query):
        """Search files by name"""
        query = query.lower()
        results = []
        for path, info in file_database.items():
            name = info.get("name", "").lower()
            if query in name:
                # Score based on position (higher if it appears earlier)
                position = name.find(query)
                score = 1.0 - (position / len(name)) * 0.5
                results.append((info, score, "name"))
        return sorted(results, key=lambda x: x[1], reverse=True)
        
    def search_files_by_content(query):
        """Search files by content match in summary"""
        query = query.lower()
        results = []
        for path, info in file_database.items():
            summary = info.get("summary", "").lower()
            classification = info.get("classification", "").lower()
            keywords = " ".join(info.get("keywords", [])).lower()
            
            # Check for matches in different fields with different weights
            summary_match = query in summary
            class_match = query in classification
            keyword_match = query in keywords
            
            if summary_match or class_match or keyword_match:
                score = 0.0
                # Weight matches
                if summary_match:
                    score += 0.6
                if class_match:
                    score += 0.3
                if keyword_match:
                    score += 0.7
                    
                results.append((info, min(score, 1.0), "content"))
                
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def search_files_by_vector(query):
        """Search files by vector similarity - placeholder"""
        # Return empty list since we're not implementing vector search in minimal version
        return []

# Worker thread for scanning files
class ScannerThread(QThread):
    update_progress = pyqtSignal(str, float, int, int)
    scan_complete = pyqtSignal()
    
    def __init__(self, drive_paths, scan_mode="standard"):
        super().__init__()
        self.drive_paths = drive_paths
        self.scan_mode = scan_mode
        self.is_cancelled = False
        
        # Initialize thread locks and queues for parallel processing
        self.results_lock = threading.Lock()
        self.file_queue = queue.Queue(maxsize=100)
        self.worker_count = 0
        self.scan_complete_flag = False
        
    def run(self):
        """Execute the scan based on the selected mode"""
        if self.scan_mode in ("parallel", "turbo"):
            self.parallel_scan_files()
        else:
            self.sequential_scan_files()
            
    def cancel(self):
        """Cancel the scan operation"""
        self.is_cancelled = True
        
    def sequential_scan_files(self):
        """Sequential scan implementation"""
        config = load_config()
        exclude_dirs = config["exclude_dirs"]
        exclude_extensions = config["exclude_extensions"]
        max_file_size_mb = config["max_file_size_mb"]
        offline_mode = self.scan_mode == "offline" or config.get("offline_mode", False)
        
        # Save offline mode status to config
        if offline_mode != config.get("offline_mode", False):
            config["offline_mode"] = offline_mode
            save_config(config)
        
        # Count files first
        self.update_progress.emit("Counting files...", 0, 0, 0)
        total_files = 0
        
        for drive in self.drive_paths:
            try:
                for root, dirs, files in os.walk(drive):
                    if self.is_cancelled:
                        return
                    
                    # Skip excluded directories
                    dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                    
                    # Count files that meet criteria
                    for file in files:
                        _, ext = os.path.splitext(file.lower())
                        if ext not in exclude_extensions:
                            total_files += 1
            except Exception as e:
                print(f"Error counting files on {drive}: {e}")
        
        # Process files
        processed_files = 0
        for drive in self.drive_paths:
            try:
                self.update_progress.emit(f"Scanning {drive}", processed_files / total_files if total_files > 0 else 0, 
                                         processed_files, total_files)
                
                for root, dirs, files in os.walk(drive):
                    if self.is_cancelled:
                        return
                        
                    # Skip excluded directories
                    dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                    
                    for file in files:
                        if self.is_cancelled:
                            return
                            
                        file_path = os.path.join(root, file)
                        _, ext = os.path.splitext(file.lower())
                        
                        if ext not in exclude_extensions:
                            try:
                                # Skip if already in database and not too old
                                if file_path in file_database:
                                    file_info = file_database[file_path]
                                    last_modified_time = os.path.getmtime(file_path)
                                    last_scan_time = file_info.get("scan_timestamp", 0)
                                    
                                    # Skip if file hasn't been modified since last scan
                                    if last_modified_time <= last_scan_time:
                                        processed_files += 1
                                        self.update_progress.emit(f"Scanning {drive}", 
                                                               processed_files / total_files if total_files > 0 else 0,
                                                               processed_files, total_files)
                                        continue
                                
                                # Check file size
                                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                                if file_size_mb > max_file_size_mb:
                                    file_database[file_path] = {
                                        "path": file_path,
                                        "name": file,
                                        "size_mb": file_size_mb,
                                        "classification": "Large File",
                                        "summary": f"File too large to process ({file_size_mb:.2f} MB)",
                                        "keywords": ["large_file"],
                                        "scan_timestamp": time.time()
                                    }
                                    processed_files += 1
                                    self.update_progress.emit(f"Scanning {drive}", 
                                                           processed_files / total_files if total_files > 0 else 0,
                                                           processed_files, total_files)
                                    continue
                                
                                # Get file preview
                                content_preview = get_file_preview(file_path)
                                
                                # Determine if we're in offline mode
                                if offline_mode:
                                    # Use simple heuristic classification instead of LLM
                                    file_ext = ext[1:] if ext else "unknown"  # Remove the dot
                                    classification = f"{file_ext.upper()} file"
                                    
                                    classification_result = {
                                        "classification": classification,
                                        "summary": f"File indexed in offline mode ({file_size_mb:.2f} MB)",
                                        "keywords": [file_ext if ext else "unknown"]
                                    }
                                else:
                                    # Classify with LLM
                                    classification_result = classify_file_with_llm(file_path, content_preview)
                                
                                # Store in database
                                file_database[file_path] = {
                                    "path": file_path,
                                    "name": file,
                                    "size_mb": file_size_mb,
                                    "classification": classification_result.get("classification", "Unknown"),
                                    "summary": classification_result.get("summary", "No summary available"),
                                    "keywords": classification_result.get("keywords", []),
                                    "scan_timestamp": time.time(),
                                    "offline_indexed": offline_mode
                                }
                                
                                # Periodically save database
                                if processed_files % 100 == 0:
                                    save_database()
                                    
                            except Exception as e:
                                print(f"Error processing file {file_path}: {e}")
                                
                            finally:
                                processed_files += 1
                                self.update_progress.emit(f"Scanning {drive}", 
                                                       processed_files / total_files if total_files > 0 else 0,
                                                       processed_files, total_files)
            except Exception as e:
                print(f"Error scanning drive {drive}: {e}")
        
        # Final save of the database
        save_database()
        self.update_progress.emit("Scan complete", 1.0, processed_files, total_files)
        self.scan_complete.emit()
        
    def process_file_worker(self):
        """Worker thread for parallel processing files"""
        self.worker_count += 1
        offline_mode = self.scan_mode in ("offline", "turbo")
        
        try:
            while True:
                try:
                    # Get a file from the queue with a timeout
                    file_info = self.file_queue.get(timeout=0.5)
                    if file_info is None:  # Sentinel value
                        break
                        
                    file_path = file_info["path"]
                    file_name = file_info["name"]
                    file_size_mb = file_info["size_mb"]
                    
                    # Get file preview
                    content_preview = get_file_preview(file_path)
                    
                    # Determine if we're in offline mode
                    if offline_mode:
                        # Use simple heuristic classification instead of LLM
                        _, ext = os.path.splitext(file_name.lower())
                        file_ext = ext[1:] if ext else "unknown"  # Remove the dot
                        classification = f"{file_ext.upper()} file"
                        
                        classification_result = {
                            "classification": classification,
                            "summary": f"File indexed in offline mode ({file_size_mb:.2f} MB)",
                            "keywords": [file_ext if ext else "unknown"]
                        }
                    else:
                        # Classify with LLM
                        classification_result = classify_file_with_llm(file_path, content_preview)
                    
                    # Store in database (thread-safe)
                    with self.results_lock:
                        file_database[file_path] = {
                            "path": file_path,
                            "name": file_name,
                            "size_mb": file_size_mb,
                            "classification": classification_result.get("classification", "Unknown"),
                            "summary": classification_result.get("summary", "No summary available"),
                            "keywords": classification_result.get("keywords", []),
                            "scan_timestamp": time.time(),
                            "offline_indexed": offline_mode
                        }
                    
                except queue.Empty:
                    # Check if scanning is complete and queue is empty
                    if self.scan_complete_flag and self.file_queue.empty():
                        break
                    # Otherwise just continue waiting
                    continue
                    
                except Exception as e:
                    print(f"Error processing file: {e}")
                    
                finally:
                    # Always mark task as done
                    self.file_queue.task_done()
                    
        finally:
            self.worker_count -= 1
            
    def parallel_scan_files(self):
        """Parallel scan implementation using worker threads"""
        config = load_config()
        exclude_dirs = config["exclude_dirs"]
        exclude_extensions = config["exclude_extensions"]
        max_file_size_mb = config["max_file_size_mb"]
        offline_mode = self.scan_mode in ("offline", "turbo")
        
        # Save offline mode status to config
        if offline_mode != config.get("offline_mode", False):
            config["offline_mode"] = offline_mode
            save_config(config)
            
        # Reset state
        self.scan_complete_flag = False
        
        # Count total files
        self.update_progress.emit("Counting files...", 0, 0, 0)
        total_files = 0
        
        for drive in self.drive_paths:
            try:
                for root, dirs, files in os.walk(drive):
                    if self.is_cancelled:
                        return
                        
                    # Skip excluded directories
                    dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                    
                    # Count files that meet criteria
                    for file in files:
                        _, ext = os.path.splitext(file.lower())
                        if ext not in exclude_extensions:
                            total_files += 1
            except Exception as e:
                print(f"Error counting files on {drive}: {e}")
        
        # Start worker threads
        num_workers = min(os.cpu_count() or 4, 16 if offline_mode else 8)
        print(f"Starting {num_workers} worker threads")
        workers = []
        for _ in range(num_workers):
            worker = threading.Thread(target=self.process_file_worker)
            worker.daemon = True
            worker.start()
            workers.append(worker)
        
        # Process files
        processed_files = 0
        for drive in self.drive_paths:
            try:
                self.update_progress.emit(f"Scanning {drive}", processed_files / total_files if total_files > 0 else 0,
                                        processed_files, total_files)
                
                for root, dirs, files in os.walk(drive):
                    if self.is_cancelled:
                        break
                        
                    # Skip excluded directories
                    dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                    
                    for file in files:
                        if self.is_cancelled:
                            break
                            
                        file_path = os.path.join(root, file)
                        _, ext = os.path.splitext(file.lower())
                        
                        if ext not in exclude_extensions:
                            try:
                                # Skip if already in database and not too old
                                if file_path in file_database:
                                    file_info = file_database[file_path]
                                    last_modified_time = os.path.getmtime(file_path)
                                    last_scan_time = file_info.get("scan_timestamp", 0)
                                    
                                    # Skip if file hasn't been modified since last scan
                                    if last_modified_time <= last_scan_time:
                                        processed_files += 1
                                        self.update_progress.emit(f"Scanning {drive}", 
                                                               processed_files / total_files if total_files > 0 else 0,
                                                               processed_files, total_files)
                                        continue
                                
                                # Check file size
                                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                                if file_size_mb > max_file_size_mb:
                                    with self.results_lock:
                                        file_database[file_path] = {
                                            "path": file_path,
                                            "name": file,
                                            "size_mb": file_size_mb,
                                            "classification": "Large File",
                                            "summary": f"File too large to process ({file_size_mb:.2f} MB)",
                                            "keywords": ["large_file"],
                                            "scan_timestamp": time.time()
                                        }
                                    processed_files += 1
                                    self.update_progress.emit(f"Scanning {drive}", 
                                                           processed_files / total_files if total_files > 0 else 0,
                                                           processed_files, total_files)
                                    continue
                                
                                # Add file to processing queue
                                self.file_queue.put({
                                    "path": file_path,
                                    "name": file,
                                    "size_mb": file_size_mb
                                })
                                
                                # Periodically save database
                                if processed_files % 100 == 0:
                                    save_database()
                                    
                            except Exception as e:
                                print(f"Error processing file {file_path}: {e}")
                                
                            finally:
                                processed_files += 1
                                self.update_progress.emit(f"Scanning {drive}", 
                                                      processed_files / total_files if total_files > 0 else 0,
                                                      processed_files, total_files)
            except Exception as e:
                print(f"Error scanning drive {drive}: {e}")
        
        # Signal that we're done adding files to the queue
        self.scan_complete_flag = True
        
        # Add sentinel values to signal workers to stop
        for _ in range(num_workers):
            self.file_queue.put(None)
            
        # Wait for queue to be processed
        self.update_progress.emit("Finalizing classification...", 0.99, processed_files, total_files)
        
        # Wait for all workers to finish
        for worker in workers:
            worker.join(timeout=0.5)
            
        # Save final database
        save_database()
        self.update_progress.emit("Scan complete", 1.0, processed_files, total_files)
        self.scan_complete.emit()


# Dialog for drive selection
class DriveSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Drives to Scan")
        self.setMinimumSize(400, 300)
        self.selected_drives = []
        
        # Layout
        layout = QVBoxLayout()
        
        # Label
        title_label = QLabel("Select drives to scan:")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)
        
        # Drive checkboxes
        self.drive_checkboxes = []
        drives = get_available_drives()
        
        for drive in drives:
            drive_info = f"{drive}"
            try:
                # Get drive type and free space on Windows
                if os.name == 'nt':
                    import ctypes
                    free_bytes = ctypes.c_ulonglong(0)
                    total_bytes = ctypes.c_ulonglong(0)
                    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                        ctypes.c_wchar_p(drive), None, 
                        ctypes.pointer(total_bytes), 
                        ctypes.pointer(free_bytes)
                    )
                    free_gb = free_bytes.value / (1024**3)
                    total_gb = total_bytes.value / (1024**3)
                    drive_info = f"{drive} ({free_gb:.1f} GB free / {total_gb:.1f} GB)"
            except:
                pass
                
            checkbox = QCheckBox(drive_info)
            self.drive_checkboxes.append((checkbox, drive))
            layout.addWidget(checkbox)
            
        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def get_selected_drives(self):
        """Get the list of selected drives"""
        return [drive for checkbox, drive in self.drive_checkboxes if checkbox.isChecked()]


# Main application window
class FileClassifierApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Classifier & Search")
        self.setMinimumSize(1000, 600)
        self.scanning_active = False
        self.current_page = 0
        self.search_results = []
        self.results_per_page = 10
        self.selected_mode = "standard"  # Default mode
        
        self.init_ui()
        
        # Load database
        load_database()
        
        # Initialize embedding model in background
        threading.Thread(target=init_embedding_model, daemon=True).start()
        
        # Timer for auto-save
        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.auto_save)
        self.save_timer.start(60000)  # Save every minute
        
    def init_ui(self):
        """Initialize the user interface"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Title
        title_label = QLabel("File Classifier & Search")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        main_layout.addWidget(title_label)
        
        # Search bar and buttons layout
        search_layout = QHBoxLayout()
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search files...")
        self.search_input.setMinimumHeight(40)
        self.search_input.returnPressed.connect(self.on_search)
        search_layout.addWidget(self.search_input, 4)
        
        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.on_search)
        search_layout.addWidget(self.search_button, 1)
        
        main_layout.addLayout(search_layout)
        
        # Controls layout (left side - results, right side - buttons)
        controls_layout = QHBoxLayout()
        
        # Results area
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        
        # Database stats
        self.stats_label = QLabel(f"Database: {len(file_database)} files indexed")
        results_layout.addWidget(self.stats_label)
        
        # Progress bar and status
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar, 4)
        
        self.task_label = QLabel("")
        self.task_label.setVisible(False)
        progress_layout.addWidget(self.task_label, 3)
        
        results_layout.addLayout(progress_layout)
        
        # Results header
        self.results_header = QLabel("Search Results: 0")
        self.results_header.setFont(QFont("Arial", 14, QFont.Bold))
        results_layout.addWidget(self.results_header)
        
        # Results scroll area
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_scroll.setWidget(self.results_container)
        results_layout.addWidget(self.results_scroll)
        
        # Pagination layout
        pagination_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.on_prev_page)
        self.page_label = QLabel("Page 0/0")
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.on_next_page)
        
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_button)
        pagination_layout.addStretch()
        
        results_layout.addLayout(pagination_layout)
        
        # Control buttons (right side)
        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout(buttons_widget)
        
        # Scan button
        self.scan_button = QPushButton("Scan Drives")
        self.scan_button.setMinimumHeight(40)
        self.scan_button.clicked.connect(self.on_scan)
        buttons_layout.addWidget(self.scan_button)
        
        # Stop button
        self.stop_button = QPushButton("Stop Scan")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.clicked.connect(self.on_stop_scan)
        self.stop_button.setEnabled(False)
        buttons_layout.addWidget(self.stop_button)
        
        # Mode selection
        mode_group_box = QFrame()
        mode_group_box.setFrameShape(QFrame.StyledPanel)
        mode_layout = QVBoxLayout(mode_group_box)
        
        mode_label = QLabel("Scan Mode:")
        mode_label.setFont(QFont("Arial", 12))
        mode_layout.addWidget(mode_label)
        
        # Mode buttons
        self.mode_buttons = []
        
        # Standard mode
        self.standard_button = QPushButton("Standard Mode")
        self.standard_button.setCheckable(True)
        self.standard_button.setChecked(True)
        self.standard_button.clicked.connect(lambda: self.on_mode_change("standard"))
        mode_layout.addWidget(self.standard_button)
        self.mode_buttons.append((self.standard_button, "standard"))
        
        # Parallel mode
        self.parallel_button = QPushButton("Parallel Mode")
        self.parallel_button.setCheckable(True)
        self.parallel_button.clicked.connect(lambda: self.on_mode_change("parallel"))
        mode_layout.addWidget(self.parallel_button)
        self.mode_buttons.append((self.parallel_button, "parallel"))
        
        # Offline mode
        self.offline_button = QPushButton("Offline Mode")
        self.offline_button.setCheckable(True)
        self.offline_button.clicked.connect(lambda: self.on_mode_change("offline"))
        mode_layout.addWidget(self.offline_button)
        self.mode_buttons.append((self.offline_button, "offline"))
        
        # Turbo mode
        self.turbo_button = QPushButton("Turbo Mode")
        self.turbo_button.setCheckable(True)
        self.turbo_button.clicked.connect(lambda: self.on_mode_change("turbo"))
        mode_layout.addWidget(self.turbo_button)
        self.mode_buttons.append((self.turbo_button, "turbo"))
        
        buttons_layout.addWidget(mode_group_box)
        buttons_layout.addStretch()
        
        # Add left and right parts to the controls layout
        controls_layout.addWidget(results_widget, 3)  # Results take more space
        controls_layout.addWidget(buttons_widget, 1)  # Buttons take less space
        
        main_layout.addLayout(controls_layout)
        
    def auto_save(self):
        """Auto save database periodically"""
        if file_database:
            save_database()
            
    def on_mode_change(self, mode):
        """Handle mode button clicks"""
        self.selected_mode = mode
        
        # Update button states
        for button, btn_mode in self.mode_buttons:
            button.setChecked(btn_mode == mode)
            
    def on_search(self):
        """Handle search button click"""
        query = self.search_input.text().strip()
        if not query:
            return
            
        self.search_results = []
        self.current_page = 0
        
        # Determine search type
        if query.startswith(".") and len(query) > 1:
            # Extension search
            self.search_results = search_files_by_extension(query)
        else:
            # Name search
            name_results = search_files_by_name(query)
            
            # Content search
            content_results = search_files_by_content(query)
            
            # Vector search (if available)
            vector_results = search_files_by_vector(query)
            
            # Combine and deduplicate results
            seen_paths = set()
            for result in name_results + content_results + vector_results:
                path = result[0].get("path", "")
                if path and path not in seen_paths:
                    self.search_results.append(result)
                    seen_paths.add(path)
        
        # Update results display
        self.update_results_display()
        
    def update_results_display(self):
        """Update the search results display"""
        # Clear previous results
        for i in reversed(range(self.results_layout.count())):
            widget = self.results_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Update header
        self.results_header.setText(f"Search Results: {len(self.search_results)}")
        
        # Calculate pagination
        total_pages = (len(self.search_results) - 1) // self.results_per_page + 1 if self.search_results else 0
        self.page_label.setText(f"Page {self.current_page + 1}/{total_pages}")
        
        # Enable/disable pagination buttons
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < total_pages - 1)
        
        # Display results for current page
        if self.search_results:
            start_idx = self.current_page * self.results_per_page
            end_idx = min(start_idx + self.results_per_page, len(self.search_results))
            
            for i in range(start_idx, end_idx):
                item, score, search_type = self.search_results[i]
                path = item.get("path", "")
                name = item.get("name", "Unknown")
                classification = item.get("classification", "Unknown")
                summary = item.get("summary", "No summary available")
                
                # Create result item widget
                result_frame = QFrame()
                result_frame.setFrameShape(QFrame.StyledPanel)
                result_frame.setLineWidth(1)
                result_frame.setMidLineWidth(1)
                
                item_layout = QVBoxLayout(result_frame)
                
                # Header with name and classification
                header_layout = QHBoxLayout()
                header_text = QLabel(f"{name} - {classification}")
                header_text.setFont(QFont("Arial", 12, QFont.Bold))
                header_layout.addWidget(header_text)
                
                # Score
                score_text = QLabel(f"{search_type.capitalize()}: {score:.2f}")
                score_text.setAlignment(Qt.AlignRight)
                header_layout.addWidget(score_text)
                
                item_layout.addLayout(header_layout)
                
                # Path
                path_text = QLabel(path)
                path_text.setWordWrap(True)
                item_layout.addWidget(path_text)
                
                # Summary
                summary_text = QLabel(summary[:200] + "..." if len(summary) > 200 else summary)
                summary_text.setWordWrap(True)
                item_layout.addWidget(summary_text)
                
                # Buttons for actions
                btn_layout = QHBoxLayout()
                
                open_file_btn = QPushButton("Open File")
                open_file_btn.clicked.connect(lambda checked, p=path: self.open_file(p))
                
                open_folder_btn = QPushButton("Open Folder")
                open_folder_btn.clicked.connect(lambda checked, p=path: self.open_folder(p))
                
                btn_layout.addStretch()
                btn_layout.addWidget(open_file_btn)
                btn_layout.addWidget(open_folder_btn)
                
                item_layout.addLayout(btn_layout)
                
                # Add to results layout
                self.results_layout.addWidget(result_frame)
        
        # Add stretch at the end
        self.results_layout.addStretch()
        
    def open_file(self, path):
        """Open a file using the default application"""
        if os.path.exists(path):
            if os.name == "nt":  # Windows
                os.startfile(path)
            elif os.name == "posix":  # macOS or Linux
                subprocess.call(("xdg-open", path) if sys.platform == "linux" else ("open", path))
                
    def open_folder(self, path):
        """Open containing folder"""
        if os.path.exists(path):
            folder = os.path.dirname(path)
            if os.name == "nt":  # Windows
                os.startfile(folder)
            elif os.name == "posix":  # macOS or Linux
                subprocess.call(("xdg-open", folder) if sys.platform == "linux" else ("open", folder))
                
    def on_prev_page(self):
        """Go to previous page of results"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_results_display()
            
    def on_next_page(self):
        """Go to next page of results"""
        total_pages = (len(self.search_results) - 1) // self.results_per_page + 1
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_results_display()
            
    def on_scan(self):
        """Handle scan button click"""
        if self.scanning_active:
            return
            
        # Show drive selection dialog
        dialog = DriveSelectionDialog(self)
        if dialog.exec_():
            selected_drives = dialog.get_selected_drives()
            
            if selected_drives:
                self.scanning_active = True
                self.scan_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                
                # Update UI for scanning
                self.progress_bar.setVisible(True)
                self.task_label.setVisible(True)
                
                # Start scanner thread
                mode_desc = self.selected_mode.capitalize()
                self.task_label.setText(f"Starting {mode_desc} scan...")
                
                self.scanner_thread = ScannerThread(selected_drives, self.selected_mode)
                self.scanner_thread.update_progress.connect(self.update_scan_progress)
                self.scanner_thread.scan_complete.connect(self.on_scan_complete)
                self.scanner_thread.start()
                
    def on_stop_scan(self):
        """Handle stop scan button click"""
        if self.scanning_active and hasattr(self, "scanner_thread"):
            self.scanner_thread.cancel()
            self.task_label.setText("Stopping scan...")
            
    def update_scan_progress(self, task, progress, processed, total):
        """Update the progress display"""
        self.task_label.setText(f"{task} - {processed}/{total} files")
        self.progress_bar.setValue(int(progress * 100))
        
        # Update database stats periodically
        self.stats_label.setText(f"Database: {len(file_database)} files indexed")
        
    def on_scan_complete(self):
        """Handle scan completion"""
        self.scanning_active = False
        self.scan_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # Final UI updates
        self.progress_bar.setValue(100)
        self.stats_label.setText(f"Database: {len(file_database)} files indexed")
        
        # Hide progress after a delay
        QTimer.singleShot(3000, lambda: self.progress_bar.setVisible(False))
        QTimer.singleShot(3000, lambda: self.task_label.setVisible(False))
        
    def closeEvent(self, event):
        """Handle window close event"""
        # Save database when closing
        if file_database:
            save_database()
        event.accept()


if __name__ == "__main__":
    # Apply any required patches from run_file_classifier.py
    try:
        from run_file_classifier import patch_llm_timeout_handler
        patch_llm_timeout_handler()
    except ImportError:
        print("Warning: Could not apply patches from run_file_classifier.py")
        
    # Create and run the application
    app = QApplication(sys.argv)
    
    # Set style
    app.setStyle("Fusion")
    
    # Create and show the main window
    window = FileClassifierApp()
    window.show()
    
    sys.exit(app.exec_())
