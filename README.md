# VARNA Voice Assistant

**VARNA (Voice Activated Responsive Network Assistant)** is a secure, offline Windows desktop voice assistant. It utilizes OpenAI Whisper for high-accuracy speech recognition and pyttsx3 for text-to-speech feedback, featuring a robust whitelist-based execution system for security.

## Features

### v1.0 — Core Assistant
- **Offline STT**: Uses OpenAI Whisper (local) for reliable speech-to-text.
- **Offline TTS**: Uses pyttsx3 for immediate voice response.
- **Command Whitelist**: Ensures only safe, predefined PowerShell/System commands are executed.
- **Customizable**: Easily extendable command set via `commands.json`.

### v1.1 — Smarter Commands (No LLM)
- **Parameterized Commands**: Dynamic queries injected into templates.
  - `"search React hooks"` → Opens Google search for "React hooks"
  - `"search youtube Python tutorials"` → Opens YouTube search
  - `"open website github.com"` → Opens any website
- **Multi-Step Command Chains**: Sequential execution pipelines.
  - `"start my backend"` → Navigates to project folder and runs `npm start`
  - `"start full stack"` → Launches both backend and frontend servers
- **Developer Mode**: Productivity shortcuts for developers.
  - `"kill port 3000"` → Kills process on port 3000
  - `"show running ports"` → Lists all listening ports
  - `"pull latest from git"` → Runs `git pull origin main`
  - `"git status"` → Shows current git status
  - `"open git bash"` → Opens Git Bash terminal
  - `"run npm start"` / `"run npm install"`

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

### Example Voice Commands

| Category         | Example Command                         | What It Does                        |
| ---------------- | --------------------------------------- | ----------------------------------- |
| **Static**       | "open chrome"                           | Launches Chrome browser             |
| **Static**       | "battery status"                        | Shows battery percentage            |
| **Parameterized**| "search React hooks"                    | Google search for "React hooks"     |
| **Parameterized**| "search youtube Python tutorials"       | YouTube search                      |
| **Chain**        | "start my backend"                      | Navigates to folder + npm start     |
| **Developer**    | "kill port 3000"                        | Kills process on port 3000          |
| **Developer**    | "show running ports"                    | Lists all listening ports           |

## Repository Structure

- `main.py` — Entry point of the application.
- `listener.py` — Handles speech recognition and voice input.
- `parser.py` — Processes recognized text into commands (static, parameterized, chains).
- `executor.py` — Safe execution of system commands (single + chain).
- `speaker.py` — Handles text-to-speech output.
- `commands.json` — Structured command whitelist (static, parameterized, chains, developer).

## Version History

| Version | Description                                                     |
| ------- | --------------------------------------------------------------- |
| v1.0    | Core assistant — static commands, TTS, STT                      |
| v1.1    | Parameterized commands, command chaining, developer mode         |
