"""
VARNA v1.5 - Universal App Manager
Scans, indexes, fuzzy-matches, launches, and closes ANY installed application.

Scan sources:
  - Start Menu shortcuts  (fastest, most reliable)
  - Program Files / Program Files (x86)
  - User AppData (Local + Roaming)
  - UWP / Microsoft Store apps via Get-StartApps

Cache:
  - apps.json — rebuilt on demand ("scan apps" / "refresh app list")

Closing:
  - Uses psutil to find running processes by name and terminate them
"""

import json
import os
import re
import subprocess
import time
from difflib import get_close_matches
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False
    log.warning("psutil not installed — dynamic app close disabled.")

_APPS_CACHE = Path(__file__).resolve().parent / "apps.json"

# Setting to enable/disable dynamic app discovery
ALLOW_DYNAMIC_APPS = True

# Directories to skip during scanning (speed up & avoid noise)
_SKIP_DIRS = {
    "cache", "temp", "tmp", "__pycache__", "node_modules",
    ".git", ".vscode", "logs", "log", "crash", "crashpad",
    "locales", "resources", "swiftshader", "dictionaries",
}

# Exe names to ignore (system utilities, not user apps)
_IGNORE_EXES = {
    "uninstall.exe", "uninst.exe", "unins000.exe", "update.exe",
    "updater.exe", "setup.exe", "install.exe", "installer.exe",
    "crash_reporter.exe", "crashreporter.exe", "helper.exe",
    "nacl64.exe", "notification_helper.exe", "pwahelper.exe",
    "gpu_process.exe", "renderer.exe", "plugin_host.exe",
}

# Map common spoken names to their exe filename (overrides for tricky ones)
_NAME_OVERRIDES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "notepad": "notepad",
    "calculator": "calc",
    "paint": "mspaint",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "task manager": "taskmgr",
    "file explorer": "explorer",
    "command prompt": "cmd",
    "powershell": "powershell",
}


