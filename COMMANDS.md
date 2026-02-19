# VARNA v1.2 — Full Command List

This document lists all commands supported by VARNA v1.2, organized by category.

---

## 1. Static Commands (36)
Standard system commands that perform a specific action without extra input.

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
| 24 | system info | Displays system hardware and OS specs |
| 25 | battery status | Shows battery percentage and state |
| 26 | ip address | Shows local IPv4 address |
| 27 | disk space | Lists drive names and free space |
| 28 | list processes | Lists top 10 CPU consuming processes |
| 29 | current time | Speaks/Displays current time |
| 30 | current date | Speaks/Displays current date |
| 31 | lock screen | Locks the Windows session |
| 32 | empty recycle bin | Clears the Recycle Bin ⚠️ |
| 33 | screenshot | Takes a screenshot and saves to Desktop |
| 34 | increase volume | Raises system volume |
| 35 | decrease volume | Lowers system volume |
| 36 | mute volume | Mutes system volume |

---

## 2. Parameterized Commands (4)
Dynamic commands that accept additional input after the keyword.

| # | Command Template | Usage Example | Action |
|---|-----------------|---------------|--------|
| 37 | search `{query}` | "search React hooks" | Google search |
| 38 | open website `{url}` | "open website github.com" | Opens URL in Chrome |
| 39 | search youtube `{query}` | "search youtube Python" | YouTube search |
| 40 | open folder `{path}` | "open folder C:\Users" | Opens folder path |

---

## 3. Command Chains (4)
Multi-step sequences triggered by a single voice command.

| # | Command | Steps |
|---|---------|-------|
| 41 | open vscode and my react project | Opens VS Code → Waits 2s → Opens React project |
| 42 | start my backend | Opens PowerShell → cd to backend → npm start |
| 43 | start my frontend | Opens PowerShell → cd to frontend → npm start |
| 44 | start full stack | Starts backend → Waits 3s → Starts frontend |

---

## 4. Developer Mode (12)
Productivity shortcuts for software development.

| # | Command | Action |
|---|---------|--------|
| 45 | run npm start | Runs `npm start` in a new PowerShell |
| 46 | run npm install | Runs `npm install` in a new PowerShell |
| 47 | pull latest from git | Executes `git pull origin main` |
| 48 | git status | Shows current Git status |
| 49 | open git bash | Launches Git Bash |
| 50 | kill port 3000 | Force stops process on port 3000 |
| 51 | kill port 5000 | Force stops process on port 5000 |
| 52 | kill port 8080 | Force stops process on port 8080 |
| 53 | show running ports | Lists all listening ports and PIDs |
| 54 | show node processes | Lists active Node.js processes |
| 55 | kill all node | Terminates all Node.js instances ⚠️ |
| 56 | open terminal here | Opens PowerShell in current path |

---

## 5. System Commands (6) — 🆕 v1.2
System-level commands for power management and task scheduling.

| # | Command | Action |
|---|---------|--------|
| 57 | shutdown system | Shuts down the PC ⚠️ |
| 58 | restart system | Restarts the PC ⚠️ |
| 59 | log off | Logs off the current user ⚠️ |
| 60 | cancel scheduled shutdown | Removes VARNA shutdown task |
| 61 | cancel scheduled restart | Removes VARNA restart task |
| 62 | show scheduled tasks | Lists VARNA-created scheduled tasks |

---

## 6. Scheduler Commands (2) — 🆕 v1.2
Schedule system actions at a specific time using Windows Task Scheduler.

| # | Command Template | Usage Example | Action |
|---|-----------------|---------------|--------|
| 63 | schedule shutdown `{time}` | "schedule shutdown at 10 PM" | Schedules PC shutdown ⚠️ |
| 64 | schedule restart `{time}` | "schedule restart in 30 minutes" | Schedules PC restart ⚠️ |

---

## 7. Process Monitoring (3) — 🆕 v1.2
Monitor and check running processes in the background.

| # | Command Template | Usage Example | Action |
|---|-----------------|---------------|--------|
| 65 | monitor `{process}` | "monitor chrome memory usage" | Starts background memory monitoring |
| 66 | stop monitoring | "stop monitoring" | Stops the background monitor |
| 67 | check process `{name}` | "check process node" | One-shot process status report |

---

## 8. Context-Aware Commands (9) — 🆕 v1.2
Commands that use session memory to resolve pronouns and references.

| # | Command | Action |
|---|---------|--------|
| 68 | close it | Closes the last opened app |
| 69 | close that | Closes the last opened app |
| 70 | open it again | Re-opens the last app |
| 71 | reopen it | Re-opens the last app |
| 72 | open it | Re-opens the last app |
| 73 | go back | Opens the last project/folder |
| 74 | open last project | Opens the last project/folder |
| 75 | open last folder | Opens the last project/folder |
| 76 | what was my last app | Reports the last used application |
| 77 | session status | Reports full session context |

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ⚠️ | Dangerous command — VARNA asks "Are you sure?" before executing |
| 🆕 | New in v1.2 |
| `{query}` | Dynamic user input |

---

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
| Context-Aware | 9 + 1 (session status) | v1.2 |
| **Total** | **77** | |
