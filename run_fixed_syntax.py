"""
Fix for pygame display surface and syntax error in simple_unified_app.py.
This script fixes the layout and syntax issues in the MOUSEBUTTONDOWN handler.
"""
import os
import sys
import pygame

def fix_simple_unified_app():
    """Create a fixed version of the simple_unified_app.py file"""
    try:
        # Read the original file
        with open("simple_unified_app.py", "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # Find the problematic section
        mousemotion_idx = -1
        mousebuttondown_idx = -1
        
        for i, line in enumerate(lines):
            if "event.type == pygame.MOUSEMOTION" in line:
                mousemotion_idx = i
            if "event.type == pygame.MOUSEBUTTONDOWN" in line:
                mousebuttondown_idx = i
                break
        
        if mousemotion_idx >= 0 and mousebuttondown_idx >= 0:
            print(f"Found event handlers at lines {mousemotion_idx+1} and {mousebuttondown_idx+1}")
            
            # Fix the indentation
            lines[mousemotion_idx] = "                elif event.type == pygame.MOUSEMOTION:\n"
            lines[mousemotion_idx+1] = "                    mouse_pos = event.pos\n"
            lines[mousemotion_idx+2] = "                    \n"
            lines[mousebuttondown_idx] = "                elif event.type == pygame.MOUSEBUTTONDOWN:\n"
            
            # Fix the indentation for the scan button handler
            next_line = mousebuttondown_idx + 1
            lines[next_line] = "                    if scan_button.collidepoint(mouse_pos) and not scanning_active:\n"
            
            # Write the fixed file
            fixed_file = "fixed_simple_unified_app.py"
            with open(fixed_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
            
            print(f"Created fixed version: {fixed_file}")
            return fixed_file
                
        else:
            print("Could not find the event handler sections!")
            return None
            
    except Exception as e:
        print(f"Error fixing file: {e}")
        return None

def add_error_handling():
    """Add better error handling to the fixed file"""
    try:
        fixed_file = "fixed_simple_unified_app.py"
        
        # Read the fixed file
        with open(fixed_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Add try-except blocks where needed
        # 1. Around the select_drives_dialog call
        old_str = "                    # Let user select drives to scan\n                    selected_drives = select_drives_dialog()"
        new_str = "                    # Let user select drives to scan\n                    try:\n                        selected_drives = select_drives_dialog()\n                    except pygame.error as e:\n                        print(f\"Error in drive selection dialog: {e}\")\n                        # Try to restore the display\n                        try:\n                            screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)\n                            pygame.display.set_caption(\"File Classifier & Search\")\n                            continue\n                        except:\n                            pass"
        
        content = content.replace(old_str, new_str)
        
        # 2. Add global try-except around the main drawing code
        old_str = "        # Fill background\n        screen.fill(WHITE)"
        new_str = "        # Fill background\n        try:\n            screen.fill(WHITE)"
        
        content = content.replace(old_str, new_str)
        
        # 3. Add try-except for display updates
        old_str = "        # Update display\n        pygame.display.flip()\n        clock.tick(30)"
        new_str = "        # Update display\n            try:\n                pygame.display.flip()\n                clock.tick(30)\n            except pygame.error as e:\n                print(f\"Error updating display: {e}\")\n                # Attempt to restore display\n                try:\n                    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)\n                    pygame.display.set_caption(\"File Classifier & Search\")\n                except:\n                    # If we can't restore, we might need to exit\n                    running = False\n        except Exception as e:\n            print(f\"Error in rendering: {e}\")\n            # Try to recover\n            try:\n                screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)\n                pygame.display.set_caption(\"File Classifier & Search\")\n            except:\n                pass"
                
        content = content.replace(old_str, new_str)
        
        # 4. Add better cleanup in finally block
        old_str = "    # Save database before exit\n    save_database()\n    pygame.quit()"
        new_str = "    # Save database before exit\n    try:\n        save_database()\n        pygame.quit()\n    except Exception as e:\n        print(f\"Error during cleanup: {e}\")"
        
        content = content.replace(old_str, new_str)
        
        # Save the enhanced file
        with open(fixed_file, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"Added error handling to {fixed_file}")
        return True
            
    except Exception as e:
        print(f"Error adding error handling: {e}")
        return False

if __name__ == "__main__":
    # Fix the syntax issues first
    fixed_file = fix_simple_unified_app()
    
    if fixed_file:
        # Add better error handling
        add_error_handling()
        
        # Run the fixed file
        print("Running fixed file...")
        try:
            import fixed_simple_unified_app
        except Exception as e:
            print(f"Error running fixed file: {e}")
