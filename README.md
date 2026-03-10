<p align="center">
  <img src="https://img.shields.io/badge/VARNA-v2.3-e94560?style=for-the-badge&logo=windows&logoColor=white" alt="VARNA v2.3"/>
  <img src="https://img.shields.io/badge/Python-3.8+-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.8+"/>
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078d4?style=for-the-badge&logo=windows&logoColor=white" alt="Windows"/>
  <img src="https://img.shields.io/badge/Offline-100%25-28a745?style=for-the-badge" alt="Offline"/>
  <img src="https://img.shields.io/github/license/Nandan-k-s-27/varna-voice-assistant?style=for-the-badge" alt="License"/>
</p>

<h1 align="center">🌻 VARNA — Voice Activated Resource & Navigation Assistant</h1>

<p align="center">
  <b>A secure, fully offline Windows desktop voice assistant powered by OpenAI Whisper STT and intelligent NLP.</b><br/>
  Control your PC with natural speech — open apps, manage windows, type text, search the web, automate workflows, and more. No internet required.
</p>

---

## What is VARNA?

**VARNA** (Voice Activated Responsive Network Assistant) is an open-source, privacy-first voice assistant for Windows. Unlike cloud-based assistants (Alexa, Google, Siri), VARNA runs **100% offline** on your machine — your voice data never leaves your computer.

It uses **OpenAI Whisper** for accurate speech-to-text, a **layered NLP pipeline** for understanding natural language commands, and a **whitelist-based execution system** that ensures only safe, predefined actions are performed.

### Why VARNA?

| Feature | VARNA | Cloud Assistants |
|---------|-------|-----------------|
| **Privacy** | 100% offline — voice never leaves your PC | Sends audio to cloud servers |
| **Internet** | Not required | Required for most features |
| **Cost** | Free & open-source | Subscription/data collection |
| **Customization** | Full control — add your own commands | Limited API |
| **Security** | Whitelist-only execution | Black-box processing |
| **Latency** | ~1-2s local processing | Network-dependent |

---

## How It Works

```
🎤 Microphone
    │
    ▼
📝 Speech-to-Text (Whisper / Vosk — fully offline)
    │
    ▼
🧹 NLP Pipeline
    ├── Text Normalization (filler removal, accent correction)
    ├── Exact Match (static command lookup)
    ├── Fuzzy Match (handles speech errors — "crome" → "chrome")
    ├── Phonetic Match (pronunciation variants)
    └── Semantic Match (ML-based meaning understanding)
    │
    ▼
🧠 Parser (maps to whitelisted commands)
    │
    ▼
🛡️ Safety Layer (4-gate validation + sandboxing)
    │
    ▼
⚡ Executor
    ├── 🪟 Window Manager (focus, minimize, maximize, snap)
    ├── 📦 App Manager (launch/close ANY installed app)
    ├── ⌨️ PyAutoGUI (type text, tab control, scrolling)
    └── 💻 PowerShell (safe, whitelisted system commands)
    │
    ▼
🔊 Text-to-Speech Response (pyttsx3 — offline)
    │
    ▼
🖥️ System Tray UI (status overlay)
```

---

## Features

### Core Capabilities
- **Open/Close ANY App** — `"open whatsapp"`, `"close spotify"` — scans your entire PC
- **Window Intelligence** — `"switch to chrome"`, `"minimize vscode"`, `"maximize edge"`
- **Voice Typing** — `"type hello world"` — types in any active window
- **Smart Search** — `"search React hooks"` — searches in active browser or opens new tab
- **Tab Control** — `"new tab"`, `"close tab"`, `"go to tab 3"`, `"next tab"`
- **Natural Language** — `"can you help me open notepad"` → strips fillers, understands intent
- **Custom Macros** — `"whenever I say focus mode do open vscode and open chrome"`
- **Command Chaining** — `"open edge and search React hooks"` — multiple commands in one phrase
- **Context Awareness** — `"close it"` closes last app, `"go back"` opens last folder

### Navigation & Control
- **Smart Scrolling** — `"scroll down"`, `"scroll little up"`, `"scroll a lot down"`
- **Drive Navigation** — `"go to D drive"`, `"go to downloads"`, `"go to this PC"`
- **Browser Controls** — `"go back"`, `"go forward"`, `"refresh"`
- **Text Selection** — `"select all text"`, `"select line"`, `"select next 3 words"`
- **40+ Key Commands** — `"press enter"`, `"undo"`, `"redo"`, `"copy this"`, `"paste it"`
- **Clipboard** — `"read clipboard"`, `"open clipboard"`, `"paste 3rd item"`
- **Screenshot** — `"screenshot as ReactBug"` → saves `ReactBug.png` to Desktop

