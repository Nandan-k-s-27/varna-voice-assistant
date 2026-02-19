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

### v1.2 — Context Awareness + System Expansion (No LLM)
- **Wake Word Activation**: VARNA only listens after hearing "hey VARNA" / "hi VARNA".
  - Ignores all ambient speech until the wake word is detected.
  - Plays an audio acknowledgement ("Yes?") before listening for commands.
- **Context / State Tracking**: Remembers session state for smart command resolution.
  - Tracks last opened app, last project, and current working directory.
  - `"close it"` → Closes the last opened application.
  - `"open it again"` → Re-opens the last app.
  - `"go back"` → Opens the last accessed project folder.
  - `"session status"` → Reports full context state.
- **Confirmation Layer**: Safety mechanism for dangerous commands.
  - `"shutdown system"` → VARNA asks **"Are you sure?"** before executing.
  - Supports voice confirmation (yes/no) with timeout auto-cancel.
  - Protects: shutdown, restart, log off, empty recycle bin, kill all node.
- **Task Scheduler Integration**: OS-level automation via Windows Task Scheduler.
  - `"schedule shutdown at 10 PM"` → Creates a scheduled shutdown task.
  - `"schedule restart in 30 minutes"` → Schedules restart with relative time.
  - `"cancel scheduled shutdown"` → Removes the scheduled task.
  - `"show scheduled tasks"` → Lists VARNA-created tasks.
- **Process Monitoring**: Background memory monitoring with alerts.
  - `"monitor chrome memory usage"` → Polls Chrome every 5s in background.
  - Alerts via TTS when memory exceeds threshold (default 500 MB).
  - `"stop monitoring"` → Stops the background monitor.
  - `"check process node"` → One-shot process status report.

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

Say **"hey VARNA"** to activate, then speak your command.

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
| **System** 🆕    | "shutdown system"                       | Shuts down PC (with confirmation)   |
| **Scheduler** 🆕 | "schedule shutdown at 10 PM"            | Schedules shutdown via Task Scheduler|
| **Monitor** 🆕   | "monitor chrome memory usage"           | Background memory monitoring        |
| **Context** 🆕   | "close it"                              | Closes last opened app              |
| **Context** 🆕   | "go back"                               | Opens last project folder           |

For the full list of all 77 commands, see [`COMMANDS.md`](COMMANDS.md).

## Repository Structure

- `main.py` — Entry point with wake-word loop, confirmation, and monitor handling.
- `listener.py` — Speech recognition: wake word detection, command listening, yes/no confirmation.
- `parser.py` — Maps spoken text to commands (static, parameterized, chains, scheduler, monitor, context).
- `executor.py` — Safe execution of PowerShell commands (single + chain).
- `speaker.py` — Text-to-speech output.
- `context.py` — Session state tracking and pronoun resolution. 🆕
- `monitor.py` — Background process monitoring with TTS alerts. 🆕
- `commands.json` — Structured command whitelist (static, parameterized, chains, developer, system, scheduler, monitoring, context).

## Version History

| Version | Description                                                     |
| ------- | --------------------------------------------------------------- |
| v1.0    | Core assistant — static commands, TTS, STT                      |
| v1.1    | Parameterized commands, command chaining, developer mode         |
| v1.2    | Wake word, context tracking, confirmation, scheduler, monitoring |
