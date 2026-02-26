"""
VARNA v2.3 - Grammar Pattern Matcher
Template-based command recognition using grammar patterns.

Patterns like:
    open <app>
    close <app>
    search <query>
    go to <location>

This reduces reliance on semantic matching and improves speed/precision.
"""

import re
from typing import Optional
from dataclasses import dataclass
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class GrammarMatch:
    """Represents a grammar pattern match."""
    pattern_name: str
    intent: str
    entities: dict
    confidence: float


# Grammar patterns - regex patterns with named entity extraction
_GRAMMAR_PATTERNS = {
    # App control
    "open_app": {
        "pattern": r"^(?:open|launch|start|run|fire up|bring up|load|execute|activate|boot up|pull up|access)\s+(?P<app>.+)$",
        "intent": "open",
        "confidence": 0.95,
    },
    "close_app": {
        "pattern": r"^(?:close|quit|exit|kill|terminate|stop|end|shut|shut down|turn off)\s+(?P<app>.+)$",
        "intent": "close",
        "confidence": 0.95,
    },
    "switch_app": {
        "pattern": r"^(?:switch to|go to|focus|activate|jump to|move to|change to)\s+(?P<app>.+)$",
        "intent": "switch",
        "confidence": 0.90,
    },
    
    # Window control
    "minimize": {
        "pattern": r"^minimize\s+(?P<target>.+)$",
        "intent": "minimize",
        "confidence": 0.95,
    },
    "maximize": {
        "pattern": r"^maximize\s+(?P<target>.+)$",
        "intent": "maximize",
        "confidence": 0.95,
    },
    "minimize_this": {
        "pattern": r"^minimize\s+(?:this|this window|it|current window)$",
        "intent": "minimize_this",
        "confidence": 0.95,
    },
    "maximize_this": {
        "pattern": r"^maximize\s+(?:this|this window|it|current window)$",
        "intent": "maximize_this",
        "confidence": 0.95,
    },
    "fullscreen": {
        "pattern": r"^(?:full\s*screen|go\s+full\s*screen|enter\s+full\s*screen|make\s+(?:it\s+)?full\s*screen|toggle\s+full\s*screen|f11)$",
        "intent": "fullscreen",
        "confidence": 0.95,
    },
    "show_desktop": {
        "pattern": r"^(?:show\s+desktop|minimize\s+all(?:\s+windows)?|hide\s+all(?:\s+windows)?|clear\s+desktop|desktop)$",
        "intent": "show_desktop",
        "confidence": 0.90,
    },
    
    # Search
    "search_web": {
        "pattern": r"^(?:search|google|look up|find|find online|search for|search online|web search)\s+(?:for\s+)?(?P<query>.+)$",
        "intent": "search",
        "confidence": 0.90,
    },
    "search_youtube": {
        "pattern": r"^(?:search\s+youtube|search\s+on\s+youtube|youtube\s+search|find\s+on\s+youtube)\s+(?:for\s+)?(?P<query>.+)$",
        "intent": "search_youtube",
        "confidence": 0.90,
    },
    "search_site": {
        "pattern": r"^search\s+(?:on\s+)?(?P<site>amazon|flipkart|github|wikipedia|stackoverflow)\s+(?:for\s+)?(?P<query>.+)$",
        "intent": "search_site",
        "confidence": 0.90,
    },
    
    # Typing
    "type_text": {
        "pattern": r"^(?:type|write|enter)\s+(?P<text>.+)$",
        "intent": "type",
        "confidence": 0.95,
    },
    
    # Navigation
    "go_back": {
        "pattern": r"^(?:go\s+back|back|go\s+previous|previous\s+page|page\s+back)$",
        "intent": "go_back",
        "confidence": 0.95,
    },
    "go_forward": {
        "pattern": r"^(?:go\s+forward|forward|next\s+page|page\s+forward)$",
        "intent": "go_forward",
        "confidence": 0.95,
    },
    "navigate_to": {
        "pattern": r"^(?:navigate to|go to|browse to|visit)\s+(?P<url>.+)$",
        "intent": "navigate",
        "confidence": 0.90,
    },
    "refresh": {
        "pattern": r"^(?:refresh|reload|refresh\s+page|reload\s+page)$",
        "intent": "refresh",
        "confidence": 0.95,
    },
    
    # Tab control
    "new_tab": {
        "pattern": r"^(?:new|open)\s+tab$",
        "intent": "new_tab",
        "confidence": 0.95,
    },
    "close_tab": {
        "pattern": r"^close\s+tab$",
        "intent": "close_tab",
        "confidence": 0.95,
    },
    "next_tab": {
        "pattern": r"^(?:next|right)\s+tab$",
        "intent": "next_tab",
        "confidence": 0.95,
    },
    "prev_tab": {
        "pattern": r"^(?:previous|prev|left|last)\s+tab$",
        "intent": "prev_tab",
        "confidence": 0.95,
    },
    "reopen_tab": {
        "pattern": r"^(?:reopen|restore|recover|bring back)\s+(?:closed\s+)?tab$",
        "intent": "reopen_tab",
        "confidence": 0.95,
    },
    "close_all_tabs": {
        "pattern": r"^close\s+all\s+tabs?$",
        "intent": "close_all_tabs",
        "confidence": 0.95,
    },
    "duplicate_tab": {
        "pattern": r"^(?:duplicate|clone|copy)\s+tab$",
        "intent": "duplicate_tab",
        "confidence": 0.95,
    },
    "pin_tab": {
        "pattern": r"^(?:pin|unpin)\s+tab$",
        "intent": "pin_tab",
        "confidence": 0.95,
    },
    "tab_number": {
        "pattern": r"^(?:go to\s+)?tab\s+(?P<number>\d+)$",
        "intent": "tab_number",
        "confidence": 0.95,
    },
    
    # Scrolling
    "scroll_down": {
        "pattern": r"^scroll\s+(?:a\s+)?(?P<amount>little|lot|bit)?\s*down$",
        "intent": "scroll_down",
        "confidence": 0.90,
    },
    "scroll_up": {
        "pattern": r"^scroll\s+(?:a\s+)?(?P<amount>little|lot|bit)?\s*up$",
        "intent": "scroll_up",
        "confidence": 0.90,
    },
    "scroll_top": {
        "pattern": r"^scroll\s+(?:to\s+)?top$",
        "intent": "scroll_top",
        "confidence": 0.95,
    },
    "scroll_bottom": {
        "pattern": r"^scroll\s+(?:to\s+)?bottom$",
        "intent": "scroll_bottom",
        "confidence": 0.95,
    },
    
    # Selection
    "select_word": {
        "pattern": r"^select\s+(?P<word>\w+)$",
        "intent": "select_word",
        "confidence": 0.90,
    },
    "select_all": {
        "pattern": r"^select\s+all(?:\s+text)?$",
        "intent": "select_all",
        "confidence": 0.95,
    },
    "select_line": {
        "pattern": r"^select\s+(?:this\s+)?line$",
        "intent": "select_line",
        "confidence": 0.95,
    },
    
    # Clipboard
    "copy": {
        "pattern": r"^(?:copy|copy this|copy it|copy that|copy text|copy selection)$",
        "intent": "copy",
        "confidence": 0.95,
    },
    "paste": {
        "pattern": r"^(?:paste|paste it|paste here|paste that|paste text)$",
        "intent": "paste",
        "confidence": 0.95,
    },
    "cut": {
        "pattern": r"^(?:cut|cut this|cut it|cut that|cut text|cut selection)$",
        "intent": "cut",
        "confidence": 0.95,
    },
    "clipboard": {
        "pattern": r"^(?:read\s+clipboard|what did i copy|what is in clipboard|show clipboard|clipboard\s+content|clipboard\s+history)$",
        "intent": "clipboard",
        "confidence": 0.90,
    },
    
    # Undo/Redo
    "undo": {
        "pattern": r"^(?:undo|undo that|undo this|undo last|take it back|revert)$",
        "intent": "undo",
        "confidence": 0.95,
    },
    "redo": {
        "pattern": r"^(?:redo|redo that|redo this|do again|redo last)$",
        "intent": "redo",
        "confidence": 0.95,
    },
    
    # Key presses
    "press_key": {
        "pattern": r"^press\s+(?P<key>.+)$",
        "intent": "press_key",
        "confidence": 0.90,
    },
    "send_enter": {
        "pattern": r"^(?:send|send it|press enter)$",
        "intent": "send_enter",
        "confidence": 0.95,
    },
    
    # File operations
    "save": {
        "pattern": r"^save(?:\s+file)?$",
        "intent": "save",
        "confidence": 0.95,
    },
    "save_as": {
        "pattern": r"^save\s+as\s+(?P<filename>.+)$",
        "intent": "save_as",
        "confidence": 0.90,
    },
    
    # Screenshot
    "screenshot": {
        "pattern": r"^(?:screenshot|capture|take screenshot)(?:\s+as\s+(?P<name>.+))?$",
        "intent": "screenshot",
        "confidence": 0.90,
    },
    
    # System
    "shutdown": {
        "pattern": r"^(?:shutdown|shut\s+down)(?:\s+(?:system|computer|pc|this))?$",
        "intent": "shutdown",
        "confidence": 0.90,
    },
    "restart": {
        "pattern": r"^(?:restart|reboot)(?:\s+(?:system|computer|pc|this))?$",
        "intent": "restart",
        "confidence": 0.90,
    },
    "lock": {
        "pattern": r"^lock(?:\s+(?:screen|computer|pc|system|this))?$",
        "intent": "lock",
        "confidence": 0.90,
    },
    "sleep": {
        "pattern": r"^(?:sleep|sleep\s+mode|go\s+to\s+sleep|hibernate)(?:\s+(?:system|computer|pc))?$",
        "intent": "sleep",
        "confidence": 0.90,
    },
    "logoff": {
        "pattern": r"^(?:log\s*off|sign\s*out|logout)(?:\s+(?:system|computer|pc))?$",
        "intent": "logoff",
        "confidence": 0.90,
    },
    "battery": {
        "pattern": r"^(?:battery|check\s+battery|battery\s+status|how\s+much\s+battery|battery\s+level|battery\s+percentage)$",
        "intent": "battery",
        "confidence": 0.90,
    },
    "datetime": {
        "pattern": r"^(?:time|date|what\s+time|what\s+date|current\s+time|current\s+date|what\s+is\s+the\s+time|what\s+is\s+the\s+date|today\s+date)$",
        "intent": "datetime",
        "confidence": 0.90,
    },
    
    # Context commands
    "repeat": {
        "pattern": r"^(?:repeat|do it again|again|one more time|repeat that|repeat last|say again|do that again)$",
        "intent": "repeat",
        "confidence": 0.95,
    },
    "close_this": {
        "pattern": r"^(?:close|hide|dismiss)\s+(?:this|it|this window|current window)$",
        "intent": "close_this",
        "confidence": 0.95,
    },
    
    # Volume
    "volume_up": {
        "pattern": r"^(?:volume\s+up|increase\s+volume|louder|raise\s+volume|turn\s+up\s+volume|make\s+it\s+louder|sound\s+up|increase\s+sound)$",
        "intent": "volume_up",
        "confidence": 0.90,
    },
    "volume_down": {
        "pattern": r"^(?:volume\s+down|decrease\s+volume|quieter|softer|lower\s+volume|turn\s+down\s+volume|make\s+it\s+quieter|sound\s+down|decrease\s+sound)$",
        "intent": "volume_down",
        "confidence": 0.90,
    },
    "mute": {
        "pattern": r"^(?:mute|unmute|mute\s+sound|unmute\s+sound|silence|toggle\s+mute|mute\s+volume)$",
        "intent": "mute",
        "confidence": 0.95,
    },
    "brightness_up": {
        "pattern": r"^(?:brightness\s+up|increase\s+brightness|brighter|more\s+brightness|turn\s+up\s+brightness)$",
        "intent": "brightness_up",
        "confidence": 0.90,
    },
    "brightness_down": {
        "pattern": r"^(?:brightness\s+down|decrease\s+brightness|dimmer|less\s+brightness|turn\s+down\s+brightness|dim)$",
        "intent": "brightness_down",
        "confidence": 0.90,
    },
    
    # Media
    "play_pause": {
        "pattern": r"^(?:play|pause|play\s+pause|toggle\s+play|resume)$",
        "intent": "play_pause",
        "confidence": 0.90,
    },
    "next_track": {
        "pattern": r"^(?:next\s+(?:track|song|music)|skip(?:\s+track)?|skip\s+song)$",
        "intent": "next_track",
        "confidence": 0.90,
    },
    "prev_track": {
        "pattern": r"^(?:previous\s+(?:track|song|music)|prev\s+(?:track|song)|go\s+back\s+(?:track|song))$",
        "intent": "prev_track",
        "confidence": 0.90,
    },
    
    # Developer
    "git_command": {
        "pattern": r"^git\s+(?P<action>.+)$",
        "intent": "git",
        "confidence": 0.90,
    },
    "npm_command": {
        "pattern": r"^npm\s+(?P<action>.+)$",
        "intent": "npm",
        "confidence": 0.90,
    },
    "kill_port": {
        "pattern": r"^(?:kill|stop|free)\s+port\s+(?P<port>\d+)$",
        "intent": "kill_port",
        "confidence": 0.90,
    },
    "start_server": {
        "pattern": r"^(?:start|run)\s+(?:the\s+)?(?P<type>server|dev\s*server|flask|django|vite|react|angular|express)$",
        "intent": "start_server",
        "confidence": 0.90,
    },
    
    # Monitor/Check
    "monitor_process": {
        "pattern": r"^(?:monitor|check|watch)\s+(?P<process>.+?)\s+(?:memory|cpu|usage)$",
        "intent": "monitor",
        "confidence": 0.85,
    },
    
    # Schedule
    "schedule_command": {
        "pattern": r"^schedule\s+(?P<command>.+?)\s+(?:at|in)\s+(?P<time>.+)$",
        "intent": "schedule",
        "confidence": 0.85,
    },
}

