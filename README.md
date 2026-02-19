# VARNA Voice Assistant

**VARNA (Voice Activated Responsive Network Assistant)** is a secure, offline Windows desktop voice assistant. It utilizes OpenAI Whisper for high-accuracy speech recognition and pyttsx3 for text-to-speech feedback, featuring a robust whitelist-based execution system for security.

## Features

- **Offline STT**: Uses OpenAI Whisper (local) for reliable speech-to-text.
- **Offline TTS**: Uses pyttsx3 for immediate voice response.
- **Command Whitelist**: Ensures only safe, predefined PowerShell/System commands are executed.
- **Customizable**: Easily extendable command set via `commands.json`.

## Requirements

- Python 3.8+
- Requirements listed in `requirements.txt`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Nandan-k-s-27/varna-voice-assistant.git
   cd varna-voice-assistant
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the main assistant script:
```bash
python main.py
```

## Repository Structure

- `main.py`: Entry point of the application.
- `listener.py`: Handles speech recognition and voice input.
- `parser.py`: Processes recognized text into commands.
- `executor.py`: Safe execution of system commands.
- `speaker.py`: Handles text-to-speech output.
- `commands.json`: Whitelisted command mappings.
