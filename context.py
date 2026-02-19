"""
VARNA v1.2 - Session Context Manager
Tracks state across the session for context-aware command resolution.

Provides:
  - Last opened/closed app tracking
  - Last opened project/folder tracking
  - Current working directory
  - Pronoun resolution  ("close it" → last app)
"""

import re
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)


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

# Reverse map: process name → friendly name for TTS
_PROCESS_FRIENDLY = {v.lower(): k for k, v in _APP_PROCESS_MAP.items()}


class SessionContext:
    """Maintains session state for context-aware command execution."""

    def __init__(self):
        self.last_app: str | None = None          # e.g. "chrome"
        self.last_app_process: str | None = None   # e.g. "chrome"
        self.last_project: str | None = None       # e.g. "E:\\Projects\\react-app"
        self.cwd: str = str(Path.cwd())
        self.last_command_key: str | None = None   # e.g. "open chrome"
        log.info("SessionContext initialised. CWD = %s", self.cwd)

    # ------------------------------------------------------------------ #
    def update_after_command(self, command_key: str, ps_command: str) -> None:
        """
        Update context based on the command that was just executed.

        Automatically detects app opens/closes and project paths.
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

        # Detect app close — "close chrome", etc.
        close_match = re.match(r"^close\s+(.+)$", key)
        if close_match:
            app_name = close_match.group(1).strip()
            self.last_app = app_name
            self.last_app_process = _APP_PROCESS_MAP.get(app_name, app_name)
            log.info("Context: last_app (closed) = '%s'", self.last_app)

        # Detect folder/project opens — command contains a path
        path_match = re.search(r"[A-Za-z]:\\[^\s'\"]+", ps_command)
        if path_match:
            detected_path = path_match.group(0).rstrip("'\"")
            self.last_project = detected_path
            log.info("Context: last_project = '%s'", self.last_project)

    # ------------------------------------------------------------------ #
    def resolve_pronoun(self, text: str) -> tuple[str, str] | None:
        """
        Resolve pronoun-based commands to concrete commands.

        Supported phrases:
          "close it"     → Stop-Process for last_app
          "open it again" → Start-Process for last_app
          "go back"      → Open last_project folder

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
                # Use the original start command name
                start_name = self.last_app
                # Map friendly names back to process names
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
        if text in ("go back", "open last project", "open last folder"):
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
        if self.last_project:
            parts.append(f"Last project: {self.last_project}")
        parts.append(f"Working directory: {self.cwd}")
        return ". ".join(parts) if parts else "No context yet."
