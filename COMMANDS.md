# VARNA v2.2 — Full Command List

All commands supported by VARNA v2.2, organized by category.

---

## 🆕 v2.2 — Adaptive Intelligence + Self-Healing

### Intent Pre-Classification
VARNA v2.2 uses a fast intent router that categorizes commands before NLP processing:

| Category | Example Patterns | Skip Semantic |
|----------|------------------|---------------|
| APP_CONTROL | open, close, launch, start | Yes |
| SEARCH | search, find, look up, google | Yes |
| NAVIGATION | go to, switch to, navigate | Yes |
| TYPING | type, write, enter text | Yes |
| TAB_CONTROL | new tab, close tab, next tab | Yes |
| WINDOW | minimize, maximize, restore | Yes |
| SYSTEM | shutdown, restart, lock | Yes |
| MEDIA | play, pause, volume | Yes |
| CLIPBOARD | copy, paste, clipboard | Yes |
| FILE | create file, delete file, rename | Yes |
| UNKNOWN | Fallback to full NLP | No |

### Confidence-Based Response Tiers

| Confidence | Action | Example |
|------------|--------|---------|
| >90% | Execute immediately | "open chrome" → Opens Chrome |
| 70-90% | Execute with confirmation | "open chrom" → "Opening Chrome" |
| 50-70% | Ask user to confirm | "Did you mean 'open chrome'?" |
| <50% | Suggest alternatives | "Did you mean: chrome, code, edge?" |

### Command Learning Memory
VARNA learns from your corrections and preferences:

- **Pronunciations**: "crome" → "chrome" after 2 corrections
- **App Preferences**: Learns which apps you use at different times
- **Phrase Shortcuts**: "dev mode" → "open vscode and open terminal"

### Smart Failure Recovery

| Failure Type | Auto-Recovery |
|--------------|---------------|
| App Not Found | Auto-rescan installed apps |
| Command Not Recognized | Suggest similar commands |
| Execution Error | Graceful degradation + log |
| Timeout | Retry with increased timeout |

### New v2.2 Commands

| # | Command | Action |
|---|---------|--------|
| — | optimize system | Clears temp files, shows resource hogs |
| — | show cpu hogs | Lists top 5 CPU-consuming processes |
| — | show memory hogs | Lists top 5 memory-consuming processes |
| — | clear temp files | Clears Windows temp directory |
| — | undo | Undoes last command (if undo handler exists) |
| — | stop / stop talking | Interrupts current speech |

---

## 🆕 v2.1 — Intelligent Features

### Weighted Intent Scoring
VARNA now uses an intelligent scoring engine to match commands:

| Signal | Weight | Description |
|--------|--------|-------------|
| Exact Match | 1.0 | Direct command match |
| Semantic | 0.8 | ML-based meaning similarity |
| Grammar | 0.7 | Template pattern match |
| Fuzzy | 0.6 | Character similarity (RapidFuzz) |
| Phonetic | 0.5 | Pronunciation match |
| Context | 0.3 | App-aware bonus |

**Learning**: Corrections are saved to `user_corrections.json` and boost future matches.

### STT Performance Modes

| Mode | Model | Use Case |
|------|-------|----------|
| `ultra_fast` | Whisper tiny | Low-latency, limited accuracy |
| `balanced` | Whisper base | Default, good balance |
| `accuracy` | Whisper small | Best recognition, slower |

**Auto-Switch**: When CPU > 70%, automatically switches to tiny model for responsiveness.

### Context-Aware Modes

| Mode | Triggered By | Boosted Commands |
|------|-------------|------------------|
| BROWSING | Chrome, Edge, Firefox | search, tab, scroll, bookmark |
| CODING | VS Code, IntelliJ | debug, run, git, terminal |
| FILE_MANAGER | Explorer, Total Commander | copy, paste, rename, delete |
| CHATTING | WhatsApp, Discord, Slack | type, send, emoji |
| SYSTEM | Default | open, close, volume |

