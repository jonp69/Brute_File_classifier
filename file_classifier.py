import os
import pygame
import json
import threading
import time
import requests
from pathlib import Path
import string
import re
from datetime import datetime
import shutil
import tkinter as tk
from tkinter import filedialog
from tqdm import tqdm
import numpy as np
import torch  # Add this import

# Check CUDA availability
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA device count: {torch.cuda.device_count()}")
if torch.cuda.is_available():
    print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
    # Set PyTorch to use CUDA
    device = torch.device("cuda:0")
else:
    device = torch.device("cpu")
    print("CUDA not available, using CPU")

from sentence_transformers import SentenceTransformer

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
    "embedding_model": "all-MiniLM-L6-v2",  # This is a good small model
}

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (200, 200, 200)
DARK_GRAY = (100, 100, 100)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)

# Global variables
file_database = {}
embedding_model = None
embeddings_cache = {}
scanning_active = False
current_task = ""
progress = 0
total_files = 0
processed_files = 0
search_results = []
current_page = 0
results_per_page = 10


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
    with open(config["database_path"], "w", encoding="utf-8") as f:
        json.dump(file_database, f, indent=4, ensure_ascii=False)


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


def classify_file_with_llm(file_path, content_preview):
    """Classify and summarize a file using a local LLM"""
    config = load_config()
    
    if len(content_preview.strip()) == 0:
        return {
            "classification": "Unknown",
            "summary": "Empty or unreadable file",
            "keywords": []
        }
    
    prompt = f"""Please analyze this file content preview and provide:
1. Classification (document type, programming language, etc.)
2. Brief summary (1-2 sentences)
3. Keywords (comma-separated)

File path: {file_path}
Content preview:
```
{content_preview[:1500]}  # Limiting preview size
```

Respond in JSON format:
{{
    "classification": "your classification",
    "summary": "your summary",
    "keywords": ["keyword1", "keyword2", "..."]
}}"""

    try:
        if config["llm_provider"] == "ollama":
            response = requests.post(
                config["ollama_url"],
                json={
                    "model": config["model_name"],
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
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
            
        elif config["llm_provider"] == "lmstudio":
            response = requests.post(
                config["lmstudio_url"],
                json={
                    "model": config["model_name"],
                    "prompt": prompt,
                    "max_tokens": 500,
                    "temperature": 0.1
                },
                timeout=30
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
    
        # Default response if parsing fails
        return {
            "classification": "Unknown",
            "summary": "Failed to classify with LLM",
            "keywords": ["error", "classification-failed"]
        }
    
    except Exception as e:
        print(f"LLM classification error: {e}")
        return {
            "classification": "Error",
            "summary": f"Error classifying: {str(e)}",
            "keywords": ["error"]
        }


def get_file_preview(file_path, max_size_mb=5):
    """Get a preview of a file's content"""
    try:
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
        if file_size > max_size_mb:
            return f"[File too large: {file_size:.2f} MB]"
            
        # Handle text files
        text_extensions = ['.txt', '.py', '.js', '.html', '.css', '.json', '.md', '.csv', '.xml', '.log',
                           '.c', '.cpp', '.h', '.hpp', '.cs', '.java', '.go', '.rs', '.swift', '.kt',
                           '.php', '.rb', '.pl', '.sh', '.bat', '.ps1', '.ino', '.pde', '.sql', '.yaml', '.yml']
        
        _, ext = os.path.splitext(file_path.lower())
        
        # Try to handle extension-less files by checking if content appears to be text
        if ext in text_extensions or ext == '':
            try:
                # Try reading as text first
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(2000)  # Read sample to check if it's text
                    
                    # Check if content seems like text (high proportion of printable chars)
                    printable_ratio = sum(c.isprintable() or c.isspace() for c in content) / len(content) if content else 0
                    if ext == '' and printable_ratio < 0.8:
                        # Probably binary
                        raise ValueError("Appears to be binary content")
                        
                    # If we got here, it's likely text, so read more
                    if len(content) < 10000:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            return f.read(10000)
                    return content
                    
            except Exception as e:
                # If error reading as text, try binary approach
                if ext == '':
                    with open(file_path, 'rb') as f:
                        binary_data = f.read(5000)
                        text = binary_data.decode('utf-8', errors='ignore')
                        text = ''.join(c if c.isprintable() or c.isspace() else ' ' for c in text)
                        return f"[Binary file preview]\n{text}"
                else:
                    return f"[Error reading file: {str(e)}]"
        else:
            # Binary files
            try:
                with open(file_path, 'rb') as f:
                    binary_data = f.read(5000)
                    text = binary_data.decode('utf-8', errors='ignore')
                    text = ''.join(c if c.isprintable() or c.isspace() else ' ' for c in text)
                    return f"[Binary file preview]\n{text}"
            except Exception as e:
                return f"[Error previewing binary file: {str(e)}]"
    except Exception as e:
        return f"[Error accessing file: {str(e)}]"


def scan_files(drive_paths):
    """Scan files on the specified drives"""
    global scanning_active, current_task, progress, total_files, processed_files, file_database
    
    config = load_config()
    exclude_dirs = config["exclude_dirs"]
    exclude_extensions = config["exclude_extensions"]
    max_file_size_mb = config["max_file_size_mb"]
    
    scanning_active = True
    current_task = "Counting files..."
    progress = 0
    
    # First count total files to process
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
    
    # Now process each file
    processed_files = 0
    for drive in drive_paths:
        try:
            current_task = f"Scanning {drive}"
            
            for root, dirs, files in os.walk(drive):
                if not scanning_active:
                    return
                    
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
                
                for file in files:
                    if not scanning_active:
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
                                    progress = processed_files / total_files if total_files > 0 else 0
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
                                progress = processed_files / total_files if total_files > 0 else 0
                                continue
                            
                            # Get file preview
                            content_preview = get_file_preview(file_path, max_file_size_mb)
                            
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
                                "scan_timestamp": time.time()
                            }
                            
                            # Periodically save the database
                            if processed_files % 100 == 0:
                                save_database()
                                
                        except Exception as e:
                            print(f"Error processing file {file_path}: {e}")
                            
                        finally:
                            processed_files += 1
                            progress = processed_files / total_files if total_files > 0 else 0
        
        except Exception as e:
            print(f"Error scanning drive {drive}: {e}")
    
    # Save final database
    save_database()
    scanning_active = False
    current_task = "Scan complete"


def init_embedding_model():
    """Initialize the sentence embedding model"""
    global embedding_model
    config = load_config()
    try:
        embedding_model = SentenceTransformer(config["embedding_model"])
        # Move model to GPU if available
        if torch.cuda.is_available():
            embedding_model = embedding_model.to(device)
            print("Embedding model loaded on GPU")
        else:
            print("Embedding model loaded on CPU")
    except Exception as e:
        print(f"Error loading embedding model: {e}")
        embedding_model = None


def get_embedding(text):
    """Get embedding vector for text"""
    global embedding_model, embeddings_cache
    
    if text in embeddings_cache:
        return embeddings_cache[text]
    
    if embedding_model is None:
        init_embedding_model()
        if embedding_model is None:
            return None
    
    try:
        # Set smaller batch size for GPU memory constraints
        embedding = embedding_model.encode(text, batch_size=4)
        embeddings_cache[text] = embedding
        return embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None


def semantic_search(query, items, top_k=20):
    """Perform semantic search using embeddings"""
    query_embedding = get_embedding(query)
    if query_embedding is None:
        return []
    
    results = []
    for item in items:
        summary = item.get("summary", "")
        if not summary:
            continue
            
        summary_embedding = get_embedding(summary)
        if summary_embedding is None:
            continue
            
        # Calculate cosine similarity
        similarity = np.dot(query_embedding, summary_embedding) / (
            np.linalg.norm(query_embedding) * np.linalg.norm(summary_embedding)
        )
        
        results.append((item, similarity))
    
    # Sort by similarity and return top k
    results.sort(key=lambda x: x[1], reverse=True)
    return [(item, score) for item, score in results[:top_k]]


def keyword_search(query, items):
    """Search files by keywords"""
    query = query.lower()
    results = []
    
    for item in items:
        score = 0
        
        # Check filename
        if query in item.get("name", "").lower():
            score += 0.3
            
        # Check classification
        if query in item.get("classification", "").lower():
            score += 0.2
            
        # Check summary
        if query in item.get("summary", "").lower():
            score += 0.3
            
        # Check keywords
        for keyword in item.get("keywords", []):
            if query in keyword.lower():
                score += 0.2
                break
                
        if score > 0:
            results.append((item, score))
    
    # Sort by score
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def search_files(query):
    """Search files using both keyword and semantic search"""
    global file_database, search_results
    
    if not query.strip():
        search_results = []
        return
        
    items = list(file_database.values())
    
    # Combine keyword and semantic search results
    keyword_results = keyword_search(query, items)
    semantic_results = semantic_search(query, items)
    
    # Merge results (this is a simple approach, could be more sophisticated)
    seen_paths = set()
    combined_results = []
    
    # Add keyword results first
    for item, score in keyword_results:
        path = item.get("path")
        if path not in seen_paths:
            seen_paths.add(path)
            combined_results.append((item, score, "keyword"))
            
    # Add semantic results
    for item, score in semantic_results:
        path = item.get("path")
        if path not in seen_paths and score > 0.5:  # Threshold for semantic similarity
            seen_paths.add(path)
            combined_results.append((item, score, "semantic"))
    
    # Sort by score
    combined_results.sort(key=lambda x: x[1], reverse=True)
    search_results = combined_results


def open_file(path):
    """Open a file with the default application"""
    try:
        if os.name == 'nt':  # Windows
            os.startfile(path)
        elif os.name == 'posix':  # Linux, Mac
            subprocess.call(('xdg-open', path))
    except Exception as e:
        print(f"Error opening file: {e}")


def open_folder(path):
    """Open the folder containing the file"""
    try:
        folder_path = os.path.dirname(path)
        if os.name == 'nt':  # Windows
            os.startfile(folder_path)
        elif os.name == 'posix':  # Linux, Mac
            subprocess.call(('xdg-open', folder_path))
    except Exception as e:
        print(f"Error opening folder: {e}")


def draw_text(surface, text, pos, font, color=BLACK, max_width=None, align="left"):
    """Draw text, optionally wrapping to max_width"""
    if max_width is None:
        text_surface = font.render(text, True, color)
        surface.blit(text_surface, pos)
        return pos[1] + text_surface.get_height()
    else:
        words = text.split(' ')
        space_width = font.size(' ')[0]
        x, y = pos
        line_height = font.get_linesize()
        
        current_line = []
        current_width = 0
        
        for word in words:
            word_width = font.size(word)[0]
            
            if current_width + word_width <= max_width:
                current_line.append(word)
                current_width += word_width + space_width
            else:
                if current_line:
                    line_text = ' '.join(current_line)
                    line_surface = font.render(line_text, True, color)
                    
                    # Handle alignment
                    line_x = x
                    if align == "center":
                        line_x = x + (max_width - line_surface.get_width()) // 2
                    elif align == "right":
                        line_x = x + max_width - line_surface.get_width()
                        
                    surface.blit(line_surface, (line_x, y))
                    y += line_height
                    
                current_line = [word]
                current_width = word_width + space_width
                
        if current_line:
            line_text = ' '.join(current_line)
            line_surface = font.render(line_text, True, color)
            
            # Handle alignment
            line_x = x
            if align == "center":
                line_x = x + (max_width - line_surface.get_width()) // 2
            elif align == "right":
                line_x = x + max_width - line_surface.get_width()
                
            surface.blit(line_surface, (line_x, y))
            y += line_height
            
        return y


def draw_button(surface, rect, text, font, color=DARK_GRAY, hover=False):
    """Draw a button with text"""
    # Draw button background
    if hover:
        # Safe way to darken a color
        darker_color = tuple(max(c-30, 0) for c in color)
        pygame.draw.rect(surface, darker_color, rect)
    else:
        pygame.draw.rect(surface, color, rect)
        
    # Draw button border
    pygame.draw.rect(surface, BLACK, rect, 1)
    
    # Draw button text
    text_surf = font.render(text, True, WHITE)
    text_rect = text_surf.get_rect(center=rect.center)
    surface.blit(text_surf, text_rect)


class Input:
    def __init__(self, rect, font, placeholder="", max_length=100):
        self.rect = pygame.Rect(rect)
        self.font = font
        self.text = ""
        self.placeholder = placeholder
        self.active = False
        self.cursor = 0
        self.max_length = max_length
        self.cursor_visible = True
        self.cursor_timer = 0
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.active = True
                # Set cursor position based on click
                x = event.pos[0] - self.rect.x - 5
                pos = 0
                char_width = self.font.size("A")[0]  # Approximate character width
                while pos < len(self.text) and x > 0:
                    x -= char_width
                    pos += 1
                self.cursor = max(0, min(pos, len(self.text)))
            else:
                self.active = False
        
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                if self.cursor > 0:
                    self.text = self.text[:self.cursor-1] + self.text[self.cursor:]
                    self.cursor -= 1
            elif event.key == pygame.K_DELETE:
                if self.cursor < len(self.text):
                    self.text = self.text[:self.cursor] + self.text[self.cursor+1:]
            elif event.key == pygame.K_LEFT:
                self.cursor = max(0, self.cursor - 1)
            elif event.key == pygame.K_RIGHT:
                self.cursor = min(len(self.text), self.cursor + 1)
            elif event.key == pygame.K_HOME:
                self.cursor = 0
            elif event.key == pygame.K_END:
                self.cursor = len(self.text)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                return True  # Submit
            elif len(self.text) < self.max_length and event.unicode.isprintable():
                self.text = self.text[:self.cursor] + event.unicode + self.text[self.cursor:]
                self.cursor += 1
                
        return False
        
    def draw(self, surface):
        # Draw background
        background_color = WHITE if self.active else GRAY
        pygame.draw.rect(surface, background_color, self.rect)
        pygame.draw.rect(surface, BLACK, self.rect, 1)
        
        # Draw text or placeholder
        if self.text:
            text_surf = self.font.render(self.text, True, BLACK)
        else:
            text_surf = self.font.render(self.placeholder, True, DARK_GRAY)
            
        # Calculate visible text portion (basic scrolling if text too long)
        text_width = text_surf.get_width()
        visible_width = self.rect.width - 10
        
        # Scroll to keep cursor visible if text is too long
        cursor_x_pos = self.font.size(self.text[:self.cursor])[0]
        scroll_x = max(0, min(cursor_x_pos - visible_width + 20, max(0, text_width - visible_width)))
        
        # Blit text with offset
        surface.blit(text_surf, (self.rect.x + 5, self.rect.centery - text_surf.get_height()//2), 
                     (scroll_x, 0, visible_width, text_surf.get_height()))
        
        # Draw cursor if active
        if self.active:
            self.cursor_timer += 1
            if self.cursor_timer > 30:
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer = 0
                
            if self.cursor_visible:
                cursor_x = self.rect.x + 5 + self.font.size(self.text[:self.cursor])[0] - scroll_x
                cursor_height = text_surf.get_height() if self.text else self.font.get_linesize()
                cursor_y = self.rect.centery - cursor_height//2
                pygame.draw.line(surface, BLACK, (cursor_x, cursor_y), 
                                (cursor_x, cursor_y + cursor_height), 2)


def select_drives_dialog():
    """Display a dialog for drive selection"""
    available_drives = get_available_drives()
    selected_drives = []
    
    # Create a simple dialog using Pygame
    pygame.init()
    dialog_width, dialog_height = 400, 300
    
    # Position the dialog in the center of the screen
    screen_info = pygame.display.Info()
    dialog_x = (screen_info.current_w - dialog_width) // 2
    dialog_y = (screen_info.current_h - dialog_height) // 2
    
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
        dialog.fill(WHITE)
        
        # Title
        draw_text(dialog, "Select Drives to Scan", (20, 20), title_font)
        
        # Draw checkboxes
        for checkbox in checkboxes:
            pygame.draw.rect(dialog, BLACK, checkbox["rect"], 1)
            if checkbox["checked"]:
                # Draw X inside checkbox
                pygame.draw.line(dialog, BLACK, 
                               (checkbox["rect"].left + 3, checkbox["rect"].top + 3), 
                               (checkbox["rect"].right - 3, checkbox["rect"].bottom - 3), 2)
                pygame.draw.line(dialog, BLACK, 
                               (checkbox["rect"].left + 3, checkbox["rect"].bottom - 3), 
                               (checkbox["rect"].right - 3, checkbox["rect"].top + 3), 2)
                
            # Draw drive label
            draw_text(dialog, checkbox["info"], (checkbox["rect"].right + 10, checkbox["rect"].top), normal_font)
        
        # Draw buttons
        ok_hover = ok_button.collidepoint(mouse_pos)
        cancel_hover = cancel_button.collidepoint(mouse_pos)
        
        draw_button(dialog, ok_button, "OK", normal_font, hover=ok_hover)
        draw_button(dialog, cancel_button, "Cancel", normal_font, hover=cancel_hover)
        
        pygame.display.flip()
    
    # Restore main screen
    pygame.display.quit()
    
    return selected_drives


def main():
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
    search_input = Input((20, 70, width - 200, 40), normal_font, "Search files...")
    
    # Load database
    load_database()
    
    # Initialize embedding model in background
    threading.Thread(target=init_embedding_model, daemon=True).start()
    
    # Main UI elements
    scan_button = pygame.Rect(width - 170, 70, 150, 40)
    stop_button = pygame.Rect(width - 170, 120, 150, 40)
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
                if scan_button.collidepoint(mouse_pos) and not scanning_active:
                    # Let user select drives to scan
                    selected_drives = select_drives_dialog()
                    
                    if selected_drives:  # Only scan if drives were selected
                        # Start scan in a background thread
                        scan_thread = threading.Thread(
                            target=scan_files,
                            args=(selected_drives,),
                            daemon=True
                        )
                        scan_thread.start()
                        
                elif stop_button.collidepoint(mouse_pos) and scanning_active:
                    scanning_active = False
                    current_task = "Scan stopped"
                    
                elif prev_button.collidepoint(mouse_pos) and current_page > 0:
                    current_page -= 1
                    
                elif next_button.collidepoint(mouse_pos) and (current_page + 1) * results_per_page < len(search_results):
                    current_page += 1
                    
                # Handle result clicks (open file or folder)
                if len(search_results) > 0:
                    start_idx = current_page * results_per_page
                    end_idx = min(start_idx + results_per_page, len(search_results))
                    
                    result_y = 210  # Match the same starting position
                    for i in range(start_idx, end_idx):
                        item = search_results[i][0]
                        path = item.get("path", "")
                        
                        # Calculate required height based on content (simplified)
                        name = item.get("name", "Unknown")
                        classification = item.get("classification", "Unknown")
                        summary = item.get("summary", "No summary available")[:150]
                        
                        content_height = heading_font.get_linesize() + small_font.get_linesize() + normal_font.get_linesize() * 2
                        result_height = max(90, content_height + 20)
                        
                        # File button
                        file_btn = pygame.Rect(width - 180, result_y + 5, 80, 24)
                        if file_btn.collidepoint(mouse_pos) and os.path.exists(path):
                            open_file(path)
                            
                        # Folder button
                        folder_btn = pygame.Rect(width - 90, result_y + 5, 80, 24)
                        if folder_btn.collidepoint(mouse_pos) and os.path.exists(path):
                            open_folder(path)
                            
                        # Update result_y for next item
                        result_y += result_height + 10
                
            # Handle input
            if search_input.handle_event(event):
                # Search triggered
                search_files(search_input.text)
                current_page = 0
        
        # Fill background
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
        y = draw_text(screen, results_text, (20, 180), heading_font)
        
        if search_results:
            start_idx = current_page * results_per_page
            end_idx = min(start_idx + results_per_page, len(search_results))
            
            # Draw results with proper spacing
            result_y = 210  # Start slightly lower to avoid overlap with header
            for i in range(start_idx, end_idx):
                item, score, search_type = search_results[i]
                path = item.get("path", "")
                name = item.get("name", "Unknown")
                classification = item.get("classification", "Unknown")
                summary = item.get("summary", "No summary available")
                
                # Calculate required height based on content
                content_height = 0
                content_height += heading_font.get_linesize()  # Name and classification
                content_height += small_font.get_linesize()    # Path
                
                # Estimate summary text height (based on length and width)
                summary_max_len = 150
                summary_text = summary if len(summary) < summary_max_len else summary[:summary_max_len] + "..."
                summary_lines = len(summary_text) * small_font.size("A")[0] // (width - 240) + 1
                content_height += normal_font.get_linesize() * min(3, summary_lines)
                
                # Ensure minimum height
                result_height = max(90, content_height + 20)
                
                # Draw result box with calculated height
                result_rect = pygame.Rect(20, result_y, width - 40, result_height)
                pygame.draw.rect(screen, GRAY, result_rect, 0, 5)
                
                # Draw file name and classification
                name_text = f"{name} - {classification}"
                y = draw_text(screen, name_text, (30, result_y + 5), heading_font)
                
                # Draw path (truncated)
                path_max_width = width - 70
                path_text = path if len(path) < 50 else "..." + path[-47:]
                y = draw_text(screen, path_text, (30, y + 2), small_font, color=DARK_GRAY)
                
                # Draw summary (truncated)
                summary_text = summary if len(summary) < summary_max_len else summary[:summary_max_len] + "..."
                y = draw_text(screen, summary_text, (30, y + 2), normal_font, max_width=width - 200)
                
                # Match type and score
                score_text = f"{search_type.capitalize()}: {score:.2f}"
                draw_text(screen, score_text, (width - 260, result_y + 5), small_font, color=BLUE)
                
                # Draw open buttons
                file_btn_hover = pygame.Rect(width - 180, result_y + 5, 80, 24).collidepoint(mouse_pos)
                draw_button(screen, pygame.Rect(width - 180, result_y + 5, 80, 24),
                           "Open File", small_font, hover=file_btn_hover)
                
                folder_btn_hover = pygame.Rect(width - 90, result_y + 5, 80, 24).collidepoint(mouse_pos)
                draw_button(screen, pygame.Rect(width - 90, result_y + 5, 80, 24),
                           "Open Folder", small_font, hover=folder_btn_hover)
                
                # Update result_y for next item with proper spacing
                result_y += result_height + 10
            
            # Draw pagination
            if len(search_results) > results_per_page:
                page_text = f"Page {current_page + 1} of {(len(search_results) - 1) // results_per_page + 1}"
                draw_text(screen, page_text, (width//2 - 50, height - 70), normal_font)
                
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
        pygame.display.flip()
        clock.tick(30)
    
    # Save database before exit
    save_database()
    pygame.quit()


if __name__ == "__main__":
    main()
