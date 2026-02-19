# VARNA v1.4 — Full Command List

All commands supported by VARNA v1.4, organized by category.

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
- **Filler removal**: "can you please open notepad for me" → "open notepad"
- **Fuzzy matching**: Handles speech recognition errors (75%+ similarity)
- **Intent extraction**: "launch chrome" → understood as "open chrome"
- **Synonym support**: "bring up", "fire up", "start" all map to "open"

---

## 18. Natural Chains — 🆕 v1.4 (automatic)

Say multiple commands in one sentence:
- "open edge **and** search React hooks" → opens Edge, then searches
- "open notepad **then** type hello world" → opens Notepad, then types

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
| **Total** | **~107+** | |
