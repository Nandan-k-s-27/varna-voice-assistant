"""
VARNA v1.5 - Window Manager
Smart application control using pygetwindow + AppManager fallback.

Provides:
  - Smart open  (restore if minimized, focus if running, launch if not)
  - Minimize / Maximize / Restore / Switch-to
  - Show Desktop  (Win+D)
  - Active window detection
  - Fallback to AppManager for unknown apps
"""

import subprocess
import time
from utils.logger import get_logger

log = get_logger(__name__)

# Lazy-loaded AppManager reference (set by main.py)
_app_manager = None

def set_app_manager(mgr):
    """Set the AppManager instance for fallback lookups."""
    global _app_manager
    _app_manager = mgr

try:
    import pygetwindow as gw
    _HAS_GW = True
except ImportError:
    _HAS_GW = False
    log.warning("pygetwindow not installed — window intelligence disabled.")

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    _HAS_AUTO = True
except ImportError:
    _HAS_AUTO = False

# Map friendly app names → process names for window title matching
_TITLE_HINTS = {
    "notepad": "Notepad",
    "chrome": "Google Chrome",
    "firefox": "Mozilla Firefox",
    "edge": "Edge",
    "msedge": "Edge",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
    "word": "Word",
    "winword": "Word",
    "excel": "Excel",
    "powerpoint": "PowerPoint",
    "powerpnt": "PowerPoint",
    "calculator": "Calculator",
    "calc": "Calculator",
    "paint": "Paint",
    "mspaint": "Paint",
    "explorer": "File Explorer",
    "task manager": "Task Manager",
    "taskmgr": "Task Manager",
    "cmd": "Command Prompt",
    "powershell": "PowerShell",
}

# Map friendly names → executable for launching
_LAUNCH_MAP = {
    "notepad": "notepad",
    "chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "calculator": "calc",
    "paint": "mspaint",
    "file explorer": "explorer",
    "task manager": "taskmgr",
    "command prompt": "cmd",
    "powershell": "powershell",
    "vscode": "code",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
}


