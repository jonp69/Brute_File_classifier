"""
Unified Scanner Module for File Classifier
This module provides a single interface for all scanning modes
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import queue

# Saved references to original functions
original_functions = {}

def setup(scan_func, parallel_scan_func):
    """Store references to original scanning functions"""
    global original_functions
    original_functions['sequential_scan'] = scan_func
    original_functions['parallel_scan'] = parallel_scan_func

def unified_scan(drive_paths, scan_mode="standard", **kwargs):
    """
    Unified scanning function that supports different scanning modes
    
    Args:
        drive_paths: List of drive paths to scan
        scan_mode: Scanning mode to use:
            - "standard": Sequential scanning with LLM classification
            - "parallel": Parallel scanning with LLM classification
            - "offline": Sequential scanning without LLM classification
            - "turbo": Parallel scanning without LLM classification
        **kwargs: Additional arguments to pass to the scanning function
    
    Returns:
        Thread object for the scanning thread
    """
    # Set offline mode based on scan mode
    config = kwargs.get('load_config', lambda: {})()
    original_offline_mode = config.get('offline_mode', False)
    
    # Update config based on mode
    if scan_mode in ("offline", "turbo"):
        config['offline_mode'] = True
        if 'save_config' in kwargs:
            kwargs['save_config'](config)
    
    # Choose scanning function based on mode
    if scan_mode in ("parallel", "turbo"):
        # For parallel modes, use parallel scanner
        scan_function = original_functions['parallel_scan']
        scan_thread = threading.Thread(
            target=scan_function,
            args=(drive_paths,),
            kwargs=kwargs,
            daemon=True
        )
    else:
        # For standard/offline modes, use sequential scanner
        scan_function = original_functions['sequential_scan']
        scan_thread = threading.Thread(
            target=scan_function,
            args=(drive_paths,),
            daemon=True
        )
    
    # Start scanning
    scan_thread.start()
    
    # Restore original config after scan completes
    def restore_config():
        scan_thread.join()
        config = kwargs.get('load_config', lambda: {})()
        config['offline_mode'] = original_offline_mode
        if 'save_config' in kwargs:
            kwargs['save_config'](config)
    
    # Start restoration thread if needed
    if scan_mode in ("offline", "turbo"):
        restore_thread = threading.Thread(target=restore_config, daemon=True)
        restore_thread.start()
    
    return scan_thread
