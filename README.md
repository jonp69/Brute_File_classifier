# Brute File Classifier

This application scans your computer drives, classifies files using a local LLM (Large Language Model), generates summaries, and allows you to search through these summaries using semantic search.

## Features

- **Drive Scanning**: Recursively scans all connected drives for files
- **LLM Classification**: Uses a local LLM (Ollama or LM Studio) to classify and summarize files
- **Semantic Search**: Find files by meaning, not just by keywords
- **User-friendly UI**: Built with Pygame for a simple, interactive interface

## Requirements

- Python 3.7+
- Pygame
- Sentence Transformers (for semantic search)
- Local LLM provider (Ollama or LM Studio)

## Installation

1. Clone this repository
2. Install dependencies:

```
pip install -r requirements.txt
```

3. Make sure you have either Ollama or LM Studio running locally

## Usage

### Unified Interface (Recommended)

Run the application with all scanning modes integrated into a single user interface:

```
run_unified.bat     # Windows
```

or

```
.\run_unified.ps1   # PowerShell
```

The unified interface provides buttons to select your scanning mode directly in the application:

- **Standard Mode**: Sequential scanning with LLM classification
- **Parallel Mode**: Uses multiple worker threads with LLM classification
- **Offline Mode**: Fast scanning without LLM classification
- **Turbo Mode**: Parallel processing without LLM (maximum speed)

### Legacy Mode Options

These separate scripts are maintained for backward compatibility:

- `run_fixed.bat` / `run_fixed.ps1`: Fixed display surface version
- `run_parallel.bat` / `run_parallel.ps1`: Parallel processing
- `run_offline.bat` / `run_offline.ps1`: Offline mode (no LLM)
- `run_turbo.bat` / `run_turbo.ps1`: Combined parallel and offline modes

### Usage Instructions

1. Click "Scan Drives" to begin scanning your connected drives
2. Use the search bar to find files by content, even if they don't contain the exact keywords
3. Use the "Open File" and "Open Folder" buttons to access the files directly

## Configuration

The application will create a `config.json` file on first run with default settings. You can modify this file to:

- Change the LLM provider (ollama/lmstudio)
- Specify which model to use
- Exclude certain directories or file extensions
- Set maximum file size for processing
- Change the embedding model for semantic search
- Adjust timeout settings for LLM requests
- Enable/disable offline mode

### Advanced Settings

```json
{
  "request_timeout": 60,      // Timeout for LLM requests in seconds
  "max_retries": 2,           // Number of retry attempts for failed LLM requests
  "offline_mode": false       // When true, skips LLM classification for faster scanning
}
```

## Troubleshooting

### LLM Connection Timeout

If you see "LLM classification error: Read timed out" messages:

1. Try increasing the `request_timeout` in config.json
2. Run in offline mode using `run_offline.bat` for initial scanning
3. Ensure your LLM server (Ollama/LM Studio) is running properly
4. Try using a smaller LLM model

### UI Layout Issues

If UI elements overlap or display incorrectly:
- Use the `run_fixed.bat` or `run_fixed.ps1` scripts which include UI layout fixes

## How It Works

1. **Scanning**: The app walks through all connected drives, collecting files that match the size and extension criteria.
2. **Classification**: Each file's contents are sent to a local LLM to classify the file type, generate a summary, and extract keywords.
3. **Indexing**: This information is stored in a searchable database.
4. **Semantic Search**: When you search, the app compares the meaning of your query with file summaries using embeddings from a smaller model.

### Performance Optimizations

- **Parallel Processing**: In the optimized version, file scanning and LLM processing happen concurrently using multiple worker threads. Files are queued for processing as they're discovered, significantly improving throughput.
- **Offline Mode**: When enabled, skips the LLM classification step and uses simple file extension-based classification for extremely fast scanning.
- **Turbo Mode**: Combines parallel processing with offline mode for the fastest possible initial scan.
- **Incremental Updates**: The app remembers previously scanned files and only processes files that have changed since the last scan.

## Notes

- Initial scanning may take a significant amount of time depending on the number of files
- The application remembers previously scanned files to avoid redundant processing
- Only files below the maximum size limit (default: 5MB) will be fully analyzed
- File information is saved locally in a JSON database file
