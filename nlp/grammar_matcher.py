"""
VARNA v2.1 - Grammar Pattern Matcher
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
        "pattern": r"^(?:open|launch|start|run|fire up|bring up)\s+(?P<app>.+)$",
        "intent": "open",
        "confidence": 0.95,
    },
    "close_app": {
        "pattern": r"^(?:close|quit|exit|kill|terminate|stop|end)\s+(?P<app>.+)$",
        "intent": "close",
        "confidence": 0.95,
    },
    "switch_app": {
        "pattern": r"^(?:switch to|go to|focus|activate)\s+(?P<app>.+)$",
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
        "pattern": r"^minimize\s+(?:this|it)$",
        "intent": "minimize_this",
        "confidence": 0.95,
    },
    "maximize_this": {
        "pattern": r"^maximize\s+(?:this|it)$",
        "intent": "maximize_this",
        "confidence": 0.95,
    },
    
    # Search
    "search_web": {
        "pattern": r"^(?:search|google|look up|find)\s+(?:for\s+)?(?P<query>.+)$",
        "intent": "search",
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
        "pattern": r"^go\s+back$",
        "intent": "go_back",
        "confidence": 0.95,
    },
    "go_forward": {
        "pattern": r"^go\s+forward$",
        "intent": "go_forward",
        "confidence": 0.95,
    },
    "go_to_location": {
        "pattern": r"^go\s+to\s+(?P<location>.+)$",
        "intent": "go_to",
        "confidence": 0.90,
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
        "pattern": r"^(?:previous|prev|left)\s+tab$",
        "intent": "prev_tab",
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
        "pattern": r"^(?:copy|copy this)$",
        "intent": "copy",
        "confidence": 0.95,
    },
    "paste": {
        "pattern": r"^(?:paste|paste it)$",
        "intent": "paste",
        "confidence": 0.95,
    },
    "cut": {
        "pattern": r"^(?:cut|cut this)$",
        "intent": "cut",
        "confidence": 0.95,
    },
    
    # Undo/Redo
    "undo": {
        "pattern": r"^undo$",
        "intent": "undo",
        "confidence": 0.95,
    },
    "redo": {
        "pattern": r"^redo$",
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
        "pattern": r"^(?:shutdown|shut down)\s+(?:system|computer)?$",
        "intent": "shutdown",
        "confidence": 0.90,
    },
    "restart": {
        "pattern": r"^restart\s+(?:system|computer)?$",
        "intent": "restart",
        "confidence": 0.90,
    },
    "lock": {
        "pattern": r"^lock\s+(?:screen|computer)?$",
        "intent": "lock",
        "confidence": 0.90,
    },
    
    # Context commands
    "repeat": {
        "pattern": r"^(?:repeat|do it again|again)$",
        "intent": "repeat",
        "confidence": 0.95,
    },
    "close_this": {
        "pattern": r"^close\s+(?:this|it)$",
        "intent": "close_this",
        "confidence": 0.95,
    },
    
    # Volume
    "volume_up": {
        "pattern": r"^(?:volume up|increase volume|louder)$",
        "intent": "volume_up",
        "confidence": 0.90,
    },
    "volume_down": {
        "pattern": r"^(?:volume down|decrease volume|quieter|softer)$",
        "intent": "volume_down",
        "confidence": 0.90,
    },
    "mute": {
        "pattern": r"^(?:mute|unmute)$",
        "intent": "mute",
        "confidence": 0.95,
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
