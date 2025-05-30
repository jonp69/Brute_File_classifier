"""
Fix for pygame display surface issue in File Classifier.
This script patches common issues with pygame window management and UI layout.
"""
import os
import sys
import pygame

def patch_select_drives_dialog():
    """Patch the file_classifier.py in memory to fix the display surface issue"""
    import file_classifier
    
    # Store the original function for later restoration
    original_select_drives = file_classifier.select_drives_dialog
    
    def fixed_select_drives_dialog():
        """Fixed version of the select_drives_dialog that preserves display state"""
        available_drives = file_classifier.get_available_drives()
        selected_drives = []
        
        # Store current display mode
        current_display_info = pygame.display.Info()
        current_w, current_h = current_display_info.current_w, current_display_info.current_h
        current_display_surface = pygame.display.get_surface()
        current_caption = pygame.display.get_caption()[0]
        
        # Create a simple dialog using Pygame
        dialog_width, dialog_height = 400, 300
        
        # Position the dialog in the center of the screen
        dialog_x = (current_w - dialog_width) // 2
        dialog_y = (current_h - dialog_height) // 2
        
        dialog = pygame.display.set_mode((dialog_width, dialog_height))
        pygame.display.set_caption("Select Drives to Scan")
        
        # Fonts
        title_font = pygame.font.SysFont("Arial", 20, bold=True)
        normal_font = pygame.font.SysFont("Arial", 16)
        
        # Create checkboxes for each drive
        checkboxes = []
        for i, drive in enumerate(available_drives):
            drive_info = f"{drive}"
            try:
                # Get drive type and free space
                if os.name == 'nt':
                    import ctypes
                    free_bytes = ctypes.c_ulonglong(0)
                    total_bytes = ctypes.c_ulonglong(0)
                    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                        ctypes.c_wchar_p(drive), None, ctypes.pointer(total_bytes), ctypes.pointer(free_bytes)
                    )
                    free_gb = free_bytes.value / (1024**3)
                    total_gb = total_bytes.value / (1024**3)
                    drive_info = f"{drive} ({free_gb:.1f} GB free / {total_gb:.1f} GB)"
            except:
                pass
                
            checkbox_rect = pygame.Rect(20, 60 + i * 30, 20, 20)
            checkboxes.append({
                "rect": checkbox_rect, 
                "checked": False, 
                "drive": drive,
                "info": drive_info
            })
        
        # Buttons
        ok_button = pygame.Rect(dialog_width // 2 - 100, dialog_height - 50, 80, 30)
        cancel_button = pygame.Rect(dialog_width // 2 + 20, dialog_height - 50, 80, 30)
        
        # Dialog loop
        running = True
        mouse_pos = (0, 0)
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    
                elif event.type == pygame.MOUSEMOTION:
                    mouse_pos = event.pos
                    
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Check checkbox clicks
                    for checkbox in checkboxes:
                        if checkbox["rect"].collidepoint(mouse_pos):
                            checkbox["checked"] = not checkbox["checked"]
                    
                    # Check button clicks
                    if ok_button.collidepoint(mouse_pos):
                        selected_drives = [cb["drive"] for cb in checkboxes if cb["checked"]]
                        running = False
                        
                    elif cancel_button.collidepoint(mouse_pos):
                        running = False
            
            # Draw dialog
            dialog.fill(file_classifier.WHITE)
            
            # Title
            file_classifier.draw_text(dialog, "Select Drives to Scan", (20, 20), title_font)
            
            # Draw checkboxes
            for checkbox in checkboxes:
                pygame.draw.rect(dialog, file_classifier.BLACK, checkbox["rect"], 1)
                if checkbox["checked"]:
                    # Draw X inside checkbox
                    pygame.draw.line(dialog, file_classifier.BLACK, 
                                   (checkbox["rect"].left + 3, checkbox["rect"].top + 3), 
                                   (checkbox["rect"].right - 3, checkbox["rect"].bottom - 3), 2)
                    pygame.draw.line(dialog, file_classifier.BLACK, 
                                   (checkbox["rect"].left + 3, checkbox["rect"].bottom - 3), 
                                   (checkbox["rect"].right - 3, checkbox["rect"].top + 3), 2)
                    
                # Draw drive label
                file_classifier.draw_text(dialog, checkbox["info"], (checkbox["rect"].right + 10, checkbox["rect"].top), normal_font)
            
            # Draw buttons
            ok_hover = ok_button.collidepoint(mouse_pos)
            cancel_hover = cancel_button.collidepoint(mouse_pos)
            
            file_classifier.draw_button(dialog, ok_button, "OK", normal_font, hover=ok_hover)
            file_classifier.draw_button(dialog, cancel_button, "Cancel", normal_font, hover=cancel_hover)
            
            pygame.display.flip()
        
        # Restore the original display mode
        if current_display_surface is not None:
            restored_screen = pygame.display.set_mode((current_w, current_h), pygame.RESIZABLE)
            pygame.display.set_caption(current_caption)
        
        return selected_drives
    
    # Replace with the fixed version
    file_classifier.select_drives_dialog = fixed_select_drives_dialog

def patch_llm_timeout_handler():
    """Patch the LLM request handling to fix timeout issues"""
    import file_classifier
    import json
    import requests
    
    # Store the original function for reference
    original_classify = file_classifier.classify_file_with_llm
    
    def fixed_classify_file_with_llm(file_path, content_preview):
        """Fixed version of classify_file_with_llm with better timeout handling"""
        config = file_classifier.load_config()
        
        if len(content_preview.strip()) == 0:
            return {
                "classification": "Unknown",
                "summary": "Empty or unreadable file",
                "keywords": []
            }
        
        # Limit content preview length more aggressively to reduce LLM load
        max_preview_length = 1000  # Reduced from 1500
        
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
            
            # Update config with these values if not present
            if "request_timeout" not in config:
                config["request_timeout"] = timeout
                file_classifier.save_config(config)
            if "max_retries" not in config:
                config["max_retries"] = max_retries
                file_classifier.save_config(config)
                
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
                            json_match = file_classifier.re.search(r'\{.*\}', text, file_classifier.re.DOTALL)
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
                            json_match = file_classifier.re.search(r'\{.*\}', text, file_classifier.re.DOTALL)
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
                    
                    # Wait before retrying
                    backoff_time = (retry + 1) * 2
                    print(f"Retrying LLM request in {backoff_time} seconds (attempt {retry+1}/{max_retries})...")
                    file_classifier.time.sleep(backoff_time)
                    
                except requests.exceptions.Timeout:
                    print(f"LLM request timed out (attempt {retry+1}/{max_retries+1})")
                    if retry == max_retries:
                        raise  # Re-raise the timeout exception on last attempt
                    backoff_time = (retry + 1) * 2
                    print(f"Retrying in {backoff_time} seconds...")
                    file_classifier.time.sleep(backoff_time)
                    
                except requests.exceptions.ConnectionError as ce:
                    print(f"LLM connection error: {ce} (attempt {retry+1}/{max_retries+1})")
                    if retry == max_retries:
                        raise
                    backoff_time = (retry + 1) * 2
                    print(f"Retrying in {backoff_time} seconds...")
                    file_classifier.time.sleep(backoff_time)
            
            # Fallback response if all retries failed
            return {
                "classification": "Unknown",
                "summary": "Failed to classify with LLM after multiple attempts",
                "keywords": ["error", "classification-failed", "timeout"]
            }
        
        except Exception as e:
            print(f"LLM classification error: {e}")
            return {
                "classification": "Error",
                "summary": f"Error classifying: {str(e)}",
                "keywords": ["error"]
            }
    
    # Replace with the fixed version
    file_classifier.classify_file_with_llm = fixed_classify_file_with_llm

def patch_search_results_display():
    """Patch the search results display to fix overlapping UI elements"""
    import file_classifier
    
    # Store original function for reference 
    original_main = file_classifier.main
    
    def fixed_main():
        """Fixed version of the main function with improved UI layout"""
        # Initialize pygame
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
        search_input = file_classifier.Input((20, 70, width - 200, 40), normal_font, "Search files...")
        
        # Load database
        file_classifier.load_database()
        
        # Initialize embedding model in background
        threading.Thread(target=file_classifier.init_embedding_model, daemon=True).start()
        
        # Main UI elements
        scan_button = pygame.Rect(width - 170, 70, 150, 40)
        stop_button = pygame.Rect(width - 170, 120, 150, 40)
        prev_button = pygame.Rect(width//2 - 100, height - 50, 80, 30)
        next_button = pygame.Rect(width//2 + 20, height - 50, 80, 30)
        
        # Track mouse for hover effects
        mouse_pos = (0, 0)
        
        # Main loop
        running = True
        clock = pygame.time.Clock()
        
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    
                elif event.type == pygame.VIDEORESIZE:
                    width, height = event.w, event.h
                    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                    # Update UI positions
                    search_input.rect = pygame.Rect(20, 70, width - 200, 40)
                    scan_button = pygame.Rect(width - 170, 70, 150, 40)
                    stop_button = pygame.Rect(width - 170, 120, 150, 40)
                    prev_button = pygame.Rect(width//2 - 100, height - 50, 80, 30)
                    next_button = pygame.Rect(width//2 + 20, height - 50, 80, 30)
                    
                elif event.type == pygame.MOUSEMOTION:
                    mouse_pos = event.pos
                    
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if scan_button.collidepoint(mouse_pos) and not file_classifier.scanning_active:
                        # Let user select drives to scan
                        selected_drives = file_classifier.select_drives_dialog()
                        
                        if selected_drives:  # Only scan if drives were selected
                            # Start scan in a background thread
                            scan_thread = threading.Thread(
                                target=file_classifier.scan_files,
                                args=(selected_drives,),
                                daemon=True
                            )
                            scan_thread.start()
                            
                    elif stop_button.collidepoint(mouse_pos) and file_classifier.scanning_active:
                        file_classifier.scanning_active = False
                        file_classifier.current_task = "Scan stopped"
                        
                    elif prev_button.collidepoint(mouse_pos) and file_classifier.current_page > 0:
                        file_classifier.current_page -= 1
                        
                    elif next_button.collidepoint(mouse_pos) and (file_classifier.current_page + 1) * file_classifier.results_per_page < len(file_classifier.search_results):
                        file_classifier.current_page += 1
                        
                    # Handle result clicks (open file or folder)
                    if len(file_classifier.search_results) > 0:
                        start_idx = file_classifier.current_page * file_classifier.results_per_page
                        end_idx = min(start_idx + file_classifier.results_per_page, len(file_classifier.search_results))
                        
                        result_y = 210
                        for i in range(start_idx, end_idx):
                            item = file_classifier.search_results[i][0]
                            path = item.get("path", "")
                            
                            # Calculate result box height more accurately
                            name = item.get("name", "Unknown")
                            classification = item.get("classification", "Unknown")
                            summary = item.get("summary", "No summary available")[:150]
                            
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
                            
                            # File button
                            file_btn = pygame.Rect(width - 180, result_y + 10, 80, 24)
                            if file_btn.collidepoint(mouse_pos) and os.path.exists(path):
                                file_classifier.open_file(path)
                                
                            # Folder button
                            folder_btn = pygame.Rect(width - 90, result_y + 10, 80, 24)
                            if folder_btn.collidepoint(mouse_pos) and os.path.exists(path):
                                file_classifier.open_folder(path)
                                
                            # Update result_y for next item with proper spacing
                            result_y += result_height + 10
                    
                # Handle input
                if search_input.handle_event(event):
                    # Search triggered
                    file_classifier.search_files(search_input.text)
                    file_classifier.current_page = 0
            
            # Fill background
            screen.fill(file_classifier.WHITE)
            
            # Draw title
            file_classifier.draw_text(screen, "File Classifier & Search", (20, 20), title_font)
            
            # Draw search input
            search_input.draw(screen)
            
            # Draw scan button
            scan_hover = scan_button.collidepoint(mouse_pos) and not file_classifier.scanning_active
            file_classifier.draw_button(screen, scan_button, "Scan Drives", normal_font, 
                           color=file_classifier.BLUE if not file_classifier.scanning_active else file_classifier.DARK_GRAY,
                           hover=scan_hover)
            
            # Draw stop button
            stop_hover = stop_button.collidepoint(mouse_pos) and file_classifier.scanning_active
            file_classifier.draw_button(screen, stop_button, "Stop Scan", normal_font,
                           color=file_classifier.RED if file_classifier.scanning_active else file_classifier.DARK_GRAY,
                           hover=stop_hover)
            
            # Draw database stats
            stats_text = f"Database: {len(file_classifier.file_database)} files indexed"
            file_classifier.draw_text(screen, stats_text, (20, 130), normal_font)
            
            # Draw progress bar if scanning
            if file_classifier.scanning_active:
                progress_rect = pygame.Rect(20, 150, width - 40, 20)
                pygame.draw.rect(screen, file_classifier.GRAY, progress_rect)
                fill_width = int(progress_rect.width * file_classifier.progress)
                pygame.draw.rect(screen, file_classifier.GREEN, (progress_rect.x, progress_rect.y, fill_width, progress_rect.height))
                pygame.draw.rect(screen, file_classifier.BLACK, progress_rect, 1)
                
                # Draw progress text
                progress_text = f"{file_classifier.current_task} - {file_classifier.processed_files}/{file_classifier.total_files} files processed"
                file_classifier.draw_text(screen, progress_text, (20, 175), small_font)
            
            # Draw search results
            results_text = f"Search Results: {len(file_classifier.search_results)}"
            file_classifier.draw_text(screen, results_text, (20, 180), heading_font)
            
            if file_classifier.search_results:
                start_idx = file_classifier.current_page * file_classifier.results_per_page
                end_idx = min(start_idx + file_classifier.results_per_page, len(file_classifier.search_results))
                
                # Draw results with improved spacing
                result_y = 210
                for i in range(start_idx, end_idx):
                    item, score, search_type = file_classifier.search_results[i]
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
                    pygame.draw.rect(screen, file_classifier.GRAY, result_rect, 0, 5)
                    
                    # Draw file name and classification
                    name_text = f"{name} - {classification}"
                    y = file_classifier.draw_text(screen, name_text, (30, result_y + 10), heading_font)
                    
                    # Draw path (truncated)
                    path_max_width = width - 70
                    path_text = path if len(path) < 50 else "..." + path[-47:]
                    y = file_classifier.draw_text(screen, path_text, (30, y + 5), small_font, color=file_classifier.DARK_GRAY)
                    
                    # Draw summary (truncated) with proper word wrapping
                    summary_text = summary if len(summary) < 150 else summary[:150] + "..."
                    y = file_classifier.draw_text(screen, summary_text, (30, y + 5), normal_font, max_width=summary_max_width)
                    
                    # Match type and score
                    score_text = f"{search_type.capitalize()}: {score:.2f}"
                    file_classifier.draw_text(screen, score_text, (width - 260, result_y + 10), small_font, color=file_classifier.BLUE)
                    
                    # Draw open buttons
                    file_btn_hover = pygame.Rect(width - 180, result_y + 10, 80, 24).collidepoint(mouse_pos)
                    file_classifier.draw_button(screen, pygame.Rect(width - 180, result_y + 10, 80, 24),
                                   "Open File", small_font, hover=file_btn_hover)
                    
                    folder_btn_hover = pygame.Rect(width - 90, result_y + 10, 80, 24).collidepoint(mouse_pos)
                    file_classifier.draw_button(screen, pygame.Rect(width - 90, result_y + 10, 80, 24),
                                   "Open Folder", small_font, hover=folder_btn_hover)
                    
                    # Update result_y for next item with proper spacing
                    result_y += result_height + 10
                
                # Draw pagination
                if len(file_classifier.search_results) > file_classifier.results_per_page:
                    # Ensure pagination controls don't overlap with results
                    # By enforcing a minimum distance from the last result
                    pagination_y = min(result_y + 20, height - 70)
                    
                    page_text = f"Page {file_classifier.current_page + 1} of {(len(file_classifier.search_results) - 1) // file_classifier.results_per_page + 1}"
                    file_classifier.draw_text(screen, page_text, (width//2 - 50, pagination_y), normal_font)
                    
                    # Previous button
                    prev_btn = pygame.Rect(width//2 - 100, pagination_y + 30, 80, 30)
                    prev_hover = prev_btn.collidepoint(mouse_pos) and file_classifier.current_page > 0
                    file_classifier.draw_button(screen, prev_btn, "Previous", normal_font, 
                                   color=file_classifier.DARK_GRAY if file_classifier.current_page > 0 else file_classifier.GRAY,
                                   hover=prev_hover)
                    
                    # Next button
                    next_btn = pygame.Rect(width//2 + 20, pagination_y + 30, 80, 30)
                    has_next = (file_classifier.current_page + 1) * file_classifier.results_per_page < len(file_classifier.search_results)
                    next_hover = next_btn.collidepoint(mouse_pos) and has_next
                    file_classifier.draw_button(screen, next_btn, "Next", normal_font,
                                   color=file_classifier.DARK_GRAY if has_next else file_classifier.GRAY,
                                   hover=next_hover)
            
            # Update display
            pygame.display.flip()
            clock.tick(30)
        
        # Save database before exit
        file_classifier.save_database()
        pygame.quit()
    
    # Replace with the fixed version
    file_classifier.main = fixed_main

def patch_parallel_scanning():
    """Patch the file scanning to use parallel processing"""
    import file_classifier
    import parallel_scanner
    
    # Store the original function for reference
    original_scan_files = file_classifier.scan_files
    
    def fixed_scan_files(drive_paths):
        """Fixed version of scan_files that uses parallel processing"""
        global scanning_active, current_task, progress, total_files, processed_files, file_database
        
        scanning_active = True
        current_task = "Initializing parallel scanning..."
        progress = 0
        
        def update_progress(processed, total):
            """Callback to update progress"""
            global progress, processed_files
            processed_files = processed
            progress = processed / total if total > 0 else 0
        
        try:
            current_task = "Scanning files in parallel..."
            total, processed = parallel_scanner.parallel_scan_files(
                drive_paths,
                file_database,
                file_classifier.classify_file_with_llm,
                file_classifier.get_file_preview,
                file_classifier.save_database,
                file_classifier.load_config,
                update_progress
            )
            total_files = total
            processed_files = processed
            
        except Exception as e:
            current_task = f"Error during parallel scan: {str(e)}"
            print(f"Parallel scanning error: {e}")
        finally:
            scanning_active = False
            current_task = "Scan complete"
    
    # Replace with the fixed version
    file_classifier.scan_files = fixed_scan_files
    
    # Inject the namespace
    file_classifier.parallel_scanner = parallel_scanner

if __name__ == "__main__":
    # Import threading inside this scope to avoid issues
    import threading
    
    # Apply the patches
    patch_select_drives_dialog()
    patch_llm_timeout_handler()
    patch_search_results_display()
    patch_parallel_scanning()
    
    # Now import and run the main function
    from file_classifier import main
    main()
