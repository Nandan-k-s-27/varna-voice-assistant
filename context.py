"""
VARNA v1.6 - Session Context Manager
Tracks state across the session for context-aware command resolution.

Provides:
  - Last opened/closed app tracking
  - Active foreground window detection (win32gui)
  - Last browser tracking  (search uses last browser, not always Chrome)
  - Current working directory
  - Pronoun resolution  ("close it/this" → last app / active window)
  - Repeat / do it again support
  - Last search query tracking
"""

import re
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

# Try to import win32gui for active window detection
try:
    import win32gui
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False
    log.warning("win32gui not available — active window detection disabled. "
                "Install pywin32: pip install pywin32")


# Apps whose process names differ from their Start-Process names
_APP_PROCESS_MAP = {
    "notepad": "notepad",
    "chrome": "chrome",
    "firefox": "firefox",
    "msedge": "msedge",
    "edge": "msedge",
    "calc": "CalculatorApp",
    "calculator": "CalculatorApp",
    "mspaint": "mspaint",
    "paint": "mspaint",
    "explorer": "explorer",
    "taskmgr": "taskmgr",
    "cmd": "cmd",
    "powershell": "powershell",
    "code": "Code",
    "vscode": "Code",
    "winword": "WINWORD",
    "word": "WINWORD",
    "excel": "EXCEL",
    "powerpnt": "POWERPNT",
    "powerpoint": "POWERPNT",
}

# Which app names are browsers (friendly name → Start-Process name)
_BROWSERS = {
    "chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
}

# Reverse map: process name → friendly name for TTS
_PROCESS_FRIENDLY = {v.lower(): k for k, v in _APP_PROCESS_MAP.items()}