### Intelligence
- **Offline STT** — Whisper (accuracy) or Vosk (speed), no internet required
- **4-Layer NLP** — Exact → Fuzzy → Phonetic → Semantic matching
- **Accent Support** — Optimized for Indian English accents
- **Fuzzy Matching** — Handles speech errors (`"watsapp"` → WhatsApp, `"crome"` → Chrome)
- **Weighted Scoring** — Composite confidence scoring across all matching layers
- **Grammar Templates** — 40+ pre-compiled patterns for common command structures
- **Context State Machine** — Modes: BROWSING, CODING, CHATTING, SYSTEM, FILE_MANAGER

### System & Security
- **System Info** — `"what time is it"`, `"battery status"`, `"system info"`
- **Media Control** — `"volume up"`, `"volume down"`, `"mute"` — native, precise volume control
- **Process Monitor** — `"monitor chrome memory usage"` with background alerts
- **Task Scheduler** — `"schedule shutdown at 10 PM"`
- **4-Gate Safety** — Risk assessment, phonetic safeguards, confirmation prompts
- **Command Sandboxing** — Blocks script execution, remote commands, registry edits
- **Whitelist-Only** — Only pre-approved commands can execute

### Performance & Adaptability
- **Hybrid STT** — Auto-switches models based on confidence scores
- **Intent Pre-Classification** — 30+ patterns for instant categorization (30-50% faster)
- **Threaded Execution** — Non-blocking command execution with priority queue
- **Interruptible TTS** — Stop speech instantly when you start talking
- **Startup Prewarmer** — Pre-loads models for instant first-command response
- **Command Learning** — Learns pronunciation corrections and app preferences
- **Usage Analytics** — Offline tracking of command patterns for optimization

---

## Requirements

| Requirement | Details |
|-------------|---------|
| **OS** | Windows 10 / 11 |
| **Python** | 3.8 or higher |
| **Hardware** | Microphone (built-in or external) |
| **RAM** | 4 GB minimum (8 GB recommended) |
| **Storage** | ~500 MB (including Whisper model) |
| **Internet** | NOT required (offline-first design) |

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Nandan-k-s-27/varna-voice-assistant.git
cd varna-voice-assistant
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. First Run (One-Time Model Download)

On first run, VARNA downloads the Whisper model (~150 MB). This is a one-time download:

```bash
python main.py
```

### Optional: Use Vosk Instead

For faster startup with smaller models:

1. Download a Vosk model from [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models)
2. Extract to `models/vosk-model-small-en-us/`
3. Update `config.json`: `"engine": "vosk"`

---

## Usage

```bash
python main.py
```

Speak commands naturally — VARNA understands flexible language.

### Example Commands

| Category | Command | What it does |
|----------|---------|-------------|
| **App Control** | `"open chrome"` | Smart open — restores if minimized, focuses if running, launches if not |
| **App Control** | `"close spotify"` | Finds running process and terminates it |
| **Window** | `"switch to vscode"` | Brings VS Code to front |
| **Window** | `"minimize edge"` | Minimizes Microsoft Edge |
| **Tab** | `"new tab"` / `"close tab"` | Opens/closes browser tab |
| **Tab** | `"go to tab 3"` | Switches to 3rd tab |
| **Typing** | `"type hello world"` | Types text in any active window |
| **Search** | `"search React hooks"` | In-tab if browser active, else opens new tab |
| **NLP** | `"can you open notepad"` | Strips fillers → opens Notepad |
| **Chain** | `"open edge and search React"` | Opens Edge, then searches |
| **Selection** | `"select all text"` | Ctrl+A in active window |
| **Scroll** | `"scroll little down"` | Sensitivity-aware scrolling |
| **Navigate** | `"go back"` / `"go forward"` | Alt+Left/Right in browser/explorer |
| **Navigate** | `"go to D drive"` | Opens D: drive in file explorer |
| **Clipboard** | `"read clipboard"` | Reads clipboard content aloud |
| **Screenshot** | `"screenshot as Bug1"` | Saves `Bug1.png` to Desktop |
| **Key Press** | `"press enter"` / `"undo"` | Press Enter / Ctrl+Z |
| **System** | `"battery status"` | Reports battery percentage |
| **Volume** | `"volume up"` / `"volume down"` | Adjusts system volume (native, reliable) |
| **Volume** | `"mute"` / `"unmute"` | Toggles system mute |
| **System** | `"shutdown system"` | Shuts down (with confirmation) |
| **Macro** | `"whenever I say X do Y"` | Creates a custom macro |
| **Context** | `"close it"` / `"repeat"` | Closes last app / repeats last command |
| **Exit** | `"goodbye"` / `"stop listening"` | Exits VARNA |

---

## Configuration

All settings are in `config.json`:

```json
{
    "version": "2.3",
    "stt": {
        "engine": "whisper",
        "whisper_model": "base",
        "language": "en"
    },
    "nlp": {
        "fuzzy_threshold": 0.65,
        "semantic_threshold": 0.65,
        "phonetic_enabled": true,
        "use_grammar_patterns": true
    },
    "tts": {
        "rate": 190,
        "volume": 1.0
    },
    "performance": {
        "mode": "balanced",
        "auto_switch": true,
        "prewarm_on_startup": false
    }
}
```

### STT Engine Options

