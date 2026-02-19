# VARNA v1.3 — Full Command List

All commands supported by VARNA v1.3, organized by category.

---

## 1. Static Commands (36)

| # | Command | Action |
|---|---------|--------|
| 1 | open notepad | Launches Notepad |
| 2 | open chrome | Launches Google Chrome |
| 3 | open firefox | Launches Mozilla Firefox |
| 4 | open edge | Launches Microsoft Edge |
| 5 | open calculator | Launches Calculator |
| 6 | open paint | Launches Microsoft Paint |
| 7 | open file explorer | Opens File Explorer |
| 8 | open task manager | Opens Task Manager |
| 9 | open command prompt | Opens CMD |
| 10 | open powershell | Opens PowerShell |
| 11 | open vscode | Launches Visual Studio Code |
| 12 | open word | Launches MS Word |
| 13 | open excel | Launches MS Excel |
| 14 | open powerpoint | Launches MS PowerPoint |
| 15 | open downloads | Opens Downloads folder |
| 16 | open documents | Opens Documents folder |
| 17 | open desktop | Opens Desktop folder |
| 18 | close notepad | Closes Notepad |
| 19 | close chrome | Closes Chrome |
| 20 | close firefox | Closes Firefox |
| 21 | close edge | Closes Edge |
| 22 | close calculator | Closes Calculator |
| 23 | close paint | Closes Paint |
| 24 | system info | Displays system specs |
| 25 | battery status | Shows battery percentage |
| 26 | ip address | Shows local IPv4 address |
| 27 | disk space | Lists drive free space |
| 28 | list processes | Top 10 CPU processes |
| 29 | current time | Speaks current time |
| 30 | current date | Speaks current date |
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
| 37 | search `{query}` | "search React hooks" | Google search (browser-aware) |
| 38 | open website `{url}` | "open website github.com" | Opens URL (browser-aware) |
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
| 50 | kill port 3000 | Kills process on port 3000 |
| 51 | kill port 5000 | Kills process on port 5000 |
| 52 | kill port 8080 | Kills process on port 8080 |
| 53 | show running ports | Lists listening ports |
| 54 | show node processes | Lists Node.js processes |
| 55 | kill all node | Kills all Node.js ⚠️ |
| 56 | open terminal here | Opens PowerShell |

---

## 5. System Commands (6) — v1.2

| # | Command | Action |
|---|---------|--------|
| 57 | shutdown system | Shuts down PC ⚠️ |
| 58 | restart system | Restarts PC ⚠️ |
| 59 | log off | Logs off ⚠️ |
| 60 | cancel scheduled shutdown | Removes scheduled task |
| 61 | cancel scheduled restart | Removes scheduled task |
| 62 | show scheduled tasks | Lists VARNA tasks |

---

## 6. Scheduler Commands (2) — v1.2

| # | Command | Example | Action |
|---|---------|---------|--------|
| 63 | schedule shutdown `{time}` | "schedule shutdown at 10 PM" | Schedules shutdown ⚠️ |
| 64 | schedule restart `{time}` | "schedule restart in 30 minutes" | Schedules restart ⚠️ |

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
| 68 | close it / close that | Closes last opened app |
| 69 | open it again / reopen it | Re-opens last app |
| 70 | go back | Opens last project/folder |
| 71 | open last project | Opens last project |
| 72 | open last folder | Opens last folder |
| 73 | what was my last app | Reports last app |
| 74 | session status | Reports full context |

---

## 9. Clipboard Commands (4) — 🆕 v1.3

| # | Command | Action |
|---|---------|--------|
| 75 | read clipboard | Reads and speaks clipboard contents |
| 76 | what did i copy | Reads clipboard |
| 77 | read what i copied | Reads clipboard |
| 78 | clipboard | Reads clipboard |

---

## 10. Smart Screenshot (3) — 🆕 v1.3

| # | Command | Example | Action |
|---|---------|---------|--------|
| 79 | screenshot as `{name}` | "screenshot as ReactBug" | Named screenshot |
| 80 | take screenshot as `{name}` | "take screenshot as login page" | Named screenshot |
| 81 | save screenshot as `{name}` | "save screenshot as dashboard" | Named screenshot |

---

## 11. File Search (dynamic) — 🆕 v1.3

| # | Command | Example | Action |
|---|---------|---------|--------|
| 82 | find `{description}` | "find PDF downloaded yesterday" | Searches Desktop/Downloads/Documents |
| 83 | locate `{description}` | "locate report" | Searches by name |
| 84 | find files `{query}` | "find files named budget" | Searches by name |

Supports filters:
- **File type**: "find PDF", "find docx", "find png"
- **Time**: "downloaded yesterday", "today", "this week", "last week"

---

## 12. Custom Macros (dynamic) — 🆕 v1.3

| # | Command | Example | Action |
|---|---------|---------|--------|
| 85 | whenever I say `{name}` do `{steps}` | "whenever I say focus mode do open vscode and open chrome" | Records macro |
| 86 | `{macro name}` | "focus mode" | Plays saved macro |
| 87 | list macros / show macros | "list macros" | Lists all macros |
| 88 | delete macro `{name}` | "delete macro focus mode" | Deletes a macro |

---

## 13. System Tray UI — 🆕 v1.3

VARNA now shows a floating overlay widget (bottom-right):
- 🎤 Mic status indicator
- 🗣 Last recognised speech
- ▶ Last matched command
- ✅/❌ Result status

System tray icon with Show/Hide/Exit menu.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ⚠️ | Dangerous — requires voice confirmation |
| 🆕 | New in v1.3 |

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
| **Total** | **~91+** | |
