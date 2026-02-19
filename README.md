# VARNA Voice Assistant

**VARNA (Voice Activated Responsive Network Assistant)** is a secure, fully offline Windows desktop voice assistant. It uses speech recognition for high-accuracy STT and pyttsx3 for TTS feedback, featuring a robust whitelist-based execution system.

## Features

### v1.0 — Core Assistant
- **Offline STT**: Speech recognition for reliable speech-to-text.
- **Offline TTS**: pyttsx3 for immediate voice response.
- **Command Whitelist**: Only safe, predefined commands are executed.
- **Customizable**: Extend via `commands.json`.

### v1.1 — Smarter Commands
- **Parameterized Commands**: `"search React hooks"` → Google search.
- **Multi-Step Chains**: `"start full stack"` → launches backend + frontend.
- **Developer Mode**: `"kill port 3000"`, `"git status"`, `"show running ports"`.

### v1.2 — Context Awareness + System Expansion
- **Context Tracking**: Remembers last app, project, and browser.
  - `"close it"` → closes last app. `"go back"` → opens last folder.
  - **Browser-aware**: search commands use the last-opened browser.
- **Confirmation Layer**: Dangerous commands ask "Are you sure?".
- **Task Scheduler**: `"schedule shutdown at 10 PM"` via Windows Task Scheduler.
- **Process Monitoring**: `"monitor chrome memory usage"` with background alerts.

### v1.3 — Personalization + Interface Upgrade
- **Custom Macros (Command Learning)**: Define personal automation sequences.
  - `"whenever I say focus mode do open vscode and open chrome"` → saves macro.
  - `"focus mode"` → replays the saved sequence.
  - `"list macros"` / `"delete macro focus mode"`.
- **Clipboard Intelligence**: Read clipboard contents aloud.
  - `"read clipboard"` / `"what did I copy"` → speaks clipboard text.
- **Smart Screenshot**: Take screenshots with custom filenames.
  - `"screenshot as ReactBug"` → saves `ReactBug.png` to Desktop.
- **File Search**: Find files by name, type, or date.
  - `"find PDF downloaded yesterday"` → searches Desktop, Downloads, Documents.
  - Supports type filters (PDF, docx, png, etc.) and time filters (today, yesterday, this week).
- **System Tray UI**: Floating overlay widget showing:
  - 🎤 Mic status, last speech, last command, result.
  - System tray icon with Show/Hide/Exit menu.

## Requirements

- Python 3.8+
- Windows 10/11
- Microphone

## Installation

```bash
git clone https://github.com/Nandan-k-s-27/varna-voice-assistant.git
cd varna-voice-assistant
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

Speak commands directly — VARNA processes all speech.

### Example Commands

| Category | Example | What It Does |
|----------|---------|-------------|
| **Static** | "open chrome" | Launches Chrome |
| **Static** | "battery status" | Shows battery % |
| **Parameterized** | "search React hooks" | Google search (browser-aware) |
| **Chain** | "start my backend" | Navigates + npm start |
| **Developer** | "kill port 3000" | Kills process on port |
| **System** | "shutdown system" | Shuts down (with confirmation) |
| **Scheduler** | "schedule shutdown at 10 PM" | Scheduled shutdown |
| **Monitor** | "monitor chrome memory usage" | Background memory monitor |
| **Context** | "close it" | Closes last opened app |
| **Clipboard** 🆕 | "read clipboard" | Speaks clipboard contents |
| **Screenshot** 🆕 | "screenshot as ReactBug" | Named screenshot to Desktop |
| **File Search** 🆕 | "find PDF downloaded yesterday" | Searches common folders |
| **Macros** 🆕 | "whenever I say focus mode do open vscode and open chrome" | Saves custom macro |

For the full list of **91+ commands**, see [`COMMANDS.md`](COMMANDS.md).

## Repository Structure

| File | Purpose |
|------|---------|
| `main.py` | Entry point — listening loop, command routing, tray integration |
| `listener.py` | Speech recognition, yes/no confirmation |
| `parser.py` | Maps text to commands (static, param, chain, scheduler, monitor, macro, clipboard, file search) |
| `executor.py` | Safe PowerShell execution |
| `speaker.py` | Text-to-speech |
| `context.py` | Session state + browser tracking + pronoun resolution |
| `monitor.py` | Background process monitoring |
| `macros.py` | Custom macro manager (record/play/list/delete) 🆕 |
| `tray.py` | System tray icon + floating overlay 🆕 |
| `commands.json` | Structured command whitelist |
| `macros.json` | User-defined macros storage 🆕 |

## Version History

| Version | Description |
|---------|-------------|
| v1.0 | Core assistant — static commands, TTS, STT |
| v1.1 | Parameterized commands, chaining, developer mode |
| v1.2 | Context tracking, confirmation, scheduler, monitoring |
| v1.3 | Custom macros, clipboard, smart screenshot, file search, tray UI |
