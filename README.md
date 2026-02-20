# VARNA Voice Assistant

**VARNA (Voice Activated Responsive Network Assistant)** is a secure, **fully offline** Windows desktop voice assistant. It uses **Whisper/Vosk** for high-accuracy offline STT and pyttsx3 for TTS feedback, featuring a robust whitelist-based execution system with window intelligence, **intelligent NLP** with weighted scoring and semantic understanding, and natural language processing.

## Features

### v2.2 — Adaptive Intelligence + Self-Healing (Latest)
- **Hybrid STT Confidence Switching**: Automatic fallback when recognition confidence is low.
  - Extracts confidence from Whisper's `avg_logprob` values.
  - Falls back to base model when confidence < 0.6 for better accuracy.
- **Command Learning Memory**: Learns from user behavior without ML.
  - Stores pronunciation corrections ("crome" → "chrome").
  - Tracks app preferences (time-of-day patterns, frequency).
  - Phrase shortcuts for power users.
- **Intent Pre-Classification Router**: 30-50% faster NLP processing.
  - 30+ pre-compiled patterns for instant command categorization.
  - Skips heavy semantic matching for obvious commands.
  - Categories: APP_CONTROL, SEARCH, NAVIGATION, TYPING, SYSTEM, etc.
- **Threaded Execution Layer**: Non-blocking command execution.
  - Priority queue with parallel TTS preparation.
  - Background execution with callbacks.
- **Smart Failure Recovery**: Self-healing error handling.
  - Auto-rescan apps when app not found.
  - Intelligent suggestions based on intent.
  - Graceful degradation for execution errors.
- **Confidence-Based Tiered Response**: Adaptive execution based on match confidence.
  - >90%: Execute immediately.
  - 70-90%: Execute with confirmation message.
  - 50-70%: Ask user to confirm.
  - <50%: Suggest alternatives.
- **Enhanced Context State Machine**: Full command history with undo support.
  - Stores command records with undo handlers.
  - Entity substitution ("it", "that", "this").
  - `get_repeat_commands()` for recent history.
- **Background System Optimization**: System management commands.
  - "optimize system" → clears temp files, identifies resource hogs.
  - CPU/memory process monitoring.
- **Command Sandboxing Layer**: Security validation for dangerous commands.
  - Blocks script execution, remote commands, registry modification.
  - Path validation, entity injection prevention.
  - Whitelist-based confirmation for dangerous patterns.
- **Interruptible TTS**: Stop speech when user speaks.
  - `interrupt()` method for immediate speech stop.
  - `on_audio_detected()` callback for listener integration.
- **Offline Usage Analytics**: Privacy-first usage tracking.
  - Command frequency, success rates, time patterns.
  - Priority boost for frequently-used commands.
  - Session statistics logged to `logs/analytics.json`.

### v2.1 — Intelligent Scoring + Performance Optimization
- **Weighted Intent Scoring**: Intelligent command matching using composite scoring.
  - Formula: `exact×1.0 + fuzzy×0.6 + phonetic×0.5 + semantic×0.8 + context×0.3 + grammar×0.7`
  - Dynamic confidence thresholds based on input complexity.
  - Learning from user corrections via `user_corrections.json`.
- **STT Performance Modes**: Adaptive model selection for speed vs accuracy.
  - **Ultra Fast**: Whisper tiny model for lowest latency.
  - **Balanced**: Whisper base model (default).
  - **Accuracy**: Whisper small model for best recognition.
  - Auto-switch to tiny model when CPU > 70%.
- **Startup Prewarmer**: Eliminates first-command delay.
  - Pre-loads STT engine, semantic model, grammar patterns at startup.
  - Resources ready before you speak.
- **Grammar Pattern Recognition**: 40+ pre-compiled command templates.
  - Regex-based extraction of app names, queries, numbers.
  - Handles complex patterns like "search youtube for X" or "go to tab N".
- **Context State Machine**: App-aware command suggestions.
  - Modes: BROWSING, CODING, CHATTING, SYSTEM, FILE_MANAGER.
  - Context bonuses boost relevant commands.
- **Latency Measurement**: End-to-end performance tracking.
  - Pipeline metrics: mic → STT → NLP → exec → TTS times.
  - Bottleneck identification for optimization.
- **RapidFuzz Integration**: 10x faster fuzzy matching than difflib.

### v2.0 — Offline STT + Layered NLP
- **True Offline STT**: Whisper or Vosk for completely offline speech recognition.
  - No internet required — works in airplane mode.
  - Configurable: choose between Whisper (accuracy) or Vosk (speed).
  - Automatic Google fallback if offline engines unavailable.
- **Layered NLP Pipeline**: Multi-tier command matching for maximum accuracy.
  - Exact match → Fuzzy matching → Phonetic matching → Semantic similarity.
  - Phonetic matching handles pronunciation variants ("crome" → "chrome").
  - Semantic matching understands paraphrases ("launch browser" → "open chrome").
