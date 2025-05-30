"""
LLM Configuration Helper for File Classifier
This script helps optimize LLM settings for your hardware.
"""
import os
import json
import torch
import subprocess
import platform
import psutil
import sys

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "llm_provider": "ollama",
    "ollama_url": "http://localhost:11434/api/generate",
    "lmstudio_url": "http://localhost:1234/v1/completions",
    "model_name": "mistral",
    "request_timeout": 60,
    "max_retries": 2,
    "offline_mode": False
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        return DEFAULT_CONFIG.copy()

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    print(f"Configuration saved to {CONFIG_FILE}")

def get_system_specs():
    specs = {
        "os": platform.system(),
        "python_version": platform.python_version(),
        "cpu": platform.processor(),
        "cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else "N/A",
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
        "gpu_memory_gb": None
    }
    
    # Try to get GPU memory
    if torch.cuda.is_available():
        try:
            # NVIDIA-specific approach
            result = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'])
            memory_mb = float(result.decode('ascii').strip())
            specs["gpu_memory_gb"] = round(memory_mb / 1024, 2)
        except:
            try:
                # PyTorch approach
                specs["gpu_memory_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
            except:
                specs["gpu_memory_gb"] = "Unknown"
    
    return specs

def recommend_llm_model(specs):
    """Recommend appropriate LLM model based on system specs"""
    has_gpu = specs["cuda_available"]
    gpu_memory = specs["gpu_memory_gb"]
    ram_gb = specs["ram_gb"]
    
    if has_gpu and isinstance(gpu_memory, (int, float)):
        if gpu_memory >= 24:
            return "llama2:70b", "High-end GPU with sufficient VRAM for large models"
        elif gpu_memory >= 16:
            return "llama2:13b", "Good GPU with sufficient VRAM for mid-size models"
        elif gpu_memory >= 8:
            return "llama2:7b", "Mid-range GPU suitable for 7B parameter models"
        elif gpu_memory >= 4:
            return "phi:latest", "Entry-level GPU suitable for smaller models like Phi-2"
        else:
            return "tinyllama", "Limited GPU memory, recommend very small models"
    else:
        # CPU recommendations
        if ram_gb >= 32:
            return "llama2:7b-q4_0", "No GPU but good RAM, using quantized 7B model"
        elif ram_gb >= 16:
            return "phi:latest", "No GPU but moderate RAM, using smaller model"
        else:
            return "tinyllama", "Limited system resources, recommend smallest models"

def recommend_timeout(specs):
    """Recommend timeout settings based on system specs"""
    has_gpu = specs["cuda_available"]
    gpu_memory = specs["gpu_memory_gb"]
    cores = specs["cores"]
    
    if has_gpu and isinstance(gpu_memory, (int, float)) and gpu_memory >= 8:
        return 40
    elif has_gpu:
        return 60
    elif cores >= 8:
        return 90
    else:
        return 120

def main():
    print("="*80)
    print("File Classifier LLM Configuration Helper")
    print("="*80)
    
    specs = get_system_specs()
    
    print("\nSystem Specifications:")
    print(f"- Operating System: {specs['os']}")
    print(f"- Python Version: {specs['python_version']}")
    print(f"- CPU: {specs['cpu']}")
    print(f"- CPU Cores: {specs['cores']} (Physical), {specs['logical_cores']} (Logical)")
    print(f"- RAM: {specs['ram_gb']} GB")
    print(f"- CUDA Available: {specs['cuda_available']}")
    if specs['cuda_available']:
        print(f"- CUDA Version: {specs['cuda_version']}")
        print(f"- GPU: {specs['gpu_name']}")
        print(f"- GPU Memory: {specs['gpu_memory_gb']} GB")
    print("\n")
    
    # Load existing config
    config = load_config()
    
    # Get recommendations
    model_name, reason = recommend_llm_model(specs)
    timeout = recommend_timeout(specs)
    
    print("Recommendations based on your hardware:")
    print(f"- LLM Model: {model_name}")
    print(f"  Reason: {reason}")
    print(f"- Request Timeout: {timeout} seconds")
    print(f"- Max Retries: 2")
    
    print("\nCurrent Configuration:")
    print(f"- LLM Provider: {config.get('llm_provider', 'ollama')}")
    print(f"- Model Name: {config.get('model_name', 'mistral')}")
    print(f"- Request Timeout: {config.get('request_timeout', 30)} seconds")
    print(f"- Max Retries: {config.get('max_retries', 1)}")
    print(f"- Offline Mode: {config.get('offline_mode', False)}")
    
    print("\nWould you like to apply the recommended settings?")
    choice = input("Enter (y)es to apply, or any other key to skip: ").lower().strip()
    
    if choice == 'y' or choice == 'yes':
        config["model_name"] = model_name
        config["request_timeout"] = timeout
        config["max_retries"] = 2
        save_config(config)
        print("\nSettings applied successfully!")
    
    print("\nAdditional Tips:")
    print("1. If you experience timeouts, try:")
    print("   - Using a smaller model")
    print("   - Running in offline mode (run_offline.bat)")
    print("   - Increasing the request_timeout value")
    print("2. For faster operation, use quantized models (ending with q4_0, q4_K_M)")
    print("3. To optimize for your GPU, consult Ollama documentation")
    
    print("\nPress Enter to exit...")
    input()

if __name__ == "__main__":
    main()
