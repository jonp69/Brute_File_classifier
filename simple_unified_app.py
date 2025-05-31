"""
Unified File Classifier
This version incorporates all scanning modes into a single interface
"""
import os
import sys
import pygame
import json
import threading
import time
import re
import queue
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Import the original file_classifier module
from file_classifier import *

# Global variables for parallel processing
worker_count = 0
scan_complete = False
file_queue = queue.Queue(maxsize=100)
results_lock = threading.Lock()

def process_file_worker(file_database, classify_func, get_preview_func):
    """Worker thread that processes files from the queue"""
    global worker_count
    
    worker_count += 1
    try:
        while True:
            try:
                # Get a file from the queue with a timeout
                file_info = file_queue.get(timeout=0.5)
                if file_info is None:  # Sentinel value indicating work is done
                    break
                    
                file_path = file_info["path"]
                file_name = file_info["name"]
                file_size_mb = file_info["size_mb"]
                
                # Get file preview
                content_preview = get_preview_func(file_path)
                
                # Determine if we're in offline mode
                config = load_config()
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
                
                # Store in database (thread-safe)
                with results_lock:
                    file_database[file_path] = {
                        "path": file_path,
                        "name": file_name,
                        "size_mb": file_size_mb,
                        "classification": classification_result.get("classification", "Unknown"),
                        "summary": classification_result.get("summary", "No summary available"),
                        "keywords": classification_result.get("keywords", []),
                        "scan_timestamp": time.time(),
                        "offline_indexed": config.get("offline_mode", False)
                    }
                
            except queue.Empty:
                # Check if scanning is complete and queue is empty
                if scan_complete and file_queue.empty():
                    break
                # Otherwise just continue waiting
                continue
                
            except Exception as e:
                print(f"Error processing file: {e}")
                
            finally:
                # Always mark task as done
                file_queue.task_done()
                
    finally:
        worker_count -= 1