- **Enhanced Configuration**: `config.json` for all tunable parameters.
  - STT engine selection, NLP thresholds, TTS settings.
  - Wake words, timeouts, and performance options.
- **Async TTS Queue**: Non-blocking speech with proper queue management.
  - `say_async()` returns immediately, speech plays in background.
  - Queue management: clear, pause, resume speech.
- **Performance Improvements**: Faster startup and response times.
  - Lazy model loading, pre-compiled patterns.
  - Parse result caching for repeated commands.

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

### v1.6 — Smarter NLP + Context Awareness + Speed
- **Natural Language (60+ fillers)**: `"can you help me to open edge"` / `"i want to close chrome"` → just works.
- **Typing Bug Fix**: `"type the quick brown fox"` correctly preserves `"the"` (not stripped by NLP).
- **Context Commands**: `"repeat"` / `"do it again"` / `"close this"` / `"minimize this"` / `"maximize this"`.
- **Fuzzy Window Switching**: `"switch to antigravity"` → fuzzy-matches against all open window titles.
- **40+ Key Press Commands**: `"select all text"` / `"delete"` / `"save"` / `"press space"` / `"arrow up"` / etc.
- **Faster Processing**: Async TTS (190 wpm), pre-compiled regex patterns, lower fuzzy threshold (65%).
- **System Diagnostics**: Say "run diagnostics" or "check system" for internal self-tests.
- **Standalone Debugger**: Includes `debug_varna.py` for troubleshooting hardware/deps.
- **More Exit Phrases**: `"stop listening"` / `"that's all"` / `"i'm done"` / `"go to sleep"`.

### v1.5 — Universal App Control + Advanced Interactions
- **Open ANY App**: `"open whatsapp"` / `"open spotify"` — scans your entire PC.
  - Scans Start Menu shortcuts, Program Files, AppData, and UWP Store apps.
  - Fuzzy matches speech errors: `"open watsapp"` → finds WhatsApp.
- **Close ANY App**: `"close whatsapp"` → finds running process via `psutil` and terminates.
- **App Management**: `"scan apps"` / `"list installed apps"`.
- **Text Selection**: `"select good"` → finds and highlights exact word. `"select line"` / `"select next 3 words"` / `"go to line 10"`.
- **Numbered Tab Navigation**: `"go to tab 3"` / `"first tab"` → Ctrl+N.
- **Smart Scrolling**: `"scroll down"` / `"scroll little up"` / `"scroll a lot down"` / `"scroll to top"`. Sensitivity-aware.
- **Browser/Explorer Navigation**: `"go back"` / `"go forward"` / `"refresh"` — works in browsers AND File Explorer.
- **Drive & Folder Navigation**: `"go to D drive"` / `"go to this PC"` / `"go to downloads"` — opens drives and known folders.
- **Search Result Clicking**: `"open result 1"` / `"open first result"` — Tab-navigates to Nth search result.
- **Clipboard History**: `"open clipboard"` (Win+V) / `"paste 3rd item"` — access Windows clipboard history.
- **Key Press Commands**: `"press enter"` / `"send it"` / `"undo"` / `"redo"` / `"copy this"` / `"paste it"`.
- **WhatsApp Navigation**: `"open 2nd chat"` → arrow-navigates to chat. `"search contact john"` → finds contact. Then `"type hello"` + `"send it"` to message.

### v1.4 — Smart Application Control + Natural Parsing
- **Window Intelligence**: Smart open (restores if minimized, focuses if running, launches if not).
  - `"switch to chrome"` / `"minimize edge"` / `"maximize vscode"` / `"show desktop"`.
  - `"open new chrome window"` → forces a new instance.
- **Voice Typing**: `"type hello world"` → types text in any active application.
- **Tab Control**: `"close tab"` / `"new tab"` / `"next tab"` / `"previous tab"` / `"reopen tab"`.
- **Flexible NLP** (no LLM):
  - **60+ filler phrases**: `"can you help me to open notepad"` → `"open notepad"`.
  - **Fuzzy matching**: Handles speech recognition errors (65%+ similarity).
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
| **Selection** 🆕 | "select good" | Finds and highlights the word |
| **Scroll** 🆕 | "scroll little down" | Sensitivity-aware scrolling |
| **Navigate** 🆕 | "go back" / "go forward" | Alt+Left/Right in browser/explorer |
| **Result** 🆕 | "open result 1" | Opens first search result |
| **Clipboard** 🆕 | "paste 3rd item" | Pastes from clipboard history |
| **Key Press** 🆕 | "press enter" / "send it" | Press Enter to send/search |
| **System** | "shutdown system" | Shuts down (with confirmation) |

For the full list of **160+ commands**, see [`COMMANDS.md`](COMMANDS.md).

## Repository Structure

