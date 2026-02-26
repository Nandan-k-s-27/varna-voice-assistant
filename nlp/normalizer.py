"""
VARNA v2.3 - Text Normalizer
Filler word removal, Indian accent correction, and text cleaning for command recognition.
"""

import re
from utils.logger import get_logger

log = get_logger(__name__)

# ── Indian accent / STT correction map ──────────────────────────────
_ACCENT_CORRECTIONS = {
    # App names often misheard
    "crome": "chrome", "krome": "chrome", "grome": "chrome", "chrom": "chrome",
    "crown": "chrome", "gram": "chrome", "from": "chrome", "chrome chrome": "chrome",
    "crumb": "chrome", "cram": "chrome", "krom": "chrome",
    "fire fax": "firefox", "fire fox": "firefox", "fierfox": "firefox",
    "fire foks": "firefox", "firefix": "firefox",
    "vatsapp": "whatsapp", "watsapp": "whatsapp", "what sapp": "whatsapp",
    "whatapp": "whatsapp", "whats app": "whatsapp", "what's app": "whatsapp",
    "wats app": "whatsapp", "votsapp": "whatsapp", "whatsaap": "whatsapp",
    "sportify": "spotify", "spot ify": "spotify", "spotifi": "spotify",
    "spottify": "spotify", "spotify fy": "spotify",
    "diskord": "discord", "dis cord": "discord", "discard": "discord",
    "tele gram": "telegram", "telegrams": "telegram", "teleg ram": "telegram",
    "calculater": "calculator", "kelculator": "calculator", "calculus": "calculator",
    "calculeter": "calculator", "calculetor": "calculator", "kelculater": "calculator",
    "note pad": "notepad", "not pad": "notepad", "no pad": "notepad",
    "notes pad": "notepad", "not bad": "notepad",
    "vee es code": "vscode", "vs kode": "vscode", "v s code": "vscode",
    "vees code": "vscode", "we es code": "vscode", "v code": "vscode",
    "power point": "powerpoint", "power pointer": "powerpoint",
    "spread sheet": "spreadsheet", "spreadshit": "spreadsheet",
    "power shell": "powershell", "powershall": "powershell",
    "you tube": "youtube", "utube": "youtube", "u tube": "youtube",
    "your tube": "youtube", "u2b": "youtube",
    "git hub": "github", "get hub": "github", "kit hub": "github",
    "g mail": "gmail", "gee mail": "gmail", "ji mail": "gmail",
    "linked in": "linkedin", "linkin": "linkedin", "linking": "linkedin",
    "what's app": "whatsapp",
    "net flicks": "netflix", "net flex": "netflix", "netfliks": "netflix",
    "flip kart": "flipkart", "flip cart": "flipkart",
    "stack overflow": "stackoverflow", "stack over flow": "stackoverflow",
    "chat gpt": "chatgpt", "chut gpt": "chatgpt", "chat gbt": "chatgpt",
    "joom": "zoom", "jhoom": "zoom", "jum": "zoom",
    "hedge": "edge", "edg": "edge", "ej": "edge", "hej": "edge",
    "ward": "word", "vord": "word", "woad": "word",
    "excell": "excel", "axel": "excel", "eggcel": "excel",
    "pant": "paint", "paynt": "paint", "pent": "paint",
    "hotstar": "hotstar", "hot star": "hotstar",
    "geeks for geeks": "geeksforgeeks", "geeks4geeks": "geeksforgeeks",
    "leet code": "leetcode", "lead code": "leetcode",
    "hacker rank": "hackerrank", "hacker rang": "hackerrank",
    "code pen": "codepen", "coat pen": "codepen",
    "w 3 schools": "w3schools", "w three schools": "w3schools",
    "post man": "postman", "postmen": "postman",
    "android studeo": "android studio",
    # Common verb misrecognitions
    "clothes": "close", "cloth": "close", "claws": "close",
    "clothes it": "close it", "clothe": "close",
    "lunch": "launch", "lawn": "launch", "lawnch": "launch",
    "lonch": "launch",
    "opan": "open", "upon": "open", "oppen": "open",
    "open open": "open", "aupen": "open",
    "strt": "start", "stat": "start", "startt": "start",
    "sut": "shut", "shyt": "shut", "shot": "shut",
    "swich": "switch", "swish": "switch", "svitch": "switch",
    "serch": "search", "surch": "search", "sarch": "search",
    "scrol": "scroll", "skroll": "scroll", "scrool": "scroll",
    "pase": "paste", "past": "paste", "paaste": "paste",
    "kopy": "copy", "copi": "copy", "coppy": "copy",
    "delet": "delete", "deel": "delete", "delit": "delete",
    "minimise": "minimize", "minimaze": "minimize",
    "maximise": "maximize", "maximaze": "maximize",
    # Common Indian English patterns
    "do the": "do", "make it": "", "put the": "",
    "give me": "", "show me": "show",
    "i want to see": "show", "let me see": "show",
    # Action words misheard
    "sellect": "select",
    "undoo": "undo", "and do": "undo",
    "based": "paste",
    "copied": "copy", "copying": "copy",
    "brighten": "brightness up", "dim": "brightness down",
    # System commands misheard
    "shut it down": "shutdown", "shut down": "shutdown",
    "re start": "restart", "re boot": "reboot",
    "log of": "log off", "log out": "logout",
    "slep": "sleep", "slip": "sleep",
}
_ACCENT_PATTERNS = sorted(_ACCENT_CORRECTIONS.items(), key=lambda x: len(x[0]), reverse=True)