---

## 1. Static Commands (36)

| # | Command | Action |
|---|---------|--------|
| 1 | open notepad | Smart opens Notepad (restores if minimized, focuses if running) |
| 2 | open chrome | Smart opens Chrome |
| 3 | open firefox | Smart opens Firefox |
| 4 | open edge | Smart opens Edge |
| 5 | open calculator | Smart opens Calculator |
| 6 | open paint | Smart opens Paint |
| 7 | open file explorer | Opens File Explorer |
| 8 | open task manager | Opens Task Manager |
| 9 | open command prompt | Opens CMD |
| 10 | open powershell | Opens PowerShell |
| 11 | open vscode | Smart opens VS Code |
| 12 | open word | Smart opens MS Word |
| 13 | open excel | Smart opens Excel |
| 14 | open powerpoint | Smart opens PowerPoint |
| 15 | open downloads | Opens Downloads folder |
| 16 | open documents | Opens Documents folder |
| 17 | open desktop | Opens Desktop folder |
| 18 | close notepad | Closes Notepad |
| 19 | close chrome | Closes Chrome |
| 20 | close firefox | Closes Firefox |
| 21 | close edge | Closes Edge |
| 22 | close calculator | Closes Calculator |
| 23 | close paint | Closes Paint |
| 24 | system info | System specs |
| 25 | battery status | Battery % |
| 26 | ip address | Local IPv4 |
| 27 | disk space | Drive free space |
| 28 | list processes | Top 10 CPU processes |
| 29 | current time | Current time |
| 30 | current date | Current date |
| 31 | lock screen | Locks session |
| 32 | empty recycle bin | Clears Recycle Bin ⚠️ |
| 33 | screenshot | Screenshot to Desktop |
| 34 | increase volume | Raises volume |
| 35 | decrease volume | Lowers volume |
| 36 | mute volume | Mutes volume |

---

## 2. Parameterized Commands (4)

| # | Command | Example | Action |
|---|---------|---------|--------|
| 37 | search `{query}` | "search React hooks" | Google search (browser-aware, in-tab if active) |
| 38 | open website `{url}` | "open website github.com" | Opens URL |
| 39 | search youtube `{query}` | "search youtube Python" | YouTube search (browser-aware) |
| 40 | open folder `{path}` | "open folder C:\Users" | Opens folder |

---

## 3. Command Chains (4)

| # | Command | Steps |
|---|---------|-------|
| 41 | open vscode and my react project | Opens VS Code → React project |
| 42 | start my backend | Opens PowerShell → cd → npm start |
| 43 | start my frontend | Opens PowerShell → cd → npm start |
| 44 | start full stack | Backend → Wait → Frontend |

---

## 4. Developer Mode (12)

| # | Command | Action |
|---|---------|--------|
| 45 | run npm start | Runs `npm start` |
| 46 | run npm install | Runs `npm install` |
| 47 | pull latest from git | `git pull origin main` |
| 48 | git status | Shows git status |
| 49 | open git bash | Opens Git Bash |
| 50 | kill port 3000 | Kills process on port |
| 51 | kill port 5000 | Kills on port 5000 |
| 52 | kill port 8080 | Kills on port 8080 |
| 53 | show running ports | Lists listening ports |
| 54 | show node processes | Lists Node.js processes |
| 55 | kill all node | Kills all Node.js ⚠️ |
| 56 | open terminal here | Opens PowerShell |

---

## 5. System Commands (6) — v1.2

| # | Command | Action |
|---|---------|--------|
| 57 | shutdown system | Shuts down ⚠️ |
| 58 | restart system | Restarts ⚠️ |
| 59 | log off | Logs off ⚠️ |
| 60 | cancel scheduled shutdown | Removes task |
| 61 | cancel scheduled restart | Removes task |
| 62 | show scheduled tasks | Lists VARNA tasks |

---

## 6. Scheduler Commands (2) — v1.2