| File | Purpose |
|------|---------|
| `main.py` | Entry point — listening loop, command routing, all handlers |
| `listener.py` | Speech recognition + yes/no confirmation |
| `parser.py` | 20-step command matching pipeline with NLP preprocessing |
| `executor.py` | Safe PowerShell execution |
| `speaker.py` | Text-to-speech with async queue + interruptible TTS 🆕 |
| `context.py` | Session state + browser tracking + command history + undo support 🆕 |
| `monitor.py` | Background process monitoring |
| `macros.py` | Custom macro manager |
| `tray.py` | System tray icon + floating overlay |
| `window_manager.py` | Smart window control (pygetwindow) + AppManager fallback |
| `nlp.py` | Legacy NLP (use `nlp/` package for v2.0) |
| `stt_engine.py` | Offline STT engine (Whisper/Vosk) + hybrid confidence fallback 🆕 |
| `config.json` | Centralized configuration with v2.2 settings 🆕 |
| `nlp/` | Enhanced NLP package |
| `nlp/__init__.py` | Unified NLP API with layered matching |
| `nlp/normalizer.py` | Filler removal, intent extraction |
| `nlp/fuzzy_matcher.py` | Fuzzy + phonetic matching |
| `nlp/semantic_matcher.py` | ML-based semantic similarity |
| `nlp/scoring_engine.py` | Weighted intent scoring with learning |
| `nlp/grammar_matcher.py` | Template-based command recognition |
| `nlp/intent_router.py` | Intent pre-classification for fast routing 🆕 |
| `nlp/user_adaptation.py` | Command learning memory 🆕 |
| `prewarmer.py` | Startup resource preloader |
| `utils/timing.py` | Performance timing utilities |
| `threaded_executor.py` | Non-blocking execution with priority queue 🆕 |
| `smart_recovery.py` | Self-healing failure recovery 🆕 |
| `usage_analytics.py` | Offline usage tracking 🆕 |
| `command_sandbox.py` | Security validation layer 🆕 |
| `confidence_response.py` | Tiered response based on confidence 🆕 |
| `system_optimizer.py` | Background system optimization 🆕 |
| `app_manager.py` | Universal app scan, index, fuzzy match, launch, close |
| `apps.json` | Auto-generated installed app cache |
| `commands.json` | Structured command whitelist |
| `macros.json` | User-defined macros storage |

## Architecture

```
🎤 Microphone → 📝 Offline STT (Whisper/Vosk) → 🧹 NLP Pipeline → 🧠 Parser → 🛡 Whitelist
                         ↓                            ↓
                   [Google Fallback]           ┌──────┴──────┐
                                              ↓              ↓
                                        Fuzzy Match   Semantic Match
                                        + Phonetic     (ML-based)
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
| v1.5 | **Universal App Manager** — open/close ANY app, text selection, smart scrolling, drive/folder nav, clipboard history, WhatsApp nav, 160+ commands |
| v1.6 | Smarter NLP (60+ fillers), context commands, 40+ key press commands, diagnostics |
| v2.0 | **Offline STT + Layered NLP** — Whisper/Vosk offline speech, phonetic + semantic matching, async TTS queue, config system |
| v2.1 | **Intelligent Scoring + Performance** — Weighted scoring engine, STT performance modes, startup prewarmer, grammar patterns, context state machine, rapidfuzz integration |
| v2.2 | **Adaptive Intelligence + Self-Healing** — Hybrid STT confidence switching, command learning memory, intent pre-classification, threaded execution, smart recovery, confidence-based responses, command sandboxing, interruptible TTS, usage analytics |

## Installation

### Standard Installation
```bash
git clone https://github.com/Nandan-k-s-27/varna-voice-assistant.git
cd varna-voice-assistant
pip install -r requirements.txt
```

### First Run (Model Download)
On first run, VARNA will download the Whisper model (~150MB). This is a one-time download:
```bash
python main.py
```

### Optional: Use Vosk Instead (Lighter)
If you prefer faster startup with smaller models:
1. Download a Vosk model from https://alphacephei.com/vosk/models
2. Extract to `models/vosk-model-small-en-us/`
3. Update `config.json`: `"engine": "vosk"`

## Configuration

VARNA v2.1 uses `config.json` for all settings:

```json
{
  "stt": {
    "engine": "whisper",       // "whisper", "vosk", or "hybrid"
    "whisper_model": "base"    // "tiny", "base", "small", "medium"
  },
  "nlp": {
    "fuzzy_threshold": 0.70,   // 0.0-1.0, lower = more lenient
    "semantic_threshold": 0.65,
    "use_semantic_fallback": true,
    "use_grammar_patterns": true,    // 🆕 Enable 40+ grammar templates
    "min_confidence": 0.45           // 🆕 Minimum score threshold
  },
  "performance": {
    "mode": "balanced",        // 🆕 "ultra_fast", "balanced", "accuracy"
    "auto_switch": true,       // 🆕 Switch to tiny model when CPU > 70%
    "prewarm_on_startup": true // 🆕 Pre-load models at startup
  },
  "tts": {
    "rate": 190,               // Words per minute
    "volume": 1.0
  }
}
```