# Pre-compile accent correction regexes for speed (v3.2 optimization)
_COMPILED_ACCENT_PATTERNS = [
    (re.compile(r"\b" + re.escape(wrong) + r"\b"), right, wrong)
    for wrong, right in _ACCENT_PATTERNS
]

# Filler / noise words to strip before matching
_FILLER_WORDS = [
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
    "for me please", "for me", "right now", "now",
    "quickly", "fast", "immediately", "asap",
    "if you can", "if possible", "if you don't mind",
    "thanks", "thank you", "thank you very much",
    "hey varna", "hi varna", "ok varna", "varna",
    # Indian English patterns
    "na", "no", "ya", "yaar", "boss", "bro", "dude", "man",
    "simply", "only", "itself", "also",
    "tell me", "show me", "give me",
    "i am saying", "i said", "i told you",
    "what i mean is", "i mean",
    "do one thing", "one thing",
    # Common filler
    "just", "actually", "basically", "like", "maybe",
    "try to", "try and", "kind of", "sort of",
    "um", "uh", "hmm", "ah", "er", "erm", "so",
    "you know", "i think", "i guess",
    "the", "a", "an",
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
    "open": "open", "launch": "open", "start": "open", "run": "open",
    "bring up": "open", "fire up": "open", "load": "open", "show": "open",
    "execute": "open", "activate": "open", "begin": "open",
    "turn on": "open", "boot up": "open", "pull up": "open",
    "access": "open", "go to": "open", "navigate to": "open",
    "browse": "open", "visit": "open",
    "close": "close", "quit": "close", "exit": "close", "kill": "close",
    "stop": "close", "end": "close", "terminate": "close", "shut": "close",
    "turn off": "close", "shut down": "close", "close down": "close",
    "search": "search", "google": "search", "look up": "search",
    "search for": "search", "look for": "search",
    "find": "find", "locate": "find", "where is": "find",
    "type": "type", "write": "type", "enter": "type", "input": "type",
    "send": "type", "ask": "type",
    "switch": "switch", "switch to": "switch",
    "minimize": "minimize", "minimise": "minimize", "hide": "minimize",
    "maximize": "maximize", "maximise": "maximize", "full screen": "maximize",
    "restore": "restore",
    "screenshot": "screenshot", "capture": "screenshot", "snap": "screenshot",
    "shutdown": "shutdown", "restart": "restart", "reboot": "restart",
    "lock": "lock",
    "play": "play", "pause": "pause", "resume": "play",
    "increase": "increase", "decrease": "decrease",
    "mute": "mute", "unmute": "unmute",
    "monitor": "monitor", "check": "check",
    "schedule": "schedule",
    "read": "read", "paste": "read", "clipboard": "clipboard",
    "copy": "copy", "cut": "cut",
}