| # | Command | Example | Action |
|---|---------|---------|--------|
| 63 | schedule shutdown `{time}` | "schedule shutdown at 10 PM" | Scheduled shutdown ⚠️ |
| 64 | schedule restart `{time}` | "schedule restart in 30 minutes" | Scheduled restart ⚠️ |

---

## 7. Process Monitoring (3) — v1.2

| # | Command | Example | Action |
|---|---------|---------|--------|
| 65 | monitor `{process}` | "monitor chrome memory usage" | Background monitoring |
| 66 | stop monitoring | "stop monitoring" | Stops monitor |
| 67 | check process `{name}` | "check process node" | One-shot status |

---

## 8. Context-Aware Commands (10) — v1.2

| # | Command | Action |
|---|---------|--------|
| 68–74 | close it, open it again, go back, etc. | Context-based actions |

---

## 9. Clipboard Commands (4) — v1.3

| # | Command | Action |
|---|---------|--------|
| 75 | read clipboard | Speaks clipboard contents |
| 76 | what did i copy | Reads clipboard |
| 77 | read what i copied | Reads clipboard |
| 78 | clipboard | Reads clipboard |

---

## 10. Smart Screenshot (3) — v1.3

| # | Command | Action |
|---|---------|--------|
| 79 | screenshot as `{name}` | Named screenshot to Desktop |
| 80 | take screenshot as `{name}` | Named screenshot |
| 81 | save screenshot as `{name}` | Named screenshot |

---

## 11. File Search (dynamic) — v1.3

| # | Command | Example | Action |
|---|---------|---------|--------|
| 82 | find `{desc}` | "find PDF downloaded yesterday" | Searches common folders |
| 83 | locate `{desc}` | "locate report" | Searches by name |

---

## 12. Custom Macros (dynamic) — v1.3

| # | Command | Example | Action |
|---|---------|---------|--------|
| 84 | whenever I say `{name}` do `{steps}` | "whenever I say focus mode do open vscode and open chrome" | Records macro |
| 85 | `{macro name}` | "focus mode" | Plays saved macro |
| 86 | list macros | "list macros" | Lists all macros |
| 87 | delete macro `{name}` | "delete macro focus mode" | Deletes macro |

---

## 13. Window Control (dynamic) — 🆕 v1.4

| # | Command | Example | Action |
|---|---------|---------|--------|
| 88 | switch to `{app}` | "switch to chrome" | Focuses/restores the app |
| 89 | minimize `{app}` | "minimize edge" | Minimizes the app |
| 90 | maximize `{app}` | "maximize vscode" | Maximizes the app |
| 91 | restore `{app}` | "restore notepad" | Restores minimized app |
| 92 | show desktop | "show desktop" | Win+D — minimize all |
| 93 | minimize all | "minimize all" | Same as show desktop |
| 94 | open new `{app}` window | "open new chrome window" | Forces new instance |
| 95 | restore last window | "restore last window" | Restores last app |

**Smart Open Logic** (applies to all "open X" commands):
- If app is running & minimized → **Restore**
- If app is running & active → **Focus**
- If app is not running → **Launch new instance**

---

## 14. Tab Control (5) — 🆕 v1.4

| # | Command | Action |
|---|---------|--------|
| 96 | close tab | Ctrl+W — closes current tab |
| 97 | new tab | Ctrl+T — opens new tab |
| 98 | next tab | Ctrl+Tab — next tab |
| 99 | previous tab | Ctrl+Shift+Tab — prev tab |
| 100 | reopen tab | Ctrl+Shift+T — reopens last tab |

---

## 15. Voice Typing (dynamic) — 🆕 v1.4

| # | Command | Example | Action |
|---|---------|---------|--------|
| 101 | type `{text}` | "type hello world" | Types text in active window |
| 102 | write `{text}` | "write good morning" | Types text |
| 103 | enter `{text}` | "enter username admin" | Types text |

---

## 16. Smart Search Routing — 🆕 v1.4

