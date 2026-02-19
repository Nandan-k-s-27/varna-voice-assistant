# VARNA Voice Assistant

**VARNA (Voice Activated Responsive Network Assistant)** is a secure, fully offline Windows desktop voice assistant. It uses speech recognition for high-accuracy STT and pyttsx3 for TTS feedback, featuring a robust whitelist-based execution system with window intelligence and natural language understanding.

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

### v1.3 — Personalization + Interface
- **Custom Macros**: `"whenever I say focus mode do open vscode and open chrome"`.
- **Clipboard Intelligence**: `"read clipboard"` / `"what did I copy"`.
- **Smart Screenshot**: `"screenshot as ReactBug"` → saves `ReactBug.png` to Desktop.
- **File Search**: `"find PDF downloaded yesterday"` with type + date filters.
- **System Tray UI**: Floating overlay showing mic status, last command, result.

### v1.5 — Universal App Control
- **Open ANY App**: `"open whatsapp"` / `"open spotify"` / `"open telegram"` — scans your entire PC.
  - Scans Start Menu shortcuts, Program Files, AppData, and UWP Store apps.
  - Auto-builds searchable index cached in `apps.json`.
  - Fuzzy matches speech errors: `"open watsapp"` → finds WhatsApp.
  - If multiple matches → suggests similar apps.
- **Close ANY App**: `"close whatsapp"` → finds running process via `psutil` and terminates.
- **App Management**: `"scan apps"` to rebuild index. `"list installed apps"` to see all.
- **No hardcoding**: Works with any installed .exe or UWP app.

### v1.4 — Smart Application Control + Natural Parsing
- **Window Intelligence**: Smart open (restores if minimized, focuses if running, launches if not).
  - `"switch to chrome"` / `"minimize edge"` / `"maximize vscode"` / `"show desktop"`.
  - `"open new chrome window"` → forces a new instance.
- **Voice Typing**: `"type hello world"` → types text in any active application.
- **Tab Control**: `"close tab"` / `"new tab"` / `"next tab"` / `"previous tab"` / `"reopen tab"`.
- **Flexible NLP** (no LLM):
  - **Filler removal**: `"can you please open notepad for me"` → `"open notepad"`.
  - **Fuzzy matching**: Handles speech recognition errors (75%+ similarity).
  - **Intent extraction**: `"launch chrome"` / `"fire up vscode"` → all understood.
- **Smart Search Routing**: If browser is active → searches in current tab (Ctrl+L → type → Enter).
- **Natural Chains**: `"open edge and search React hooks"` → executes both in sequence.

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

Speak commands naturally — VARNA now understands flexible language.

### Example Commands

| Category | Example | What It Does |
|----------|---------|-------------|
| **Smart Open** | "open chrome" | Restores if minimized, focuses if running, launches if not |
| **Window** | "switch to vscode" | Brings VS Code to front |
| **Window** | "minimize edge" | Minimizes Edge |
| **Tab** 🆕 | "close tab" | Closes current browser tab |
| **Tab** 🆕 | "new tab" | Opens new tab |
| **Typing** 🆕 | "type hello world" | Types in active window |
| **NLP** 🆕 | "can you open notepad" | Strips fillers → opens Notepad |
| **Chain** 🆕 | "open edge and search React" | Opens Edge, then searches |
| **Search** | "search React hooks" | In-tab if browser active, else new tab |
| **Clipboard** | "read clipboard" | Speaks clipboard contents |
| **Screenshot** | "screenshot as ReactBug" | Named screenshot to Desktop |
| **File Search** | "find PDF yesterday" | Searches common folders |
| **Macros** | "whenever I say dev mode do open vscode and open chrome" | Saves macro |
| **System** | "shutdown system" | Shuts down (with confirmation) |

For the full list of **115+ commands**, see [`COMMANDS.md`](COMMANDS.md).

## Repository Structure

| File | Purpose |
|------|---------|
| `main.py` | Entry point — listening loop, command routing, all handlers |
| `listener.py` | Speech recognition + yes/no confirmation |
| `parser.py` | 20-step command matching pipeline with NLP preprocessing |
| `executor.py` | Safe PowerShell execution |
| `speaker.py` | Text-to-speech |
| `context.py` | Session state + browser tracking + pronoun resolution |
| `monitor.py` | Background process monitoring |
| `macros.py` | Custom macro manager |
| `tray.py` | System tray icon + floating overlay |
| `window_manager.py` | Smart window control (pygetwindow) + AppManager fallback |
| `nlp.py` | Rule-based NLP — filler removal, fuzzy match, intent extract |
| `app_manager.py` | Universal app scan, index, fuzzy match, launch, close 🆕 |
| `apps.json` | Auto-generated installed app cache 🆕 |
| `commands.json` | Structured command whitelist |
| `macros.json` | User-defined macros storage |

## Architecture

```
🎤 Microphone → 📝 STT → 🧹 NLP Clean → 🧠 Parser (20 steps) → 🛡 Whitelist
                                                    ↓
                    ┌───────────────────────────────┼───────────────────────┐
                    ↓                               ↓                       ↓
             🪟 WindowManager              ⚡ PowerShell              ⌨️ PyAutoGUI
          (smart open/switch/             (safe execution)          (type/tab/search)
           minimize/maximize)
                    ↓
              📦 AppManager
           (scan / fuzzy match /
            launch / close)
                    ↓                               ↓                       ↓
                    └───────────────────────────────┼───────────────────────┘
                                                    ↓
                                              🔊 TTS Response
                                              🖥️ Tray UI Update
```

## Version History

| Version | Description |
|---------|-------------|
| v1.0 | Core assistant — static commands, TTS, STT |
| v1.1 | Parameterized commands, chaining, developer mode |
| v1.2 | Context tracking, confirmation, scheduler, monitoring |
| v1.3 | Custom macros, clipboard, smart screenshot, file search, tray UI |
| v1.4 | Window intelligence, voice typing, tab control, flexible NLP, smart search, natural chains |
| v1.5 | **Universal App Manager** — open/close ANY installed app, auto-scan, fuzzy match, UWP support |