# Pre-compile patterns at module load
_COMPILED_PATTERNS = {
    name: {
        "regex": re.compile(data["pattern"], re.IGNORECASE),
        "intent": data["intent"],
        "confidence": data["confidence"],
    }
    for name, data in _GRAMMAR_PATTERNS.items()
}


class GrammarMatcher:
    """
    Grammar-based command recognition using templates.
    
    Faster and more precise than fuzzy/semantic matching
    for commands that follow known patterns.
    """
    
    def __init__(self):
        """Initialize the grammar matcher."""
        self.patterns = _COMPILED_PATTERNS
        log.info("GrammarMatcher initialized with %d patterns", len(self.patterns))
    
    def match(self, text: str, candidate: str = None) -> float:
        """
        Check if text matches any grammar pattern.
        
        Args:
            text: User input.
            candidate: Optional candidate to match against (for scoring engine).
        
        Returns:
            Match confidence (0.0-1.0), or 0.0 if no match.
        """
        result = self.extract(text)
        if result:
            # If candidate provided, check if it relates to the matched intent
            if candidate:
                candidate_lower = candidate.lower()
                if result.intent in candidate_lower or candidate_lower.startswith(result.intent):
                    return result.confidence
                return result.confidence * 0.7  # Partial credit
            return result.confidence
        return 0.0
    
    def extract(self, text: str) -> Optional[GrammarMatch]:
        """
        Extract intent and entities from text using grammar patterns.
        
        Args:
            text: User input.
        
        Returns:
            GrammarMatch object or None.
        """
        if not text:
            return None
        
        text = text.lower().strip()
        
        for name, pattern_data in self.patterns.items():
            match = pattern_data["regex"].match(text)
            if match:
                entities = {k: v for k, v in match.groupdict().items() if v}
                
                log.debug(
                    "Grammar match: '%s' → %s (intent=%s, entities=%s)",
                    text, name, pattern_data["intent"], entities
                )
                
                return GrammarMatch(
                    pattern_name=name,
                    intent=pattern_data["intent"],
                    entities=entities,
                    confidence=pattern_data["confidence"],
                )
        
        return None
    
    def get_intent(self, text: str) -> Optional[str]:
        """Get just the intent from text."""
        result = self.extract(text)
        return result.intent if result else None
    
    def get_entities(self, text: str) -> dict:
        """Get just the entities from text."""
        result = self.extract(text)
        return result.entities if result else {}
    
    def match_command(self, text: str, commands: list[str]) -> Optional[tuple[str, float]]:
        """
        Match text against command list using grammar patterns.
        
        Args:
            text: User input.
            commands: List of valid commands.
        
        Returns:
            Tuple of (best_command, confidence) or None.
        """
        result = self.extract(text)
        if not result:
            return None
        
        # Try to find matching command based on extracted intent/entities
        intent = result.intent
        entities = result.entities
        
        # Build expected command string
        if intent == "open" and "app" in entities:
            expected = f"open {entities['app']}"
        elif intent == "close" and "app" in entities:
            expected = f"close {entities['app']}"
        elif intent == "search" and "query" in entities:
            expected = f"search {entities['query']}"
        elif intent == "type" and "text" in entities:
            expected = f"type {entities['text']}"
        else:
            expected = intent
        
        # Check for exact or close match in commands
        expected_lower = expected.lower()
        for cmd in commands:
            cmd_lower = cmd.lower()
            if cmd_lower == expected_lower or expected_lower in cmd_lower:
                return (cmd, result.confidence)
        
        return None
    
    def add_pattern(
        self, 
        name: str, 
        pattern: str, 
        intent: str, 
        confidence: float = 0.90
    ) -> None:
        """
        Add a new grammar pattern at runtime.
        
        Args:
            name: Pattern identifier.
            pattern: Regex pattern string.
            intent: Intent name.
            confidence: Match confidence.
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            self.patterns[name] = {
                "regex": compiled,
                "intent": intent,
                "confidence": confidence,
            }
            log.info("Added grammar pattern: %s", name)
        except re.error as e:
            log.error("Invalid pattern '%s': %s", pattern, e)