| Engine | Model | Accuracy | Speed | Size |
|--------|-------|----------|-------|------|
| `whisper` (default) | `tiny` | ★★★ | ★★★★★ | ~75 MB |
| `whisper` | `base` | ★★★★ | ★★★★ | ~150 MB |
| `whisper` | `small` | ★★★★★ | ★★★ | ~500 MB |
| `vosk` | small-en-us | ★★★ | ★★★★★ | ~50 MB |

### Performance Modes

| Mode | Description |
|------|-------------|
| `ultra_fast` | Uses Whisper `tiny` model, lowest latency |
| `balanced` | Uses Whisper `base` model (default) |
| `accuracy` | Uses Whisper `small` model, best recognition |

---

## Project Structure

```
varna-voice-assistant/
├── main.py                  # Entry point — listening loop & command handlers
├── listener.py              # Microphone capture + STT transcription
├── parser.py                # 21-step command matching pipeline
├── executor.py              # Safe PowerShell command execution
├── speaker.py               # Text-to-speech (pyttsx3) with async queue
├── context.py               # Session state machine + command history
├── monitor.py               # Background process memory monitoring
├── macros.py                # User-defined macro manager
├── tray.py                  # System tray icon + floating overlay
├── window_manager.py        # Smart window control (pygetwindow)
├── app_manager.py           # Universal app scanner & launcher
├── stt_engine.py            # Multi-engine offline STT (Whisper/Vosk)
├── command_safety.py        # 4-gate safety architecture
├── command_sandbox.py       # Security sandboxing layer
├── confidence_response.py   # Tiered response based on confidence
├── smart_recovery.py        # Self-healing failure recovery
├── system_optimizer.py      # System optimization commands
├── threaded_executor.py     # Non-blocking execution layer
├── prewarmer.py             # Startup resource preloader
├── usage_analytics.py       # Offline usage tracking
├── debug_varna.py           # Standalone diagnostic tool
├── test_safety.py           # Safety architecture test suite
├── config.json              # Centralized configuration
├── commands.json            # Whitelisted command definitions
├── requirements.txt         # Python dependencies
├── nlp/                     # Enhanced NLP package
│   ├── __init__.py          # NLP API + layered matching orchestration
│   ├── normalizer.py        # Filler removal, accent correction
│   ├── fuzzy_matcher.py     # Fuzzy + phonetic string matching
│   ├── semantic_matcher.py  # ML-based semantic similarity
│   ├── grammar_matcher.py   # Template-based grammar patterns
│   ├── scoring_engine.py    # Weighted composite scoring
│   ├── intent_router.py     # Intent pre-classification
│   └── user_adaptation.py   # User preference learning
└── utils/                   # Utility modules
    ├── __init__.py
    ├── logger.py            # Centralized logging
    └── timing.py            # Performance timing utilities
```

---

## Troubleshooting

### Run Diagnostics

```bash
python debug_varna.py
```

This checks:
- Microphone hardware detection
- All dependency installations
- Audio capture test
- STT engine availability

### Common Issues

| Problem | Solution |
|---------|----------|
| No microphone detected | Check audio settings, install `PyAudio` |
| Slow first command | Enable `prewarm_on_startup` in `config.json` |
| Poor recognition | Switch to `"whisper_model": "small"` for better accuracy |
| High CPU usage | Set `"mode": "ultra_fast"` in performance config |
| Import errors | Run `pip install -r requirements.txt` again |

---

## Version History

| Version | Highlights |
|---------|-----------|
| **v2.3** | Code cleanup, version unification, bug fixes, documentation overhaul |
| **v2.2** | Adaptive Intelligence — hybrid STT, command learning, intent routing, threaded execution, smart recovery, sandboxing, interruptible TTS, analytics |
| **v2.1** | Intelligent Scoring — weighted scoring engine, STT performance modes, startup prewarmer, grammar patterns, context state machine, rapidfuzz |
| **v2.0** | Offline STT — Whisper/Vosk offline speech, phonetic + semantic matching, async TTS queue, config system |
| **v1.6** | Smarter NLP (60+ fillers), context commands, 40+ key press commands, diagnostics |
| **v1.5** | Universal App Manager — open/close ANY app, text selection, scrolling, drive/folder nav, clipboard history |
| **v1.4** | Window intelligence, voice typing, tab control, flexible NLP, smart search, natural chains |
| **v1.3** | Custom macros, clipboard, smart screenshot, file search, tray UI |
| **v1.2** | Context tracking, confirmation layer, task scheduler, process monitoring |
| **v1.1** | Parameterized commands, command chaining, developer mode |
| **v1.0** | Core assistant — static commands, TTS, STT |

---

## Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "feat: add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## Author

**Nandan K S** — [GitHub](https://github.com/Nandan-k-s-27)

---

<p align="center">
  <b>🌻 VARNA v2.3</b> — Your voice, your control, your privacy.<br/>
  <i>No cloud. No subscriptions. No data collection. Just you and your PC.</i>
</p>