class AppManager:
    """Scans, indexes, and manages installed Windows applications."""

    def __init__(self, auto_scan: bool = True):
        self.apps: dict[str, dict] = {}  # name → {path, type, exe_name}
        self._load_cache()

        if auto_scan and not self.apps:
            log.info("No app cache found — running initial scan.")
            self.scan()

    # ------------------------------------------------------------------ #
    # Scanning
    # ------------------------------------------------------------------ #

    def scan(self) -> int:
        """
        Scan the system for installed applications and rebuild the index.

        Returns:
            Number of apps found.
        """
        log.info("Scanning installed applications …")
        apps: dict[str, dict] = {}

        # 1. Start Menu shortcuts (fastest, best names)
        start_dirs = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]
        for start_dir in start_dirs:
            if start_dir.exists():
                self._scan_shortcuts(start_dir, apps)

        # 2. Program Files
        for pf in [r"C:\Program Files", r"C:\Program Files (x86)"]:
            pf_path = Path(pf)
            if pf_path.exists():
                self._scan_directory(pf_path, apps, max_depth=3)

        # 3. User AppData
        appdata_local = Path(os.environ.get("LOCALAPPDATA", ""))
        appdata_roaming = Path(os.environ.get("APPDATA", ""))
        for ad in [appdata_local, appdata_roaming]:
            if ad.exists():
                self._scan_directory(ad, apps, max_depth=3)

        # 4. UWP / Store apps
        self._scan_uwp(apps)

        self.apps = apps
        self._save_cache()

        log.info("Scan complete: %d applications indexed.", len(apps))
        return len(apps)

    def _scan_shortcuts(self, directory: Path, apps: dict) -> None:
        """Scan Start Menu .lnk files to resolve app names and paths."""
        try:
            for lnk in directory.rglob("*.lnk"):
                try:
                    name = lnk.stem.lower().strip()
                    # Skip uninstall shortcuts
                    if any(skip in name for skip in ["uninstall", "uninst", "readme", "help", "manual", "license"]):
                        continue
                    # Resolve the .lnk target using PowerShell
                    result = subprocess.run(
                        ["powershell", "-NoProfile", "-Command",
                         f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}').TargetPath"],
                        capture_output=True, text=True, timeout=5,
                    )
                    target = result.stdout.strip()
                    if target and target.lower().endswith(".exe") and os.path.isfile(target):
                        exe_name = Path(target).stem.lower()
                        if Path(target).name.lower() not in _IGNORE_EXES:
                            apps[name] = {
                                "path": target,
                                "type": "exe",
                                "exe_name": exe_name,
                            }
                except Exception:
                    continue
        except Exception as exc:
            log.debug("Shortcut scan error in %s: %s", directory, exc)

    def _scan_directory(self, directory: Path, apps: dict, max_depth: int = 3) -> None:
        """Recursively scan a directory for .exe files (limited depth)."""
        try:
            for item in directory.iterdir():
                if item.is_dir():
                    dir_name = item.name.lower()
                    if dir_name in _SKIP_DIRS:
                        continue
                    if max_depth > 0:
                        self._scan_directory(item, apps, max_depth - 1)
                elif item.suffix.lower() == ".exe":
                    if item.name.lower() in _IGNORE_EXES:
                        continue
                    # Use parent folder name as app name (cleaner)
                    app_name = item.parent.name.lower().strip()
                    if not app_name or app_name in ("bin", "app", "application", "program files",
                                                     "program files (x86)", "local", "roaming"):
                        app_name = item.stem.lower()

                    # Only add if we don't already have a better entry
                    if app_name not in apps:
                        apps[app_name] = {
                            "path": str(item),
                            "type": "exe",
                            "exe_name": item.stem.lower(),
                        }
        except PermissionError:
            pass
        except Exception as exc:
            log.debug("Directory scan error: %s", exc)

    def _scan_uwp(self, apps: dict) -> None:
        """Scan UWP / Microsoft Store apps using Get-StartApps."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-StartApps | Select-Object Name, AppId | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                for entry in data:
                    name = entry.get("Name", "").strip()
                    app_id = entry.get("AppId", "").strip()
                    if name and app_id and "!" in app_id:
                        # It's a UWP app
                        friendly = name.lower()
                        if friendly not in apps:
                            apps[friendly] = {
                                "path": app_id,
                                "type": "uwp",
                                "exe_name": friendly,
                            }
        except Exception as exc:
            log.debug("UWP scan error: %s", exc)

    # ------------------------------------------------------------------ #
    # Cache
    # ------------------------------------------------------------------ #

    def _load_cache(self) -> None:
        """Load cached app index from apps.json."""
        if _APPS_CACHE.exists():
            try:
                with open(_APPS_CACHE, "r", encoding="utf-8") as fh:
                    self.apps = json.load(fh)
                log.info("Loaded %d apps from cache.", len(self.apps))
            except (json.JSONDecodeError, IOError) as exc:
                log.warning("Cache load failed: %s", exc)
                self.apps = {}

    def _save_cache(self) -> None:
        """Save current app index to apps.json."""
        try:
            with open(_APPS_CACHE, "w", encoding="utf-8") as fh:
                json.dump(self.apps, fh, indent=2, ensure_ascii=False)
            log.info("Saved %d apps to cache.", len(self.apps))
        except IOError as exc:
            log.error("Cache save failed: %s", exc)

    # ------------------------------------------------------------------ #
    # Find / Match
    # ------------------------------------------------------------------ #

    def find(self, name: str) -> tuple[str | None, dict | None, list[str]]:
        """
        Find an app by name with fuzzy matching.

        Args:
            name: Spoken app name (e.g. "whatsapp", "watsapp", "spotify")

        Returns:
            (matched_name, app_info, suggestions)
            - If exact/fuzzy match → (name, {path, type, exe_name}, [])
            - If multiple similar → (None, None, [suggestion1, suggestion2, ...])
            - If not found → (None, None, [])
        """
        if not ALLOW_DYNAMIC_APPS:
            return None, None, []

        query = name.lower().strip()

        # Check overrides first (hardcoded common names)
        if query in _NAME_OVERRIDES:
            override_exe = _NAME_OVERRIDES[query]
            # Search in indexed apps by exe_name
            for app_name, info in self.apps.items():
                if info.get("exe_name") == override_exe:
                    return app_name, info, []

        # Exact match
        if query in self.apps:
            return query, self.apps[query], []

        # Check by exe_name
        for app_name, info in self.apps.items():
            if info.get("exe_name") == query:
                return app_name, info, []

        # Fuzzy match against all app names
        candidates = list(self.apps.keys())
        matches = get_close_matches(query, candidates, n=5, cutoff=0.6)

        if len(matches) == 1:
            match = matches[0]
            log.info("Fuzzy match: '%s' → '%s'", query, match)
            return match, self.apps[match], []

        if len(matches) > 1:
            # Check if one is much better than others
            # Use contains as a tiebreaker
            exact_contains = [m for m in matches if query in m or m in query]
            if len(exact_contains) == 1:
                return exact_contains[0], self.apps[exact_contains[0]], []
            log.info("Multiple fuzzy matches for '%s': %s", query, matches)
            return None, None, matches

        # No match
        log.info("No match found for '%s'", query)
        return None, None, []

    # ------------------------------------------------------------------ #
    # Launch
    # ------------------------------------------------------------------ #

    def launch(self, name: str) -> tuple[str, str]:
        """
        Launch an application by name.

        Returns:
            (action, message) — e.g. ("launched", "Opened WhatsApp")
        """
        if not ALLOW_DYNAMIC_APPS:
            return "error", "Dynamic apps are disabled."

        matched, info, suggestions = self.find(name)

        if suggestions:
            suggestion_text = ", ".join(suggestions[:3])
            return "suggest", suggestion_text

        if not matched or not info:
            return "not_found", f"Could not find {name}. Try 'scan apps' to update the app list."

        path = info["path"]
        app_type = info.get("type", "exe")

        try:
            if app_type == "uwp":
                # Launch UWP app
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command",
                     f"explorer shell:AppsFolder\\{path}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                log.info("Launched UWP app: '%s' → %s", matched, path)
                return "launched", f"Opened {matched}"
            else:
                # Launch .exe
                subprocess.Popen(
                    [path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                log.info("Launched exe: '%s' → %s", matched, path)
                return "launched", f"Opened {matched}"

        except Exception as exc:
            log.error("Launch failed for '%s': %s", matched, exc)
            # Fallback: try Start-Process
            try:
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command",
                     f"Start-Process '{path}'"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return "launched", f"Opened {matched}"
            except Exception:
                return "error", f"Could not open {matched}: {exc}"

    # ------------------------------------------------------------------ #
    # Close
    # ------------------------------------------------------------------ #

    def close(self, name: str) -> str:
        """
        Close a running application by name using psutil.

        Returns:
            Message describing the result.
        """
        if not _HAS_PSUTIL:
            return "Cannot close apps dynamically — psutil not installed."

        query = name.lower().strip()

        # Check overrides
        if query in _NAME_OVERRIDES:
            query = _NAME_OVERRIDES[query]

        # Also check our index for the exe_name
        matched, info, _ = self.find(name)
        exe_name = info.get("exe_name", query) if info else query

        killed = 0
        tried_names = set()

        # Try to find processes matching the app name
        for search_name in [query, exe_name]:
            if search_name in tried_names:
                continue
            tried_names.add(search_name)

            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    proc_name = proc.info["name"].lower()
                    if search_name in proc_name or proc_name.startswith(search_name):
                        proc.terminate()
                        killed += 1
                        log.info("Terminated process: %s (PID %d)", proc.info["name"], proc.info["pid"])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        if killed > 0:
            return f"Closed {name} ({killed} process{'es' if killed > 1 else ''} terminated)."
        return f"{name} is not running."

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #

    def list_apps(self) -> list[str]:
        """Return all indexed app names (sorted)."""
        return sorted(self.apps.keys())

    def count(self) -> int:
        """Return number of indexed apps."""
        return len(self.apps)

    def has(self, name: str) -> bool:
        """Check if an app is in the index (exact or fuzzy)."""
        matched, info, _ = self.find(name)
        return matched is not None
