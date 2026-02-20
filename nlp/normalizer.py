"""
VARNA v2.0 - Text Normalizer
Filler word removal and text cleaning for command recognition.
"""

import re
from utils.logger import get_logger

log = get_logger(__name__)

# Filler / noise words to strip before matching
_FILLER_WORDS = [
    # Polite multi-word phrases (longest first matters)
    "can you help me to", "can you help me", "could you help me to", "could you help me",
    "would you help me to", "would you help me",
    "i would like to", "i'd like to", "i would like you to",
    "i want you to", "i want to", "i need you to", "i need to",
    "do me a favor and", "do me a favour and",
    "be kind enough to", "go ahead and",
    "can you please", "could you please", "would you please",
    "will you please", "can you just", "could you just",
    "can you", "could you", "would you", "will you",
    "i want", "i need",
    "please", "kindly",
    # Polite suffixes
    "for me please", "for me", "right now", "now",
    "quickly", "fast", "immediately", "asap",
    "if you can", "if possible", "if you don't mind",
    "thanks", "thank you", "thank you very much",
    # Wake word fragments
    "hey varna", "hi varna", "ok varna", "varna",
    # Common filler
    "just", "actually", "basically", "like", "maybe",
    "try to", "try and",
    "um", "uh", "hmm", "ah",
    "the", "a", "an",
    # Prefix noise
    "hey", "hi", "hello", "yo", "ok", "okay",
]

# Sort longest first so "can you help me to" is removed before "can you"
_FILLER_WORDS.sort(key=len, reverse=True)

# Pre-compile filler patterns at import time for speed
_FILLER_PATTERNS = [
    re.compile(r"\b" + re.escape(filler) + r"\b", re.IGNORECASE)
    for filler in _FILLER_WORDS
]

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


def clean_text(text: str) -> str:
    """
    Convenience function for quick text cleaning.
    
    Args:
        text: Raw user input.
    
    Returns:
        Cleaned text with filler words removed.
    """
    return TextNormalizer.clean(text)


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

        # Remove filler phrases using pre-compiled patterns (fast)
        for pattern in _FILLER_PATTERNS:
            cleaned = pattern.sub(" ", cleaned)

        # Collapse multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        log.debug("NLP clean: '%s' → '%s'", text, cleaned)
        return cleaned

    # ------------------------------------------------------------------ #
    @staticmethod
    def fuzzy_match(text: str, candidates: list[str], threshold: float = 0.7) -> str | None:
        """
        Find the closest matching command from candidates.
        
        DEPRECATED: Use FuzzyMatcher.match() instead.

        Uses difflib.get_close_matches with a configurable threshold.

        Args:
            text: Cleaned user input.
            candidates: List of known command keys.
            threshold: Minimum similarity ratio (0.0 to 1.0). Default 0.7 (70%).

        Returns:
            Best matching candidate, or None.
        """
        from difflib import get_close_matches
        
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
    
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize_app_name(name: str) -> str:
        """
        Normalize an application name to its canonical form.
        
        Args:
            name: Raw app name from user input.
        
        Returns:
            Canonical app name if alias exists, else original.
        """
        name_lower = name.lower().strip()
        return _OBJECT_ALIASES.get(name_lower, name_lower)