# Object aliases — maps alternate names to canonical app names
_OBJECT_ALIASES = {
    "chrome": "chrome", "google chrome": "chrome", "google": "chrome",
    "browser": "chrome", "web browser": "chrome", "internet": "chrome",
    "crome": "chrome", "krome": "chrome", "grome": "chrome",
    "edge": "edge", "microsoft edge": "edge", "ms edge": "edge",
    "firefox": "firefox", "mozilla": "firefox", "mozilla firefox": "firefox",
    "brave": "brave", "brave browser": "brave",
    "notepad": "notepad", "notes": "notepad", "text editor": "notepad",
    "note pad": "notepad", "not pad": "notepad",
    "vscode": "vscode", "vs code": "vscode", "visual studio code": "vscode",
    "code editor": "vscode", "code": "vscode", "ide": "vscode",
    "word": "word", "ms word": "word", "microsoft word": "word",
    "excel": "excel", "ms excel": "excel", "spreadsheet": "excel",
    "powerpoint": "powerpoint", "ms powerpoint": "powerpoint", "ppt": "powerpoint",
    "calculator": "calculator", "calc": "calculator",
    "calculater": "calculator", "kelculator": "calculator",
    "paint": "paint", "ms paint": "paint", "drawing": "paint",
    "file explorer": "file explorer", "explorer": "file explorer",
    "files": "file explorer", "my files": "file explorer",
    "task manager": "task manager",
    "command prompt": "command prompt", "cmd": "command prompt",
    "terminal": "command prompt", "console": "command prompt",
    "powershell": "powershell", "power shell": "powershell",
    "settings": "settings", "system settings": "settings",
    "downloads": "downloads", "download folder": "downloads",
    "documents": "documents", "my documents": "documents",
    "desktop": "desktop",
    "whatsapp": "whatsapp", "watsapp": "whatsapp", "vatsapp": "whatsapp",
    "telegram": "telegram", "discord": "discord", "diskord": "discord",
    "slack": "slack", "teams": "teams", "zoom": "zoom", "joom": "zoom",
    "spotify": "spotify", "sportify": "spotify", "music player": "spotify",
    "vlc": "vlc", "vlc player": "vlc", "media player": "vlc",
    "youtube": "youtube", "you tube": "youtube", "utube": "youtube",
    "github": "github", "git hub": "github",
    "gmail": "gmail", "g mail": "gmail",
    "outlook": "outlook", "email": "outlook", "mail": "outlook",
    "linkedin": "linkedin", "linked in": "linkedin",
    "chatgpt": "chatgpt", "chat gpt": "chatgpt", "gpt": "chatgpt",
    "stackoverflow": "stackoverflow", "stack overflow": "stackoverflow",
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


# Pre-compile STT punctuation stripping regex (v3.2 optimization)
_STT_PUNCT_TRAIL = re.compile(r'[.,!?;:…]+$')
_STT_PUNCT_LEAD = re.compile(r'^[.,!?;:…]+')
_MULTI_SPACE = re.compile(r'\s+')


class TextNormalizer:
    """Rule-based NLP for flexible command recognition."""

    # ------------------------------------------------------------------ #
    @staticmethod
    def clean(text: str) -> str:
        """
        Remove filler/noise words, apply accent corrections, and strip STT artifacts.

        "can you please open notepad for me" → "open notepad"
        "hey varna launch crome quickly"     → "launch chrome"
        "open new tab."                      → "open new tab"
        "go to previous page."               → "go to previous page"
        """
        if not text:
            return text

        cleaned = text.lower().strip()

        # Step 0: Strip trailing/leading punctuation from STT output
        cleaned = _STT_PUNCT_TRAIL.sub('', cleaned).strip()
        cleaned = _STT_PUNCT_LEAD.sub('', cleaned).strip()

        # Step 1: Indian accent / STT corrections (pre-compiled patterns)
        for pattern, right, wrong in _COMPILED_ACCENT_PATTERNS:
            if wrong not in cleaned:
                continue
            if right in cleaned and wrong in right:
                continue
            cleaned = pattern.sub(right, cleaned)

        # Step 2: Remove filler phrases using pre-compiled patterns (fast)
        for pattern in _FILLER_PATTERNS:
            cleaned = pattern.sub(" ", cleaned)

        # Collapse multiple spaces
        cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()

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