class WindowManager:
    """Smart window management using pygetwindow."""

    # ------------------------------------------------------------------ #
    @staticmethod
    def _find_windows(app_name: str) -> list:
        """Find windows whose title contains the app hint."""
        if not _HAS_GW:
            return []

        hint = _TITLE_HINTS.get(app_name.lower(), app_name)
        windows = []
        for w in gw.getAllWindows():
            if w.title and hint.lower() in w.title.lower():
                windows.append(w)
        return windows

    # ------------------------------------------------------------------ #
    def smart_open(self, app_name: str) -> tuple[str, str]:
        """
        Intelligently open an application:
          - If running & minimized → restore & focus
          - If running & visible  → bring to front
          - If not running        → launch new instance

        Returns:
            (action_taken, message)  e.g. ("restored", "Restored Notepad")
        """
        app_lower = app_name.lower().strip()

        if _HAS_GW:
            windows = self._find_windows(app_lower)
            if windows:
                win = windows[0]  # Use the first matching window
                try:
                    if win.isMinimized:
                        win.restore()
                        time.sleep(0.3)
                        win.activate()
                        log.info("Restored minimized window: '%s'", win.title)
                        return "restored", f"Restored {app_name}"
                    else:
                        win.activate()
                        log.info("Focused existing window: '%s'", win.title)
                        return "focused", f"Focused {app_name}"
                except Exception as exc:
                    log.warning("Could not activate window '%s': %s", win.title, exc)
                    # Fall through to launch

        # Not running — try hardcoded launch map first
        if app_lower in _LAUNCH_MAP:
            exec_name = _LAUNCH_MAP[app_lower]
            try:
                subprocess.Popen(
                    ["powershell", "-Command", f"Start-Process {exec_name}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                log.info("Launched (hardcoded): '%s'", exec_name)
                return "launched", f"Opened {app_name}"
            except Exception as exc:
                log.error("Failed to launch '%s': %s", exec_name, exc)
                return "error", f"Could not open {app_name}: {exc}"

        # Fallback — use AppManager for dynamic apps
        if _app_manager:
            action, msg = _app_manager.launch(app_lower)
            if action == "launched":
                return action, msg
            if action == "suggest":
                return "suggest", msg  # Suggestions list (comma-separated)
            if action == "not_found":
                return "not_found", msg

        # Last resort — try Start-Process with the raw name
        try:
            subprocess.Popen(
                ["powershell", "-Command", f"Start-Process {app_lower}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            log.info("Launched (raw): '%s'", app_lower)
            return "launched", f"Opened {app_name}"
        except Exception as exc:
            log.error("Failed to launch '%s': %s", app_lower, exc)
            return "error", f"Could not open {app_name}: {exc}"

    # ------------------------------------------------------------------ #
    def smart_open_new(self, app_name: str) -> tuple[str, str]:
        """Force-launch a new instance regardless of running state."""
        app_lower = app_name.lower().strip()
        exec_name = _LAUNCH_MAP.get(app_lower, app_lower)
        try:
            subprocess.Popen(
                ["powershell", "-Command", f"Start-Process {exec_name}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            log.info("Launched new instance (forced): '%s'", exec_name)
            return "launched", f"Opened new {app_name} window"
        except Exception as exc:
            return "error", f"Could not open {app_name}: {exc}"

    # ------------------------------------------------------------------ #
    def minimize(self, app_name: str) -> str:
        """Minimize the app window."""
        if not _HAS_GW:
            return f"Cannot minimize — pygetwindow not installed."

        windows = self._find_windows(app_name)
        if windows:
            try:
                windows[0].minimize()
                log.info("Minimized: '%s'", windows[0].title)
                return f"Minimized {app_name}"
            except Exception as exc:
                return f"Could not minimize {app_name}: {exc}"
        return f"{app_name} is not running."

    # ------------------------------------------------------------------ #
    def maximize(self, app_name: str) -> str:
        """Maximize the app window."""
        if not _HAS_GW:
            return f"Cannot maximize — pygetwindow not installed."

        windows = self._find_windows(app_name)
        if windows:
            try:
                windows[0].maximize()
                log.info("Maximized: '%s'", windows[0].title)
                return f"Maximized {app_name}"
            except Exception as exc:
                return f"Could not maximize {app_name}: {exc}"
        return f"{app_name} is not running."

    # ------------------------------------------------------------------ #
    def restore(self, app_name: str) -> str:
        """Restore a minimized app window."""
        if not _HAS_GW:
            return f"Cannot restore — pygetwindow not installed."

        windows = self._find_windows(app_name)
        if windows:
            try:
                windows[0].restore()
                time.sleep(0.2)
                windows[0].activate()
                log.info("Restored: '%s'", windows[0].title)
                return f"Restored {app_name}"
            except Exception as exc:
                return f"Could not restore {app_name}: {exc}"
        return f"{app_name} is not running."

    # ------------------------------------------------------------------ #
    def switch_to(self, app_name: str) -> str:
        """Bring the app to front / focus it."""
        if not _HAS_GW:
            return f"Cannot switch — pygetwindow not installed."

        windows = self._find_windows(app_name)
        if windows:
            try:
                win = windows[0]
                if win.isMinimized:
                    win.restore()
                    time.sleep(0.2)
                win.activate()
                log.info("Switched to: '%s'", win.title)
                return f"Switched to {app_name}"
            except Exception as exc:
                return f"Could not switch to {app_name}: {exc}"
        return f"{app_name} is not running."

    # ------------------------------------------------------------------ #
    @staticmethod
    def show_desktop() -> str:
        """Minimize all windows (Win+D)."""
        if _HAS_AUTO:
            pyautogui.hotkey("win", "d")
            log.info("Show desktop (Win+D)")
            return "Showing desktop."
        return "Cannot show desktop — pyautogui not installed."

    # ------------------------------------------------------------------ #
    @staticmethod
    def get_active_window_title() -> str | None:
        """Return the title of the currently focused window."""
        if not _HAS_GW:
            return None
        try:
            win = gw.getActiveWindow()
            return win.title if win else None
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    def is_browser_active(self) -> str | None:
        """
        Check if the currently active window is a browser.

        Returns:
            Browser process name ("chrome", "msedge", "firefox") or None.
        """
        title = self.get_active_window_title()
        if not title:
            return None
        title_lower = title.lower()
        if "google chrome" in title_lower:
            return "chrome"
        if "edge" in title_lower:
            return "msedge"
        if "firefox" in title_lower or "mozilla" in title_lower:
            return "firefox"
        return None

    # ------------------------------------------------------------------ #
    def is_app_running(self, app_name: str) -> bool:
        """Check if any window for the app exists."""
        return len(self._find_windows(app_name)) > 0