If a browser is currently active, "search X" uses **Ctrl+L → type → Enter** to search in the current tab instead of opening a new one.

---

## 17. Flexible NLP — 🆕 v1.4 (automatic)

All commands now support natural language:
- **Filler removal**: "can you help me to open notepad" → "open notepad"
- **60+ filler phrases**: "i want to", "help me", "could you please", etc.
- **Fuzzy matching**: Handles speech recognition errors (65%+ similarity)
- **Intent extraction**: "launch chrome" → understood as "open chrome"
- **Synonym support**: "bring up", "fire up", "start" all map to "open"

---

## 18. Natural Chains — 🆕 v1.4 (automatic)

Say multiple commands in one sentence:
- "open edge **and** search React hooks" → opens Edge, then searches
- "open notepad **then** type hello world" → opens Notepad, then types

## 19. Universal App Manager — 🆕 v1.5

### Open ANY Installed App

| # | Command | Example | Action |
|---|---------|---------|--------|
| 104 | open `{any app}` | "open whatsapp" | Scans index → launches .exe or UWP |
| 105 | open `{misspelled}` | "open watsapp" | Fuzzy match → finds WhatsApp |
| 106 | open `{store app}` | "open spotify" | UWP protocol launch |

### Close ANY Running App

| # | Command | Example | Action |
|---|---------|---------|--------|
| 107 | close `{any app}` | "close whatsapp" | psutil → finds & terminates process |
| 108 | close `{any app}` | "close spotify" | Works for any running process |

### App Management

| # | Command | Action |
|---|---------|--------|
| 109 | scan apps | Scans PC for installed apps → builds/rebuilds index |
| 110 | refresh app list | Same as scan apps |
| 111 | list installed apps | Shows all indexed apps |
| 112 | list apps | Same as list installed apps |

**How It Works:**
1. At startup, scans Start Menu shortcuts, Program Files, AppData, and UWP Store apps
2. Builds searchable index cached in `apps.json`
3. Fuzzy matches spoken names (handles speech errors like "watsapp" → "WhatsApp")
4. If multiple similar matches found → asks user to be specific
5. Say "scan apps" to rebuild the index if you install new applications

---

## 🆕 v1.5 — Text Selection (7 commands)

| # | Command | Example | Action |
|---|---------|---------|--------|
| 113 | select `{word}` | "select good" | Ctrl+F → finds and highlights word |
| 114 | select line | "select line" | Home → Shift+End |
| 115 | select word | "select word" | Ctrl+Shift+Left |
| 116 | select next `{N}` words | "select next 3 words" | Ctrl+Shift+Right × N |
| 117 | select previous `{N}` words | "select previous 2 words" | Ctrl+Shift+Left × N |
| 118 | go to line `{N}` | "go to line 10" | Ctrl+G → type line number |
| 119 | select all | "select all" | Ctrl+A |

---

## 🆕 v1.5 — Numbered Tab Navigation (3+ commands)

| # | Command | Example | Action |
|---|---------|---------|--------|
| 120 | go to tab `{N}` | "go to tab 3" | Ctrl+3 |
| 121 | `{ordinal}` tab | "first tab", "third tab" | Ctrl+N |
| 122 | tab `{N}` | "tab 5" | Ctrl+5 |

---

## 🆕 v1.5 — Smart Scrolling (8 commands)

| # | Command | Example | Action |
|---|---------|---------|--------|
| 123 | scroll down | "scroll down" | Normal scroll (5 clicks) |
| 124 | scroll up | "scroll up" | Normal scroll up (5 clicks) |
| 125 | scroll little down | "scroll little down" | Small scroll (2 clicks) |
| 126 | scroll little up | "scroll slightly up" | Small scroll up (2 clicks) |
| 127 | scroll a lot down | "scroll a lot down" | Big scroll (15 clicks) |
| 128 | scroll to top | "scroll to top" | Ctrl+Home |
| 129 | scroll to bottom | "scroll to bottom" | Ctrl+End |
| 130 | page down / page up | "page down" | PageDown / PageUp |