def parallel_scan_files(drive_paths):
    """Scan files using parallel processing"""
    global file_queue, worker_count, scan_complete
    global file_database, scanning_active, current_task, progress, total_files, processed_files
    
    config = load_config()
    exclude_dirs = config["exclude_dirs"]
    exclude_extensions = config["exclude_extensions"]
    max_file_size_mb = config["max_file_size_mb"]
    
    # Reset states
    scanning_active = True
    current_task = "Counting files..."
    progress = 0
    scan_complete = False
    
    # First count total files to process
    total_files = 0
    for drive in drive_paths:
        try:
            for root, dirs, files in os.walk(drive):
                if not scanning_active:
                    return
                    
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                
                # Count files that meet our criteria
                for file in files:
                    _, ext = os.path.splitext(file.lower())
                    if ext not in exclude_extensions:
                        total_files += 1
        except Exception as e:
            print(f"Error counting files on {drive}: {e}")
    
    # Start worker threads
    # Determine number of workers based on available CPU cores
    num_workers = min(os.cpu_count() or 4, 8)  # Use at most 8 workers
    
    # If we're in offline mode, we can use more workers
    if config.get("offline_mode", False):
        num_workers = min(os.cpu_count() or 4, 16)  # Use more workers in offline mode
        
    print(f"Starting {num_workers} worker threads")
    workers = []
    for _ in range(num_workers):
        worker = threading.Thread(
            target=process_file_worker,
            args=(file_database, classify_file_with_llm, get_file_preview),
            daemon=True
        )
        worker.start()
        workers.append(worker)
    
    # Process files
    processed_files = 0
    for drive in drive_paths:
        try:
            current_task = f"Scanning {drive}"
            
            for root, dirs, files in os.walk(drive):
                if not scanning_active:
                    break
                    
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                
                for file in files:
                    if not scanning_active:
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
                                    progress = processed_files / total_files if total_files > 0 else 0
                                    continue
                            
                            # Check file size
                            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                            if file_size_mb > max_file_size_mb:
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
                                processed_files += 1
                                progress = processed_files / total_files if total_files > 0 else 0
                                continue
                            
                            # Add file to processing queue
                            file_queue.put({
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
                            progress = processed_files / total_files if total_files > 0 else 0
                            
                # Sleep a tiny bit to allow UI to remain responsive
                time.sleep(0.001)
        except Exception as e:
            print(f"Error scanning drive {drive}: {e}")
    
    # Signal that we're done adding files to the queue
    scan_complete = True
    
    # Wait for queue to be processed
    current_task = "Finalizing classification..."
    try:
        # Add sentinel values to signal workers to stop
        for _ in range(num_workers):
            file_queue.put(None)
            
        # Wait for all workers to finish
        for worker in workers:
            worker.join(timeout=0.5)  # Non-blocking join
    except:
        pass
        
    # Save final database
    save_database()
    scanning_active = False
    current_task = "Scan complete"

def unified_scan(drive_paths, scan_mode="standard"):
    """
    Unified scanning function that supports different scanning modes
    
    Args:
        drive_paths: List of drive paths to scan
        scan_mode: Scanning mode to use:
            - "standard": Sequential scanning with LLM classification
            - "parallel": Parallel scanning with LLM classification
            - "offline": Sequential scanning without LLM classification
            - "turbo": Parallel scanning without LLM classification
    
    Returns:
        Thread object for the scanning thread
    """
    # Get current configuration
    config = load_config()
    original_offline_mode = config.get("offline_mode", False)
    
    # Update config based on mode
    if scan_mode in ("offline", "turbo"):
        config["offline_mode"] = True
        save_config(config)
    
    try:
        # Choose scanning function based on mode
        if scan_mode in ("parallel", "turbo"):
            scan_function = parallel_scan_files
        else:
            scan_function = scan_files
            
        # Start scanning in a background thread
        scan_thread = threading.Thread(
            target=scan_function,
            args=(drive_paths,),
            daemon=True
        )
        scan_thread.start()
        
        # Start a thread to restore the original config after scan completes
        if scan_mode in ("offline", "turbo"):
            def restore_config():
                # Wait for scan to complete
                while scanning_active:
                    time.sleep(1)
                    
                # Restore original config
                config = load_config()
                config["offline_mode"] = original_offline_mode
                save_config(config)
                
            restore_thread = threading.Thread(target=restore_config, daemon=True)
            restore_thread.start()
            
        return scan_thread
        
    except Exception as e:
        print(f"Error starting scan: {e}")
        return None

def enhanced_main():
    """Enhanced version of the main function with unified scan mode selection"""
    try:
        # Initialize pygame with proper error handling
        pygame.init()
        screen_info = pygame.display.Info()
        width, height = min(1280, screen_info.current_w - 50), min(720, screen_info.current_h - 50)
        screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        pygame.display.set_caption("File Classifier & Search")
        
        # Load fonts
        pygame.font.init()
        title_font = pygame.font.SysFont("Arial", 24, bold=True)
        heading_font = pygame.font.SysFont("Arial", 18, bold=True)
        normal_font = pygame.font.SysFont("Arial", 16)
        small_font = pygame.font.SysFont("Arial", 14)
        
        # Initialize components
        search_input = Input((20, 70, width - 200, 40), normal_font, "Search files...")
        
        # Load database
        load_database()
        
        # Initialize embedding model in background
        threading.Thread(target=init_embedding_model, daemon=True).start()
        
        # Main UI elements
        scan_button = pygame.Rect(width - 170, 70, 150, 40)
        stop_button = pygame.Rect(width - 170, 120, 150, 40)
        
        # Mode selection elements
        mode_buttons = [
            {"rect": pygame.Rect(width - 170, 180, 150, 35), "text": "Standard Mode", "mode": "standard", "color": BLUE},
            {"rect": pygame.Rect(width - 170, 220, 150, 35), "text": "Parallel Mode", "mode": "parallel", "color": GREEN},
            {"rect": pygame.Rect(width - 170, 260, 150, 35), "text": "Offline Mode", "mode": "offline", "color": YELLOW},
            {"rect": pygame.Rect(width - 170, 300, 150, 35), "text": "Turbo Mode", "mode": "turbo", "color": RED}
        ]
        
        # Default scan mode
        selected_mode = "standard"
        
        # Pagination buttons
        prev_button = pygame.Rect(width//2 - 100, height - 50, 80, 30)
        next_button = pygame.Rect(width//2 + 20, height - 50, 80, 30)
        
        # Track mouse for hover effects
        mouse_pos = (0, 0)
        
        # Main loop
        global scanning_active, current_task, progress, search_results, current_page
        running = True
        clock = pygame.time.Clock()
        
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    
                elif event.type == pygame.VIDEORESIZE:
                    try:
                        width, height = event.w, event.h
                        screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                        # Update UI positions
                        search_input.rect = pygame.Rect(20, 70, width - 200, 40)
                        scan_button = pygame.Rect(width - 170, 70, 150, 40)
                        stop_button = pygame.Rect(width - 170, 120, 150, 40)
                        
                        # Update mode button positions
                        for i, btn in enumerate(mode_buttons):
                            btn["rect"] = pygame.Rect(width - 170, 180 + i * 40, 150, 35)
                        
                        prev_button = pygame.Rect(width//2 - 100, height - 50, 80, 30)
                        next_button = pygame.Rect(width//2 + 20, height - 50, 80, 30)
                    except pygame.error as e:
                        print(f"Error handling resize: {e}")
                        continue
                      elif event.type == pygame.MOUSEMOTION:
                    mouse_pos = event.pos
                    
                elif event.type == pygame.MOUSEBUTTONDOWN:
                if scan_button.collidepoint(mouse_pos) and not scanning_active:
                    # Let user select drives to scan
                    selected_drives = select_drives_dialog()
                    
                    if selected_drives:  # Only scan if drives were selected
                        # Extract the mode description for display
                        mode_desc = next((btn["text"] for btn in mode_buttons if btn["mode"] == selected_mode), "Standard Mode")
                        current_task = f"Starting scan ({mode_desc})..."
                        
                        # Use the unified scanner with the selected mode
                        unified_scan(selected_drives, scan_mode=selected_mode)
                        
                elif stop_button.collidepoint(mouse_pos) and scanning_active:
                    scanning_active = False
                    current_task = "Scan stopped"
                    
                # Check mode button clicks
                for btn in mode_buttons:
                    if btn["rect"].collidepoint(mouse_pos) and not scanning_active:
                        selected_mode = btn["mode"]
                
                # Handle pagination
                if prev_button.collidepoint(mouse_pos) and current_page > 0:
                    current_page -= 1
                    
                elif next_button.collidepoint(mouse_pos) and (current_page + 1) * results_per_page < len(search_results):
                    current_page += 1
                    
                # Handle result clicks (open file or folder)
                if len(search_results) > 0:
                    start_idx = current_page * results_per_page
                    end_idx = min(start_idx + results_per_page, len(search_results))
                    
                    result_y = 210
                    for i in range(start_idx, end_idx):
                        item = search_results[i][0]
                        path = item.get("path", "")
                        
                        # Calculate result box height
                        name = item.get("name", "Unknown")
                        classification = item.get("classification", "Unknown")
                        summary = item.get("summary", "No summary available")[:150]
                        
                        # Calculate required height for all components
                        name_text_height = heading_font.get_linesize()
                        path_text_height = small_font.get_linesize()
                        
                        # Calculate summary text height
                        summary_max_width = width - 240
                        summary_text = summary if len(summary) < 150 else summary[:150] + "..."
                        
                        # Estimate number of lines needed for summary
                        words = summary_text.split()
                        line_width = 0
                        summary_lines = 1
                        
                        for word in words:
                            word_width = normal_font.size(word + " ")[0]
                            if line_width + word_width > summary_max_width:
                                summary_lines += 1
                                line_width = word_width
                            else:
                                line_width += word_width
                        
                        # Calculate summary height based on estimated line count
                        summary_text_height = normal_font.get_linesize() * min(3, summary_lines)
                        
                        # Calculate total content height with padding
                        content_height = name_text_height + path_text_height + summary_text_height + 25
                        result_height = max(100, content_height)  # Ensure minimum height
                        
                        # File button
                        file_btn = pygame.Rect(width - 180, result_y + 10, 80, 24)
                        if file_btn.collidepoint(mouse_pos) and os.path.exists(path):
                            open_file(path)
                            
                        # Folder button
                        folder_btn = pygame.Rect(width - 90, result_y + 10, 80, 24)
                        if folder_btn.collidepoint(mouse_pos) and os.path.exists(path):
                            open_folder(path)
                            
                        # Update result_y for next item with proper spacing
                        result_y += result_height + 10
            # Handle input
            if search_input.handle_event(event):
                # Search triggered
                search_files(search_input.text)
                current_page = 0
        
        # Fill background
        try:
            screen.fill(WHITE)
            
            # Draw title
            draw_text(screen, "File Classifier & Search", (20, 20), title_font)
            
            # Draw search input
            search_input.draw(screen)
            
            # Draw scan button
            scan_hover = scan_button.collidepoint(mouse_pos) and not scanning_active
            draw_button(screen, scan_button, "Scan Drives", normal_font, 
                       color=BLUE if not scanning_active else DARK_GRAY,
                       hover=scan_hover)
            
            # Draw stop button
            stop_hover = stop_button.collidepoint(mouse_pos) and scanning_active
            draw_button(screen, stop_button, "Stop Scan", normal_font,
                       color=RED if scanning_active else DARK_GRAY,
                       hover=stop_hover)
            
            # Draw mode selection buttons
            draw_text(screen, "Scan Mode:", (width - 170, 160), normal_font)
            for btn in mode_buttons:
                btn_hover = btn["rect"].collidepoint(mouse_pos)
                is_selected = btn["mode"] == selected_mode
                btn_color = btn["color"] if is_selected else DARK_GRAY
                draw_button(screen, btn["rect"], btn["text"], small_font, 
                           color=btn_color, hover=btn_hover)
                
            # Draw database stats
            stats_text = f"Database: {len(file_database)} files indexed"
            draw_text(screen, stats_text, (20, 130), normal_font)
            
            # Draw progress bar if scanning
            if scanning_active:
                progress_rect = pygame.Rect(20, 150, width - 40, 20)
                pygame.draw.rect(screen, GRAY, progress_rect)
                fill_width = int(progress_rect.width * progress)
                pygame.draw.rect(screen, GREEN, (progress_rect.x, progress_rect.y, fill_width, progress_rect.height))
                pygame.draw.rect(screen, BLACK, progress_rect, 1)
                
                # Draw progress text
                progress_text = f"{current_task} - {processed_files}/{total_files} files processed"
                draw_text(screen, progress_text, (20, 175), small_font)
        
            # Draw search results
            results_text = f"Search Results: {len(search_results)}"
            draw_text(screen, results_text, (20, 180), heading_font)
            
            if search_results:
                start_idx = current_page * results_per_page
                end_idx = min(start_idx + results_per_page, len(search_results))
                
                # Draw results with improved spacing
                result_y = 210
                for i in range(start_idx, end_idx):
                    item, score, search_type = search_results[i]
                    path = item.get("path", "")
                    name = item.get("name", "Unknown")
                    classification = item.get("classification", "Unknown")
                    summary = item.get("summary", "No summary available")
                    
                    # Calculate required height for all components
                    name_text_height = heading_font.get_linesize()
                    path_text_height = small_font.get_linesize()
                    
                    # Calculate summary text height more precisely
                    summary_max_width = width - 240
                    summary_text = summary if len(summary) < 150 else summary[:150] + "..."
                    
                    # Estimate number of lines needed for summary
                    words = summary_text.split()
                    line_width = 0
                    summary_lines = 1
                    
                    for word in words:
                        word_width = normal_font.size(word + " ")[0]
                        if line_width + word_width > summary_max_width:
                            summary_lines += 1
                            line_width = word_width
                        else:
                            line_width += word_width
                    
                    # Calculate summary height based on estimated line count
                    summary_text_height = normal_font.get_linesize() * min(3, summary_lines)
                    
                    # Calculate total content height with padding
                    content_height = name_text_height + path_text_height + summary_text_height + 25
                    result_height = max(100, content_height)  # Ensure minimum height
                    
                    # Draw result box with calculated height
                    result_rect = pygame.Rect(20, result_y, width - 40, result_height)
                    pygame.draw.rect(screen, GRAY, result_rect, 0, 5)
                    
                    # Draw file name and classification
                    name_text = f"{name} - {classification}"
                    y = draw_text(screen, name_text, (30, result_y + 10), heading_font)
                    
                    # Draw path (truncated)
                    path_max_width = width - 70
                    path_text = path if len(path) < 50 else "..." + path[-47:]
                    y = draw_text(screen, path_text, (30, y + 5), small_font, color=DARK_GRAY)
                    
                    # Draw summary (truncated) with proper word wrapping
                    summary_text = summary if len(summary) < 150 else summary[:150] + "..."
                    y = draw_text(screen, summary_text, (30, y + 5), normal_font, max_width=summary_max_width)
                    
                    # Match type and score
                    score_text = f"{search_type.capitalize()}: {score:.2f}"
                    draw_text(screen, score_text, (width - 260, result_y + 10), small_font, color=BLUE)
                    
                    # Draw open buttons
                    file_btn_hover = pygame.Rect(width - 180, result_y + 10, 80, 24).collidepoint(mouse_pos)
                    draw_button(screen, pygame.Rect(width - 180, result_y + 10, 80, 24),
                               "Open File", small_font, hover=file_btn_hover)
                    
                    folder_btn_hover = pygame.Rect(width - 90, result_y + 10, 80, 24).collidepoint(mouse_pos)
                    draw_button(screen, pygame.Rect(width - 90, result_y + 10, 80, 24),
                               "Open Folder", small_font, hover=folder_btn_hover)
                    
                    # Update result_y for next item with proper spacing
                    result_y += result_height + 10
                
                # Draw pagination
                if len(search_results) > results_per_page:
                    # Ensure pagination controls don't overlap with results
                    # By enforcing a minimum distance from the last result
                    pagination_y = min(result_y + 20, height - 70)
                    
                    page_text = f"Page {current_page + 1} of {(len(search_results) - 1) // results_per_page + 1}"
                    draw_text(screen, page_text, (width//2 - 50, pagination_y), normal_font)
                    
                    # Previous button
                    prev_hover = prev_button.collidepoint(mouse_pos) and current_page > 0
                    draw_button(screen, prev_button, "Previous", normal_font, 
                               color=DARK_GRAY if current_page > 0 else GRAY,
                               hover=prev_hover)
                    
                    # Next button
                    has_next = (current_page + 1) * results_per_page < len(search_results)
                    next_hover = next_button.collidepoint(mouse_pos) and has_next
                    draw_button(screen, next_button, "Next", normal_font,
                               color=DARK_GRAY if has_next else GRAY,
                               hover=next_hover)
        
        # Update display
        try:
            pygame.display.flip()
            clock.tick(30)
        except pygame.error as e:
            print(f"Error updating display: {e}")
            # Attempt to restore display
            try:
                screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                pygame.display.set_caption("File Classifier & Search")
            except:
                # If we can't restore, we might need to exit
                running = False
            
    except Exception as e:
        print(f"Error in main loop: {e}")
        return
        
    finally:
        # Always save database and cleanup pygame
        try:
            save_database()
            pygame.quit()
        except Exception as e:
            print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    # Apply any required patches from run_file_classifier.py
    try:
        from run_file_classifier import patch_select_drives_dialog, patch_llm_timeout_handler
        patch_select_drives_dialog()
        patch_llm_timeout_handler()
    except ImportError:
        print("Warning: Could not apply patches from run_file_classifier.py")
        
    # Call the enhanced main function
    enhanced_main()