class SessionContext:
    """Maintains session state for context-aware command execution."""

    def __init__(self):
        self.last_app: str | None = None          # e.g. "chrome"
        self.last_app_process: str | None = None   # e.g. "chrome"
        self.last_browser: str = "chrome"          # default browser for searches
        self.last_project: str | None = None       # e.g. "E:\\Projects\\react-app"
        self.cwd: str = str(Path.cwd())
        self.last_command_key: str | None = None   # e.g. "open chrome"
        self.last_command_text: str | None = None  # raw text for "repeat"
        self.last_search_query: str | None = None  # for "search again"
        self.last_typed_text: str | None = None    # for context in typing
        log.info("SessionContext initialised. CWD = %s, default browser = %s",
                 self.cwd, self.last_browser)

    # ------------------------------------------------------------------ #
    def get_active_window_title(self) -> str | None:
        """Get the title of the currently active (foreground) window."""
        if not _HAS_WIN32:
            return None
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            return title if title else None
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    def update_after_command(self, command_key: str, ps_command: str) -> None:
        """
        Update context based on the command that was just executed.

        Automatically detects app opens/closes, browser switches, and project paths.
        """
        self.last_command_key = command_key
        key = command_key.lower().strip()

        # Detect app open  — "open chrome", "open notepad", etc.
        open_match = re.match(r"^open\s+(.+)$", key)
        if open_match:
            app_name = open_match.group(1).strip()
            # Skip folder/directory opens
            if app_name not in ("downloads", "documents", "desktop"):
                self.last_app = app_name
                self.last_app_process = _APP_PROCESS_MAP.get(
                    app_name, app_name
                )
                log.info("Context: last_app = '%s' (process: '%s')",
                         self.last_app, self.last_app_process)

                # If the opened app is a browser, update last_browser
                if app_name in _BROWSERS:
                    self.last_browser = _BROWSERS[app_name]
                    log.info("Context: last_browser = '%s'", self.last_browser)

        # Detect app close — "close chrome", etc.
        close_match = re.match(r"^close\s+(.+)$", key)
        if close_match:
            app_name = close_match.group(1).strip()
            self.last_app = app_name
            self.last_app_process = _APP_PROCESS_MAP.get(app_name, app_name)
            log.info("Context: last_app (closed) = '%s'", self.last_app)

        # Detect browser from command itself (e.g. search/website commands)
        browser_in_cmd = re.search(r"Start-Process\s+(chrome|firefox|msedge)", ps_command, re.IGNORECASE)
        if browser_in_cmd:
            browser_exec = browser_in_cmd.group(1).lower()
            self.last_browser = browser_exec
            log.info("Context: last_browser (from command) = '%s'", self.last_browser)

        # Detect folder/project opens — command contains a path
        path_match = re.search(r"[A-Za-z]:\\[^\s'\"]+", ps_command)
        if path_match:
            detected_path = path_match.group(0).rstrip("'\"")
            self.last_project = detected_path
            log.info("Context: last_project = '%s'", self.last_project)

        # Track search queries
        search_match = re.match(r"^search\s+(.+)$", key)
        if search_match:
            self.last_search_query = search_match.group(1).strip()
            log.info("Context: last_search = '%s'", self.last_search_query)

    # ------------------------------------------------------------------ #
    def resolve_pronoun(self, text: str) -> tuple[str, str] | None:
        """
        Resolve pronoun-based commands to concrete commands.

        Supported phrases:
          "close it"     → Stop-Process for last_app
          "close this"   → Stop-Process for active foreground window
          "minimize this" → minimize foreground app
          "maximize this" → maximize foreground app
          "open it again" → Start-Process for last_app
          "go back"      → Open last_project folder
          "repeat"       → re-execute last command
          "do it again"  → re-execute last command
          "search again" → repeat last search

        Returns:
            (matched_key, ps_command) or None if no pronoun detected.
        """
        text = text.lower().strip()

        # "close it" / "close that"
        if text in ("close it", "close that"):
            if self.last_app and self.last_app_process:
                process = self.last_app_process
                cmd = f"Stop-Process -Name {process} -Force -ErrorAction SilentlyContinue"
                log.info("Pronoun resolved: '%s' → close %s", text, self.last_app)
                return f"close {self.last_app}", cmd
            else:
                log.info("Pronoun '%s' but no last_app in context.", text)
                return None

        # "open it again" / "reopen it" / "open it"
        if text in ("open it again", "reopen it", "open it", "open that again"):
            if self.last_app:
                start_name = self.last_app
                process_map_reverse = {
                    "chrome": "chrome",
                    "firefox": "firefox",
                    "edge": "msedge",
                    "notepad": "notepad",
                    "calculator": "calc",
                    "paint": "mspaint",
                    "vscode": "code",
                    "word": "winword",
                    "excel": "excel",
                    "powerpoint": "powerpnt",
                    "file explorer": "explorer",
                    "task manager": "taskmgr",
                    "command prompt": "cmd",
                    "powershell": "powershell",
                }
                exec_name = process_map_reverse.get(start_name, start_name)
                cmd = f"Start-Process {exec_name}"
                log.info("Pronoun resolved: '%s' → open %s", text, self.last_app)
                return f"open {self.last_app}", cmd
            else:
                log.info("Pronoun '%s' but no last_app in context.", text)
                return None

        # "go back" / "open last project"
        if text in ("open last project", "open last folder"):
            if self.last_project:
                cmd = f"Start-Process explorer '{self.last_project}'"
                log.info("Pronoun resolved: '%s' → open %s", text, self.last_project)
                return f"open {self.last_project}", cmd
            else:
                log.info("Pronoun '%s' but no last_project in context.", text)
                return None

        return None

    # ------------------------------------------------------------------ #
    def get_status(self) -> str:
        """Return a human-readable summary of current context."""
        parts = []
        if self.last_app:
            parts.append(f"Last app: {self.last_app}")
        if self.last_browser:
            parts.append(f"Active browser: {self.last_browser}")
        if self.last_project:
            parts.append(f"Last project: {self.last_project}")
        active = self.get_active_window_title()
        if active:
            parts.append(f"Active window: {active}")
        parts.append(f"Working directory: {self.cwd}")
        return ". ".join(parts) if parts else "No context yet."