---

## 🆕 v1.5 — Browser / Explorer Navigation (6 commands)

| # | Command | Example | Action |
|---|---------|---------|--------|
| 131 | go back | "go back" | Alt+Left — works in browser & File Explorer |
| 132 | go to previous page | "previous page" | Alt+Left |
| 133 | go forward | "go forward" | Alt+Right |
| 134 | refresh / reload | "refresh page" | F5 |
| 135 | go to address bar | "address bar" | Ctrl+L |
| 136 | navigate back/forward | "navigate back" | Alt+Left/Right |
| 137 | go to `{letter}` drive | "go to D drive" | Opens D:\ in File Explorer |
| 138 | open drive `{letter}` | "open drive E" | Opens E:\ in File Explorer |
| 139 | go to this PC | "go to this pc" | Opens This PC (My Computer) |
| 140 | go to `{folder}` | "go to downloads" | Opens known folder (Desktop/Downloads/Documents/Pictures/Music/Videos) |

---

## 🆕 v1.5 — Open Search Results (4 commands)

| # | Command | Example | Action |
|---|---------|---------|--------|
| 137 | open result `{N}` | "open result 1" | Tab-navigates to Nth result → Enter |
| 138 | open first result | "open first result" | Opens 1st search result |
| 139 | open second result | "open second result" | Opens 2nd search result |
| 140 | open `{ordinal}` result | "open third result" | Opens Nth result |

---

## 🆕 v1.5 — Clipboard History (5 commands)

| # | Command | Example | Action |
|---|---------|---------|--------|
| 141 | open clipboard | "open clipboard" | Win+V — opens clipboard history panel |
| 142 | show clipboard | "show clipboard history" | Win+V |
| 143 | paste `{N}`th item | "paste 3rd item" | Win+V → down × (N-1) → Enter |
| 144 | paste `{ordinal}` item | "paste second item" | Pastes 2nd clipboard entry |
| 145 | paste `{ordinal}` copied | "paste third copied" | Same as above |

> **Note:** Requires Windows 10/11 Clipboard History to be enabled:
> Settings → System → Clipboard → Toggle "Clipboard history" ON

---

## 🆕 v1.5 — WhatsApp Navigation (5 commands)

| # | Command | Example | Action |
|---|---------|---------|--------|
| 146 | open `{ordinal}` chat | "open 2nd chat" | Arrow-down × N → Enter |
| 147 | open chat `{N}` | "open chat 5" | Arrow-down × 5 → Enter |
| 148 | open top chat | "open top chat" | Opens most recent chat |
| 149 | search contact `{name}` | "search contact john" | Ctrl+K → type name → Enter |
| 150 | new chat | "new chat" | Ctrl+N → starts new conversation |

**Full flow:**
1. `"open whatsapp"` → launches WhatsApp
2. `"open 2nd chat"` → opens 2nd chat
3. `"type hello how are you"` → types message
4. `"send it"` → presses Enter to send

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ⚠️ | Dangerous — requires voice confirmation |
| 🆕 | New in this version |

## Summary

