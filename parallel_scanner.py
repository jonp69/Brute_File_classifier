"""
Parallel file scanning implementation for the File Classifier.
This module provides concurrent file scanning and classification.
"""

import os
import time
import threading
import queue
import json
import re
from concurrent.futures import ThreadPoolExecutor

# Queue for files waiting to be processed by LLM
file_queue = queue.Queue(maxsize=100)  # Limit queue size to prevent memory issues
results_lock = threading.Lock()  # For thread-safe database updates

# Status tracking
scan_complete = False
worker_count = 0

def process_file(file_path, file_name, file_size_mb, content_preview, classify_func, config):
    """Process a single file with LLM classification"""
    try:
        # Check if in offline mode
        if config.get("offline_mode", False):
            # Use simple heuristic classification instead of LLM
            _, ext = os.path.splitext(file_name.lower())
            if ext:
                file_type = ext[1:]  # Remove the dot
                classification = f"{file_type.upper()} file"
            else:
                classification = "Unknown file type"
                
            classification_result = {
                "classification": classification,
                "summary": f"File indexed in offline mode ({file_size_mb:.2f} MB)",
                "keywords": [file_type if ext else "unknown"]
            }
        else:
            # Classify with LLM
            classification_result = classify_func(file_path, content_preview)
        
        return {
            "path": file_path,
            "name": file_name,
            "size_mb": file_size_mb,
            "classification": classification_result.get("classification", "Unknown"),
            "summary": classification_result.get("summary", "No summary available"),
            "keywords": classification_result.get("keywords", []),
            "scan_timestamp": time.time(),
            "offline_indexed": config.get("offline_mode", False)
        }
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return {
            "path": file_path,
            "name": file_name,
            "size_mb": file_size_mb,
            "classification": "Error",
            "summary": f"Error during processing: {str(e)}",
            "keywords": ["error", "processing_failed"],
            "scan_timestamp": time.time()
        }

def llm_worker(classify_func, file_database, save_database_func, config):
    """Worker thread that processes files from the queue"""
    global scan_complete, worker_count
    
    worker_count += 1
    files_processed = 0
    
    try:
        while True:
            try:
                # Get a file from the queue with timeout
                # This allows the thread to check scan_complete periodically
                item = file_queue.get(timeout=2)
                if item is None:  # Sentinel value indicating we should stop
                    break
                    
                file_path, file_name, file_size_mb, content_preview = item
                
                # Process the file
                result = process_file(file_path, file_name, file_size_mb, 
                                     content_preview, classify_func, config)
                
                # Update the database thread-safely
                with results_lock:
                    file_database[file_path] = result
                    files_processed += 1
                    
                    # Periodically save the database
                    if files_processed % 20 == 0:  # Save more frequently
                        save_database_func()
                
            except queue.Empty:
                if scan_complete:  # If scanning is done and queue is empty, we're done
                    break
                # Otherwise, continue waiting for more files
                continue
    finally:
        worker_count -= 1
        # If this is the last worker, save the database
        if worker_count == 0 and scan_complete:
            save_database_func()

def parallel_scan_files(drive_paths, file_database, classify_file_with_llm, 
                       get_file_preview, save_database, load_config,
                       update_progress_callback=None):
    """
    Scan files on the specified drives using parallel processing
    
    Args:
        drive_paths: List of drive paths to scan
        file_database: The file database dictionary
        classify_file_with_llm: Function to classify a file
        get_file_preview: Function to get preview of a file
        save_database: Function to save the database
        load_config: Function to load configuration
        update_progress_callback: Function to call with progress updates (processed_files, total_files)
    """
    global scan_complete, worker_count
    
    config = load_config()
    exclude_dirs = config["exclude_dirs"]
    exclude_extensions = config["exclude_extensions"]
    max_file_size_mb = config["max_file_size_mb"]
    
    # Determine number of workers based on available CPU cores
    num_workers = min(os.cpu_count() or 4, 8)  # Use at most 8 workers
    
    # If we're in offline mode, we can use more workers since we're not waiting on LLM
    if config.get("offline_mode", False):
        num_workers = min(os.cpu_count() or 4, 16)
    
    scan_complete = False
    worker_count = 0
    processing_threads = []
    
    # First count total files (this part stays sequential)
    total_files = 0
    for drive in drive_paths:
        try:
            for root, dirs, files in os.walk(drive):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                
                # Count files that meet our criteria
                for file in files:
                    _, ext = os.path.splitext(file.lower())
                    if ext not in exclude_extensions:
                        total_files += 1
        except Exception as e:
            print(f"Error counting files on {drive}: {e}")
    
    # Start worker threads for LLM processing
    for _ in range(num_workers):
        thread = threading.Thread(
            target=llm_worker,
            args=(classify_file_with_llm, file_database, save_database, config),
            daemon=True
        )
        thread.start()
        processing_threads.append(thread)
    
    # Now scan files and add them to the queue
    processed_files = 0
    try:
        for drive in drive_paths:
            for root, dirs, files in os.walk(drive):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                
                for file in files:
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
                                    if update_progress_callback:
                                        update_progress_callback(processed_files, total_files)
                                    continue
                            
                            # Check file size
                            try:
                                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                            except:
                                # If can't get file size, skip this file
                                processed_files += 1
                                if update_progress_callback:
                                    update_progress_callback(processed_files, total_files)
                                continue
                                
                            if file_size_mb > max_file_size_mb:
                                # Large files are processed immediately (no LLM needed)
                                with results_lock:
                                    file_database[file_path] = {
                                        "path": file_path,
                                        "name": file,
                                        "size_mb": file_size_mb,
                                        "classification": "Large File",
                                        "summary": f"File too large to process ({file_size_mb:.2f} MB)",
                                        "keywords": ["large_file"],
                                        "scan_timestamp": time.time()
                                    }
                            else:
                                # Get file preview
                                content_preview = get_file_preview(file_path, max_file_size_mb)
                                
                                # Add to queue for LLM processing
                                # If queue is full, this will block until space is available
                                file_queue.put((file_path, file, file_size_mb, content_preview))
                                
                        except Exception as e:
                            print(f"Error queueing file {file_path}: {e}")
                            
                        finally:
                            processed_files += 1
                            if update_progress_callback:
                                update_progress_callback(processed_files, total_files)
    finally:
        # Mark scan as complete and wait for processors to finish
        scan_complete = True
        
        # Put sentinel values to signal threads to exit
        for _ in range(num_workers):
            try:
                file_queue.put(None, timeout=1)
            except queue.Full:
                pass
        
        # Wait for all worker threads to complete
        for thread in processing_threads:
            thread.join(timeout=2)  # Don't wait forever
    
    # Final save
    save_database()
    return total_files, processed_files
