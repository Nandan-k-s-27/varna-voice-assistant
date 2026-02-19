"""
VARNA v1.4 - NLP Lite (Rule-Based Natural Language Processing)
Flexible command recognition without LLM.

Provides:
  - Filler word removal  ("can you please open notepad for me" → "open notepad")
  - Fuzzy matching        (using difflib — handles speech recognition errors)
  - Intent extraction     (extracts intent + object + parameter from natural speech)
"""

import re
from difflib import get_close_matches
from utils.logger import get_logger

log = get_logger(__name__)

# Filler / noise words to strip before matching
_FILLER_WORDS = [
    # Polite prefixes
    "please", "kindly", "can you", "could you", "would you",
    "will you", "hey", "hi", "hello", "yo", "ok",
    # Polite suffixes
    "for me", "right now", "now", "quickly", "fast",
    "immediately", "asap",
    # Wake word fragments
    "varna", "hey varna", "hi varna", "ok varna",
    # Filler
    "just", "actually", "basically", "like",
    "um", "uh", "the", "a", "an",
]

# Sort longest first so "can you" is removed before "can"
_FILLER_WORDS.sort(key=len, reverse=True)

# Intent vocabulary — maps synonyms to canonical intents
_INTENT_MAP = {
    # open
    "open": "open", "launch": "open", "start": "open", "run": "open",
    "bring up": "open", "fire up": "open", "load": "open", "show": "open",
    # close
    "close": "close", "quit": "close", "exit": "close", "kill": "close",
    "stop": "close", "end": "close", "terminate": "close", "shut": "close",
    # search
    "search": "search", "google": "search", "look up": "search",
    "find": "find", "locate": "find",
    # type
    "type": "type", "write": "type", "enter": "type",
    # window control
    "switch": "switch", "switch to": "switch",
    "minimize": "minimize", "minimise": "minimize",
    "maximize": "maximize", "maximise": "maximize",
    "restore": "restore",
    # screenshot
    "screenshot": "screenshot", "capture": "screenshot",
    # system
    "shutdown": "shutdown", "restart": "restart",
    "lock": "lock",
    # monitor
    "monitor": "monitor", "check": "check",
    # schedule
    "schedule": "schedule",
    # clipboard
    "read": "read", "paste": "read", "clipboard": "clipboard",
}

# Object aliases — maps alternate names to canonical app names
_OBJECT_ALIASES = {
    "chrome": "chrome", "google chrome": "chrome", "google": "chrome",
    "edge": "edge", "microsoft edge": "edge",
    "firefox": "firefox", "mozilla": "firefox",
    "notepad": "notepad", "notes": "notepad", "text editor": "notepad",
    "vscode": "vscode", "vs code": "vscode", "visual studio code": "vscode", "code editor": "vscode",
    "calculator": "calculator", "calc": "calculator",
    "paint": "paint", "ms paint": "paint",
    "file explorer": "file explorer", "explorer": "file explorer", "files": "file explorer",
    "task manager": "task manager",
    "command prompt": "command prompt", "cmd": "command prompt", "terminal": "command prompt",
    "powershell": "powershell",
    "word": "word", "ms word": "word", "microsoft word": "word",
    "excel": "excel", "ms excel": "excel",
    "powerpoint": "powerpoint", "ms powerpoint": "powerpoint", "ppt": "powerpoint",
    "downloads": "downloads", "download folder": "downloads",
    "documents": "documents", "my documents": "documents",
    "desktop": "desktop",
}


class TextNormalizer:
    """Rule-based NLP for flexible command recognition."""

    # ------------------------------------------------------------------ #
    @staticmethod
    def clean(text: str) -> str:
        """
        Remove filler/noise words from spoken text.

        "can you please open notepad for me" → "open notepad"
        "hey varna launch chrome quickly"    → "launch chrome"
        """
        if not text:
            return text

        cleaned = text.lower().strip()

        # Remove filler phrases (longest first to avoid partial matches)
        for filler in _FILLER_WORDS:
            # Use word boundary to avoid removing "the" from "theme"
            pattern = r"\b" + re.escape(filler) + r"\b"
            cleaned = re.sub(pattern, " ", cleaned)

        # Collapse multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        log.debug("NLP clean: '%s' → '%s'", text, cleaned)
        return cleaned

    # ------------------------------------------------------------------ #
    @staticmethod
    def fuzzy_match(text: str, candidates: list[str], threshold: float = 0.7) -> str | None:
        """
        Find the closest matching command from candidates.

        Uses difflib.get_close_matches with a configurable threshold.

        Args:
            text: Cleaned user input.
            candidates: List of known command keys.
            threshold: Minimum similarity ratio (0.0 to 1.0). Default 0.7 (70%).

        Returns:
            Best matching candidate, or None.
        """
        if not text or not candidates:
            return None

        matches = get_close_matches(text, candidates, n=1, cutoff=threshold)
        if matches:
            log.info("Fuzzy match: '%s' → '%s' (threshold=%.0f%%)", text, matches[0], threshold * 100)
            return matches[0]

        log.debug("No fuzzy match for '%s' (threshold=%.0f%%)", text, threshold * 100)
        return None

    # ------------------------------------------------------------------ #
    @staticmethod
    def extract_intent(text: str) -> tuple[str | None, str | None, str | None]:
        """
        Extract (intent, object, parameter) from natural speech.

        Examples:
            "open notepad"          → ("open", "notepad", None)
            "search React hooks"    → ("search", None, "React hooks")
            "close chrome"          → ("close", "chrome", None)
            "type hello world"      → ("type", None, "hello world")
            "switch to edge"        → ("switch", "edge", None)
            "minimize vscode"       → ("minimize", "vscode", None)

        Returns:
            (intent, object, parameter) — any can be None.
        """
        if not text:
            return None, None, None

        words = text.lower().strip().split()
        if not words:
            return None, None, None

        intent = None
        obj = None
        param = None

        # Try two-word intents first ("switch to", "look up", "bring up")
        if len(words) >= 2:
            two_word = f"{words[0]} {words[1]}"
            if two_word in _INTENT_MAP:
                intent = _INTENT_MAP[two_word]
                remainder = " ".join(words[2:])
            else:
                # Single-word intent
                if words[0] in _INTENT_MAP:
                    intent = _INTENT_MAP[words[0]]
                    remainder = " ".join(words[1:])
                else:
                    return None, None, None
        else:
            if words[0] in _INTENT_MAP:
                intent = _INTENT_MAP[words[0]]
                remainder = ""
            else:
                return None, None, None

        # Remove "to" prefix from remainder ("switch to chrome" → "chrome")
        remainder = re.sub(r"^to\s+", "", remainder).strip()

        if not remainder:
            return intent, None, None

        # Try to match remainder as a known object
        # Check multi-word aliases first (longest first)
        for alias in sorted(_OBJECT_ALIASES.keys(), key=len, reverse=True):
            if remainder.startswith(alias):
                obj = _OBJECT_ALIASES[alias]
                leftover = remainder[len(alias):].strip()
                param = leftover if leftover else None
                return intent, obj, param

        # If intent is search/type/find, the remainder is a parameter
        if intent in ("search", "type", "find", "schedule"):
            return intent, None, remainder

        # Otherwise, treat first word as object, rest as parameter
        parts = remainder.split(None, 1)
        obj = parts[0]
        param = parts[1] if len(parts) > 1 else None

        return intent, obj, param