| Category | Count | Version |
|----------|-------|---------|
| Static | 36 | v1.0 |
| Parameterized | 4 | v1.1 |
| Chains | 4 | v1.1 |
| Developer | 12 | v1.1 |
| System | 6 | v1.2 |
| Scheduler | 2 | v1.2 |
| Monitoring | 3 | v1.2 |
| Context-Aware | 10 | v1.2 |
| Clipboard | 4 | v1.3 |
| Smart Screenshot | 3 | v1.3 |
| File Search | 3+ | v1.3 |
| Custom Macros | 4+ | v1.3 |
| Window Control | 8+ | v1.4 |
| Tab Control | 5 | v1.4 |
| Voice Typing | 3+ | v1.4 |
| NLP + Smart Search | auto | v1.4 |
| Natural Chains | auto | v1.4 |
| Universal App | 9+ | v1.5 |
| **Text Selection** 🆕 | **7** | **v1.5** |
| **Numbered Tabs** 🆕 | **3+** | **v1.5** |
| **Smart Scrolling** 🆕 | **8** | **v1.5** |
| **Browser/Explorer Nav** 🆕 | **10** | **v1.5** |
| **Search Results** 🆕 | **4** | **v1.5** |
| **Clipboard History** 🆕 | **5** | **v1.5** |
| **WhatsApp Nav** 🆕 | **5** | **v1.5** |
| **Key Press (expanded)** 🆕 | **40+** | **v1.6** |
| **Context Commands** 🆕 | **10** | **v1.6** |
| **Weighted Scoring** 🆕 | **auto** | **v2.1** |
| **Grammar Patterns** 🆕 | **40+** | **v2.1** |
| **STT Performance Modes** 🆕 | **3** | **v2.1** |
| **Total** | **~220+** | |

---

## v1.6 Additions

### Expanded Key Press Commands (40+)

| Command | Action |
|---------|--------|
| select all text / select everything | Ctrl+A |
| delete / delete this / delete that | Delete key |
| delete selected / remove this | Delete key |
| copy / copy this / copy that | Ctrl+C |
| paste / paste it / paste here | Ctrl+V |
| cut / cut this / cut that | Ctrl+X |
| undo / undo that | Ctrl+Z |
| redo / redo that | Ctrl+Y |
| save / save this / save file | Ctrl+S |
| press space / space | Space key |
| press up/down/left/right | Arrow keys |
| arrow up/down/left/right | Arrow keys |
| press home / press end | Home/End |
| press tab | Tab key |
| cancel | Escape |

### Context-Aware Commands (v1.6)

| Command | Action |
|---------|--------|
| repeat / do it again / again | Re-executes the last command |
| do that again / one more time | Re-executes the last command |
| run diagnostics / system test | Runs internal self-test on hardware/software |
| close this / close this window | Closes the active foreground window (Alt+F4) |
| minimize this / minimize this window | Minimizes the active window (Win+Down) |
| maximize this / maximize this window | Maximizes the active window (Win+Up) |

### Improved Window Switching (v1.6)

"switch to `{app}`" now uses **fuzzy matching** against all open window titles.
Examples:
- "switch to antigravity" → matches window with "Antigravity" in title
- "switch to code" → matches VS Code window

### Natural Language (v1.6)

60+ filler phrases stripped automatically:
- "can you help me to open edge" → "open edge" ✅
- "i want to close chrome" → "close chrome" ✅
- "would you please minimize this" → "minimize this" ✅
- "hey varna type the quick brown fox" → "type the quick brown fox" ✅

**Typing preserves content**: "type the command" correctly types "the command" (not stripped).

---

## v2.1 Additions

### Startup Prewarmer
First command executes instantly — no cold-start delay:
- STT engine pre-loaded
- Semantic model ready
- Grammar patterns compiled
- App index in memory

### Grammar Pattern Recognition (40+ patterns)
Templates for extracting parameters from natural speech:

| Pattern | Example | Extracted |
|---------|---------|-----------|
| open_app | "open spotify" | app: spotify |
| search_web | "search react hooks" | query: react hooks |
| search_youtube | "search youtube python tutorial" | query: python tutorial |
| go_to_tab | "go to tab 3" | number: 3 |
| scroll_direction | "scroll down a lot" | direction: down, amount: lot |
| type_text | "type hello world" | text: hello world |
| select_word | "select next 5 words" | count: 5 |
| close_app | "close whatsapp" | app: whatsapp |

### Performance Timing
Latency tracking for optimization:
- Mic capture time
- STT processing time
- NLP matching time
- Command execution time
- TTS response time

### RapidFuzz (10x Faster)
Upgraded fuzzy matching from difflib to rapidfuzz:
- Same accuracy, much faster
- Better for large command sets
- Falls back to difflib if not installed

