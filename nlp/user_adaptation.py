"""
VARNA v2.2 - User Adaptation Memory
Stores learned user preferences and pronunciation variants.

Features:
  - Pronunciation corrections ("crome" → "chrome")
  - App preferences ("browser" → "edge")
  - Command shortcuts
  - Phrase mappings

This creates personalized assistant behavior without ML.
"""

import json
import threading
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from utils.logger import get_logger

log = get_logger(__name__)

_ADAPT_FILE = Path(__file__).parent.parent / "user_adapt.json"


class UserAdaptation:
    """
    Micro adaptive layer for learning user preferences.
    
    Stores:
      - Pronunciation corrections
      - Preferred app mappings
      - Frequently used commands
      - Custom phrase shortcuts
    """
    
    def __init__(self, filepath: Path = _ADAPT_FILE):
        """Initialize user adaptation memory."""
        self.filepath = filepath
        self._lock = threading.Lock()
        
        # Data structure
        self._data = {
            "pronunciation": {},      # "crome": "chrome"
            "app_preferences": {},    # "browser": "edge", "editor": "vscode"
            "phrase_shortcuts": {},   # "dev mode": "open vscode and open terminal"
            "corrections": {},        # Phrase corrections with count
            "usage_stats": {},        # Command usage frequency
            "last_updated": None
        }
        
        self._load()
        log.info("UserAdaptation loaded with %d pronunciations, %d preferences",
                len(self._data["pronunciation"]),
                len(self._data["app_preferences"]))
    
    def _load(self) -> None:
        """Load adaptation data from file."""
        try:
            if self.filepath.exists():
                with open(self.filepath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Merge with defaults
                    for key in self._data:
                        if key in loaded:
                            self._data[key] = loaded[key]
        except Exception as e:
            log.warning("Failed to load user_adapt.json: %s", e)
    
    def _save(self) -> None:
        """Save adaptation data to file."""
        try:
            self._data["last_updated"] = datetime.now().isoformat()
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            log.error("Failed to save user_adapt.json: %s", e)
    
    # === Pronunciation Corrections ===
    
    def add_pronunciation(self, spoken: str, correct: str) -> None:
        """
        Learn a pronunciation variant.
        
        Args:
            spoken: What the user said (e.g., "crome")
            correct: Correct form (e.g., "chrome")
        """
        spoken = spoken.lower().strip()
        correct = correct.lower().strip()
        
        if spoken == correct:
            return
        
        with self._lock:
            self._data["pronunciation"][spoken] = correct
            self._save()
        
        log.info("Learned pronunciation: '%s' → '%s'", spoken, correct)
    
    def get_pronunciation(self, spoken: str) -> str | None:
        """Get corrected pronunciation if known."""
        return self._data["pronunciation"].get(spoken.lower().strip())
    
    def apply_pronunciations(self, text: str) -> str:
        """Apply all known pronunciation corrections to text."""
        words = text.lower().split()
        corrected = []
        
        for word in words:
            correction = self._data["pronunciation"].get(word)
            corrected.append(correction if correction else word)
        
        result = " ".join(corrected)
        if result != text.lower():
            log.debug("Applied pronunciations: '%s' → '%s'", text, result)
        
        return result
    
    # === App Preferences ===
    
    def set_app_preference(self, generic: str, specific: str) -> None:
        """
        Set user's preferred app for a generic term.
        
        Args:
            generic: Generic term (e.g., "browser", "editor")
            specific: User's preferred app (e.g., "edge", "vscode")
        """
        generic = generic.lower().strip()
        specific = specific.lower().strip()
        
        with self._lock:
            self._data["app_preferences"][generic] = specific
            self._save()
        
        log.info("Set app preference: '%s' → '%s'", generic, specific)
    
    def get_app_preference(self, generic: str) -> str | None:
        """Get user's preferred app for a generic term."""
        return self._data["app_preferences"].get(generic.lower().strip())
    
    def resolve_app_reference(self, text: str) -> str:
        """Replace generic app references with user preferences."""
        words = text.lower().split()
        resolved = []
        
        for word in words:
            pref = self._data["app_preferences"].get(word)
            resolved.append(pref if pref else word)
        
        return " ".join(resolved)
    
    # === Phrase Shortcuts ===
    
    def add_phrase_shortcut(self, shortcut: str, expansion: str) -> None:
        """
        Add a phrase shortcut.
        
        Args:
            shortcut: Short phrase (e.g., "dev mode")
            expansion: Full command (e.g., "open vscode and open terminal")
        """
        shortcut = shortcut.lower().strip()
        
        with self._lock:
            self._data["phrase_shortcuts"][shortcut] = expansion
            self._save()
        
        log.info("Added phrase shortcut: '%s' → '%s'", shortcut, expansion)
    
    def get_phrase_expansion(self, text: str) -> str | None:
        """Get phrase expansion if text is a shortcut."""
        return self._data["phrase_shortcuts"].get(text.lower().strip())
    
    # === Corrections Learning ===
    
    def record_correction(self, wrong: str, correct: str) -> None:
        """
        Record a command correction.
        
        Args:
            wrong: Misrecognized command
            correct: Correct command
        """
        wrong = wrong.lower().strip()
        correct = correct.lower().strip()
        
        if wrong == correct:
            return
        
        with self._lock:
            key = f"{wrong}|{correct}"
            if key not in self._data["corrections"]:
                self._data["corrections"][key] = {"count": 0, "first_seen": datetime.now().isoformat()}
            self._data["corrections"][key]["count"] += 1
            self._data["corrections"][key]["last_seen"] = datetime.now().isoformat()
            
            # If corrected multiple times, learn as pronunciation
            if self._data["corrections"][key]["count"] >= 2:
                # Extract single word corrections
                wrong_words = wrong.split()
                correct_words = correct.split()
                
                if len(wrong_words) == len(correct_words):
                    for w, c in zip(wrong_words, correct_words):
                        if w != c and len(w) > 2:
                            self._data["pronunciation"][w] = c
            
            self._save()
    
    # === Usage Statistics ===
    
    def record_usage(self, command: str) -> None:
        """Record command usage for frequency analysis."""
        command = command.lower().strip()
        
        with self._lock:
            if command not in self._data["usage_stats"]:
                self._data["usage_stats"][command] = 0
            self._data["usage_stats"][command] += 1
            
            # Save periodically (every 10 uses)
            total = sum(self._data["usage_stats"].values())
            if total % 10 == 0:
                self._save()
    
    def get_frequent_commands(self, n: int = 10) -> list[tuple[str, int]]:
        """Get top N most frequently used commands."""
        sorted_cmds = sorted(
            self._data["usage_stats"].items(),
            key=lambda x: -x[1]
        )
        return sorted_cmds[:n]
    
    # === Full Processing ===
    
    def process_input(self, text: str) -> str:
        """
        Apply all adaptations to input text.
        
        Order:
          1. Check for exact phrase shortcut
          2. Apply pronunciation corrections
          3. Resolve app preferences
        """
        # Check phrase shortcuts first
        expansion = self.get_phrase_expansion(text)
        if expansion:
            log.info("Expanded shortcut: '%s' → '%s'", text, expansion)
            return expansion
        
        # Apply pronunciations
        text = self.apply_pronunciations(text)
        
        # Resolve app references
        text = self.resolve_app_reference(text)
        
        return text
    
    def get_summary(self) -> dict:
        """Get summary of adaptation data."""
        return {
            "pronunciations": len(self._data["pronunciation"]),
            "app_preferences": len(self._data["app_preferences"]),
            "phrase_shortcuts": len(self._data["phrase_shortcuts"]),
            "corrections": len(self._data["corrections"]),
            "total_commands": sum(self._data["usage_stats"].values()),
            "unique_commands": len(self._data["usage_stats"]),
            "last_updated": self._data["last_updated"]
        }


# Singleton instance
_adaptation: UserAdaptation | None = None


def get_adaptation() -> UserAdaptation:
    """Get or create the singleton adaptation instance."""
    global _adaptation
    if _adaptation is None:
        _adaptation = UserAdaptation()
    return _adaptation
