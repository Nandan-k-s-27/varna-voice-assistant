"""
VARNA v1.3 - Custom Macro Manager
Allows users to define, save, and replay personal command sequences.

Usage (voice):
  Record:  "whenever I say focus mode do open vscode and open chrome"
  Play:    "focus mode"
  List:    "list macros" / "show macros"
  Delete:  "delete macro focus mode"

Storage:  macros.json  (created automatically)
"""

import json
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

_MACROS_FILE = Path(__file__).resolve().parent / "macros.json"


class MacroManager:
    """Manages user-defined command macros (persisted to JSON)."""

    def __init__(self, macros_path: Path = _MACROS_FILE):
        self._path = macros_path
        self._macros: dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        """Load macros from disk."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    self._macros = json.load(fh)
                log.info("Loaded %d macros from %s", len(self._macros), self._path.name)
            except (json.JSONDecodeError, OSError) as exc:
                log.error("Failed to load macros: %s", exc)
                self._macros = {}
        else:
            log.info("No macros file found — starting fresh.")
            self._macros = {}

    def _save(self) -> None:
        """Persist macros to disk."""
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._macros, fh, indent=4, ensure_ascii=False)
            log.info("Saved %d macros to %s", len(self._macros), self._path.name)
        except OSError as exc:
            log.error("Failed to save macros: %s", exc)

    # ------------------------------------------------------------------ #
    def record(self, name: str, step_names: list[str]) -> str:
        """
        Save a new macro.

        Args:
            name: Trigger phrase (e.g. "focus mode").
            step_names: List of command names to replay (e.g. ["open vscode", "open chrome"]).

        Returns:
            Confirmation message.
        """
        name = name.lower().strip()
        self._macros[name] = {
            "steps": step_names,
        }
        self._save()
        log.info("Macro recorded: '%s' → %s", name, step_names)
        return f"Macro '{name}' saved with {len(step_names)} steps: {', '.join(step_names)}."

    # ------------------------------------------------------------------ #
    def get(self, name: str) -> list[str] | None:
        """
        Get the step names for a macro.

        Returns:
            List of command trigger names, or None if macro doesn't exist.
        """
        name = name.lower().strip()
        entry = self._macros.get(name)
        if entry:
            return entry.get("steps", [])
        return None

    # ------------------------------------------------------------------ #
    def delete(self, name: str) -> str:
        """Delete a macro by name."""
        name = name.lower().strip()
        if name in self._macros:
            del self._macros[name]
            self._save()
            log.info("Macro deleted: '%s'", name)
            return f"Macro '{name}' has been deleted."
        return f"No macro named '{name}' found."

    # ------------------------------------------------------------------ #
    def list_all(self) -> list[str]:
        """Return all macro names."""
        return list(self._macros.keys())

    # ------------------------------------------------------------------ #
    def has(self, name: str) -> bool:
        """Check if a macro exists."""
        return name.lower().strip() in self._macros
