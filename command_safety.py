"""
VARNA v2.3 - Command Safety & Intent Isolation Engine
4-Gate Architecture for safe, accurate command execution.

Gate 1: Similarity Threshold Split (risk-based thresholds)
Gate 2: Phonetic Safeguard Layer (exact keyword match for dangerous words)
Gate 3: Two-Step Execution for Critical Commands (confirmation required)
Gate 4: Intent Isolation (category-based matching, no cross-category fuzzy)

This module prevents:
  - "click links" → "lock this" (cross-category)
  - "open first link" → "open microsoft paint" (unconstrained fuzzy)
  - "go to previous page" → "previous song" (domain leak)
  - "page down" → "power down" → "shutdown" (phonetic drift)
"""

import re
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional
from utils.logger import get_logger

log = get_logger(__name__)


# ====================================================================== #
# Risk Levels
# ====================================================================== #

class RiskLevel(Enum):
    """Command risk classification."""
    LOW = "low"           # open apps, navigation, typing — threshold 65%
    MEDIUM = "medium"     # close apps, file operations — threshold 80%
    HIGH = "high"         # lock, volume, system changes — threshold 90%
    CRITICAL = "critical" # shutdown, restart, delete, format — exact match + confirm


# ====================================================================== #
# Intent Categories
# ====================================================================== #

class IntentCategory(Enum):
    """Command intent categories for isolation."""
    APP_OPEN = auto()       # open, launch, start apps
    APP_CLOSE = auto()      # close, quit, kill apps
    BROWSER_NAV = auto()    # tabs, links, back, forward, refresh
    MEDIA = auto()          # play, pause, next/prev song, volume
    SYSTEM = auto()         # shutdown, restart, lock, sleep, brightness
    FILE_OP = auto()        # copy, paste, cut, delete, rename, save
    TYPING = auto()         # type, write, enter text
    SCROLL = auto()         # scroll up/down, page up/down
    NAVIGATION = auto()     # go to, navigate, drives, folders
    SEARCH = auto()         # search web, youtube, etc.
    WINDOW = auto()         # minimize, maximize, switch, snap
    SELECTION = auto()      # select text
    CLIPBOARD = auto()      # clipboard operations
    DEVELOPER = auto()      # git, npm, docker
    UNKNOWN = auto()        # cannot classify


# ====================================================================== #
# Risk thresholds per level
# ====================================================================== #

RISK_THRESHOLDS = {
    RiskLevel.LOW: 0.65,       # open apps, typing, scrolling
    RiskLevel.MEDIUM: 0.80,    # close apps, file ops
    RiskLevel.HIGH: 0.90,      # lock, volume control
    RiskLevel.CRITICAL: 1.0,   # shutdown, restart — EXACT MATCH ONLY
}


# ====================================================================== #
# Dangerous keywords — NEVER match these via fuzzy/phonetic
# Must appear EXACTLY in the transcript to trigger
# ====================================================================== #

EXACT_ONLY_KEYWORDS = frozenset({
    # Critical system commands
    "shutdown", "shut down", "restart", "reboot",
    "log off", "log out", "sign out", "sign off",
    "lock", "lock pc", "lock computer", "lock screen", "lock this",
    # Destructive file operations
    "format", "permanent delete", "permanently delete",
    "shift delete", "force delete",
    # System modification
    "sleep", "hibernate",
})

# Words that if present in the input, BLOCK fuzzy matching to dangerous commands
SAFEGUARD_WORDS = frozenset({
    "shutdown", "restart", "reboot", "lock", "delete",
    "format", "sleep", "hibernate", "log off", "sign out",
})


# ====================================================================== #
# Category keyword patterns for intent detection
# ====================================================================== #

_CATEGORY_PATTERNS = [
    # SCROLL — scrolling and page navigation (check BEFORE browser_nav to catch "page down" etc.)
    (IntentCategory.SCROLL, re.compile(
        r'\b(scroll|page up|page down|go up|go down|move up|move down|'
        r'top of page|bottom of page|previous page|next page|'
        r'go to previous page|go to next page)\b', re.I)),

    # BROWSER_NAV — tabs, links, browser-specific actions
    (IntentCategory.BROWSER_NAV, re.compile(
        r'\b(tab|tabs|link|links|refresh|reload|bookmark|incognito|'
        r'address bar|url|new tab|close tab|next tab|previous tab|'
        r'reopen|back page|forward page|history|dev tools|view source|'
        r'first link|second link|third link|click link|open link|'
        r'first result|second result|third result|open result)\b', re.I)),

    # MEDIA — media playback
    (IntentCategory.MEDIA, re.compile(
        r'\b(play|pause|resume|next song|previous song|skip|'
        r'stop music|stop playback|now playing|track|shuffle|repeat song)\b', re.I)),

    # SYSTEM — dangerous system commands
    (IntentCategory.SYSTEM, re.compile(
        r'\b(shutdown|shut down|restart|reboot|lock|sleep|hibernate|'
        r'log off|sign out|battery|brightness|'
        r'increase brightness|decrease brightness|'
        r'time|date|current time)\b', re.I)),

    # APP_OPEN — opening applications
    (IntentCategory.APP_OPEN, re.compile(
        r'^(open|launch|start|run|bring up|fire up|load|execute|activate|boot|pull up|access)\s', re.I)),

    # APP_CLOSE — closing applications
    (IntentCategory.APP_CLOSE, re.compile(
        r'^(close|quit|exit|kill|terminate|stop|end|shut)\s', re.I)),

    # WINDOW — window management
    (IntentCategory.WINDOW, re.compile(
        r'\b(minimize|maximize|restore|switch to|snap left|snap right|'
        r'show desktop|hide all|alt tab|switch window|next window|'
        r'minimize all|move window)\b', re.I)),

    # FILE_OP — file operations
    (IntentCategory.FILE_OP, re.compile(
        r'\b(copy|paste|cut|undo|redo|save|rename|delete|'
        r'select all|bold|italic|underline|indent|outdent|'
        r'find text|find in page|new file|new folder|properties)\b', re.I)),

    # TYPING — voice typing
    (IntentCategory.TYPING, re.compile(
        r'^(type|write|enter)\s', re.I)),

    # NAVIGATION — file/browser navigation
    (IntentCategory.NAVIGATION, re.compile(
        r'\b(go to|navigate to|go back|go forward|back|forward|'
        r'drive|this pc|my computer|downloads|documents|desktop|'
        r'pictures|music|videos|folder|parent folder)\b', re.I)),

    # SEARCH — web/app search
    (IntentCategory.SEARCH, re.compile(
        r'^(search|google|look up|find online|youtube|search youtube)\s', re.I)),

    # SELECTION — text selection
    (IntentCategory.SELECTION, re.compile(
        r'\b(select|highlight|select all|select line|select word|'
        r'select next|select previous)\b', re.I)),

    # CLIPBOARD
    (IntentCategory.CLIPBOARD, re.compile(
        r'\b(clipboard|clipboard history|paste item|paste first|paste second)\b', re.I)),

    # DEVELOPER
    (IntentCategory.DEVELOPER, re.compile(
        r'\b(git|npm|yarn|docker|port|server|dev|flask|django|vite)\b', re.I)),
]


# ====================================================================== #
# Category → Risk Level mapping
# ====================================================================== #

CATEGORY_RISK = {
    IntentCategory.APP_OPEN: RiskLevel.LOW,
    IntentCategory.BROWSER_NAV: RiskLevel.LOW,
    IntentCategory.SCROLL: RiskLevel.LOW,
    IntentCategory.TYPING: RiskLevel.LOW,
    IntentCategory.SELECTION: RiskLevel.LOW,
    IntentCategory.SEARCH: RiskLevel.LOW,
    IntentCategory.NAVIGATION: RiskLevel.LOW,
    IntentCategory.CLIPBOARD: RiskLevel.LOW,
    IntentCategory.DEVELOPER: RiskLevel.LOW,
    IntentCategory.MEDIA: RiskLevel.LOW,
    IntentCategory.WINDOW: RiskLevel.MEDIUM,
    IntentCategory.APP_CLOSE: RiskLevel.MEDIUM,
    IntentCategory.FILE_OP: RiskLevel.MEDIUM,
    IntentCategory.SYSTEM: RiskLevel.HIGH,
    IntentCategory.UNKNOWN: RiskLevel.MEDIUM,
}

# Commands that REQUIRE two-step confirmation ("Confirm shutdown?")
CONFIRMATION_REQUIRED = frozenset({
    "shutdown", "shut down", "restart", "reboot",
    "log off", "log out", "sign out", "sign off",
    "sleep", "hibernate",
    "permanent delete", "permanently delete",
    "shift delete", "force delete",
    "format",
})


# ====================================================================== #
# Safety Engine
# ====================================================================== #

@dataclass
class SafetyVerdict:
    """Result of safety evaluation."""
    allowed: bool
    needs_confirmation: bool
    risk_level: RiskLevel
    category: IntentCategory
    reason: str
    threshold: float
    blocked_reason: str | None = None


class CommandSafetyEngine:
    """
    4-Gate safety engine for command execution.
    
    Gate 1: Risk-based threshold check
    Gate 2: Phonetic/exact keyword safeguard
    Gate 3: Two-step confirmation for critical commands
    Gate 4: Intent category isolation
    """

    def __init__(self):
        self._stats = {"blocked": 0, "confirmed": 0, "passed": 0}
        log.info("CommandSafetyEngine initialized")

    # ------------------------------------------------------------------ #
    # Gate 4: Intent Category Detection
    # ------------------------------------------------------------------ #

    def detect_category(self, text: str) -> IntentCategory:
        """
        Detect the intent category of the input text.
        
        This is Gate 4 — isolates commands to their domain
        so fuzzy matching only happens within the correct category.
        
        Args:
            text: Normalized user input.
        
        Returns:
            IntentCategory enum value.
        """
        if not text:
            return IntentCategory.UNKNOWN

        text_lower = text.lower().strip()

        for category, pattern in _CATEGORY_PATTERNS:
            if pattern.search(text_lower):
                log.debug("Intent category detected: '%s' → %s", text_lower, category.name)
                return category

        return IntentCategory.UNKNOWN

    # ------------------------------------------------------------------ #
    # Gate 2: Phonetic Safeguard — exact keyword check
    # ------------------------------------------------------------------ #

    def is_exact_only_command(self, text: str) -> bool:
        """
        Check if the text contains a dangerous keyword that
        must only be triggered by exact match.
        
        Args:
            text: Normalized user input.
        
        Returns:
            True if this command should ONLY match exactly.
        """
        text_lower = text.lower().strip()
        return text_lower in EXACT_ONLY_KEYWORDS

    def contains_safeguard_word(self, candidate: str) -> bool:
        """
        Check if a candidate command contains a dangerous keyword.
        
        If it does, it should NEVER be matched via fuzzy/phonetic.
        It must only be reached by exact match.
        
        Args:
            candidate: Command key being considered.
        
        Returns:
            True if the candidate is a safeguarded command.
        """
        candidate_lower = candidate.lower()
        for word in SAFEGUARD_WORDS:
            if word in candidate_lower:
                return True
        return False

    # ------------------------------------------------------------------ #
    # Gate 1: Risk-Based Threshold
    # ------------------------------------------------------------------ #

    def get_threshold_for_category(self, category: IntentCategory) -> float:
        """
        Get the similarity threshold for a specific category.
        
        Args:
            category: Intent category.
        
        Returns:
            Minimum similarity threshold (0.0 to 1.0).
        """
        risk = CATEGORY_RISK.get(category, RiskLevel.MEDIUM)
        return RISK_THRESHOLDS[risk]

    def get_risk_level(self, text: str, category: IntentCategory = None) -> RiskLevel:
        """
        Determine risk level of a command.
        
        Args:
            text: Command text.
            category: Pre-detected category (optional).
        
        Returns:
            RiskLevel enum.
        """
        text_lower = text.lower().strip()

        # Critical commands
        for keyword in CONFIRMATION_REQUIRED:
            if keyword in text_lower:
                return RiskLevel.CRITICAL

        # Safeguard words
        for word in SAFEGUARD_WORDS:
            if word in text_lower:
                return RiskLevel.HIGH

        # Category-based risk
        if category:
            return CATEGORY_RISK.get(category, RiskLevel.MEDIUM)

        # Detect from text
        detected = self.detect_category(text)
        return CATEGORY_RISK.get(detected, RiskLevel.MEDIUM)

    # ------------------------------------------------------------------ #
    # Gate 3: Two-Step Confirmation Check
    # ------------------------------------------------------------------ #

    def needs_two_step_confirmation(self, matched_command: str) -> bool:
        """
        Check if a matched command requires two-step confirmation.
        
        Args:
            matched_command: The command key that was matched.
        
        Returns:
            True if confirmation is needed before execution.
        """
        cmd_lower = matched_command.lower().strip()
        for keyword in CONFIRMATION_REQUIRED:
            if keyword in cmd_lower:
                return True
        return False

    # ------------------------------------------------------------------ #
    # Combined Safety Evaluation
    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        input_text: str,
        matched_command: str,
        match_confidence: float,
        match_method: str,
    ) -> SafetyVerdict:
        """
        Full 4-gate safety evaluation of a command match.
        
        Args:
            input_text: What the user said (normalized).
            matched_command: What the system matched.
            match_confidence: Match confidence (0.0 to 1.0).
            match_method: How it was matched ("exact", "fuzzy", "phonetic", etc.)
        
        Returns:
            SafetyVerdict with decision.
        """
        input_lower = input_text.lower().strip()
        cmd_lower = matched_command.lower().strip()

        # Detect categories
        input_category = self.detect_category(input_text)
        cmd_category = self.detect_category(matched_command)

        # Get risk info
        risk = self.get_risk_level(matched_command, cmd_category)
        threshold = self.get_threshold_for_category(cmd_category)

        # --- Gate 1: Exact matches always pass ---
        if match_method == "exact":
            needs_confirm = self.needs_two_step_confirmation(matched_command)
            self._stats["passed"] += 1
            return SafetyVerdict(
                allowed=True,
                needs_confirmation=needs_confirm,
                risk_level=risk,
                category=input_category,
                reason="Exact match",
                threshold=threshold,
            )

        # --- Gate 2: Phonetic Safeguard ---
        # If the matched command is dangerous, it MUST NOT come from fuzzy/phonetic
        if self.contains_safeguard_word(matched_command):
            # Check if the input ALSO contains the safeguard word
            input_has_dangerous = any(w in input_lower for w in SAFEGUARD_WORDS)
            if not input_has_dangerous:
                self._stats["blocked"] += 1
                log.warning(
                    "SAFETY BLOCKED: '%s' → '%s' (dangerous command via %s, "
                    "input lacks safeguard keyword)",
                    input_text, matched_command, match_method
                )
                return SafetyVerdict(
                    allowed=False,
                    needs_confirmation=False,
                    risk_level=risk,
                    category=input_category,
                    reason="Blocked by phonetic safeguard",
                    threshold=threshold,
                    blocked_reason=f"'{matched_command}' is a dangerous command "
                                   f"that cannot be triggered via {match_method}. "
                                   f"Say the exact command.",
                )

        # --- Gate 4: Intent Isolation ---
        # If input and command are in DIFFERENT categories, block unless very high confidence
        if (input_category != IntentCategory.UNKNOWN and 
            cmd_category != IntentCategory.UNKNOWN and
            input_category != cmd_category):
            
            # Cross-category match: require much higher threshold
            cross_threshold = max(threshold, 0.90)
            if match_confidence < cross_threshold:
                self._stats["blocked"] += 1
                log.warning(
                    "SAFETY BLOCKED: '%s' [%s] → '%s' [%s] (cross-category, "
                    "confidence %.2f < %.2f)",
                    input_text, input_category.name,
                    matched_command, cmd_category.name,
                    match_confidence, cross_threshold
                )
                return SafetyVerdict(
                    allowed=False,
                    needs_confirmation=False,
                    risk_level=risk,
                    category=input_category,
                    reason="Blocked by intent isolation",
                    threshold=cross_threshold,
                    blocked_reason=f"Cross-category match blocked: "
                                   f"'{input_text}' ({input_category.name}) → "
                                   f"'{matched_command}' ({cmd_category.name}). "
                                   f"Confidence {match_confidence:.0%} < {cross_threshold:.0%}.",
                )

        # --- Gate 1: Risk-Based Threshold ---
        if match_confidence < threshold:
            self._stats["blocked"] += 1
            log.warning(
                "SAFETY BLOCKED: '%s' → '%s' (confidence %.2f < threshold %.2f for %s)",
                input_text, matched_command, match_confidence, threshold, risk.value
            )
            return SafetyVerdict(
                allowed=False,
                needs_confirmation=False,
                risk_level=risk,
                category=input_category,
                reason=f"Below {risk.value}-risk threshold",
                threshold=threshold,
                blocked_reason=f"Match confidence {match_confidence:.0%} is below "
                               f"the {threshold:.0%} threshold for {risk.value}-risk commands.",
            )

        # --- Gate 3: Two-Step Confirmation ---
        needs_confirm = self.needs_two_step_confirmation(matched_command)
        if needs_confirm:
            self._stats["confirmed"] += 1
        else:
            self._stats["passed"] += 1

        return SafetyVerdict(
            allowed=True,
            needs_confirmation=needs_confirm,
            risk_level=risk,
            category=input_category,
            reason="Passed all safety gates",
            threshold=threshold,
        )

    # ------------------------------------------------------------------ #
    # Category-Based Command Filtering
    # ------------------------------------------------------------------ #

    def filter_commands_by_category(
        self,
        category: IntentCategory,
        all_commands: dict[str, str],
    ) -> dict[str, str]:
        """
        Filter commands to only those matching the detected category.
        Falls back to ALL commands if category is UNKNOWN.
        
        Args:
            category: Detected intent category.
            all_commands: Full command dict {key: powershell_cmd}.
        
        Returns:
            Filtered command dict.
        """
        if category == IntentCategory.UNKNOWN:
            return all_commands

        filtered = {}
        for key, cmd in all_commands.items():
            cmd_category = self.detect_category(key)
            if cmd_category == category or cmd_category == IntentCategory.UNKNOWN:
                filtered[key] = cmd

        # If filtering is too aggressive (< 3 results), include UNKNOWN too
        if len(filtered) < 3:
            log.debug("Category filter too aggressive (%d results), using all commands", len(filtered))
            return all_commands

        log.debug("Filtered %d → %d commands for category %s",
                  len(all_commands), len(filtered), category.name)
        return filtered

    def filter_keys_by_category(
        self,
        category: IntentCategory,
        all_keys: list[str],
    ) -> list[str]:
        """
        Filter command keys to only those matching the detected category.
        Falls back to ALL keys if category is UNKNOWN.
        """
        if category == IntentCategory.UNKNOWN:
            return all_keys

        filtered = [k for k in all_keys if self.detect_category(k) in (category, IntentCategory.UNKNOWN)]

        if len(filtered) < 3:
            log.debug("Key filter too aggressive (%d results), using all keys", len(filtered))
            return all_keys

        return filtered

    def remove_dangerous_from_fuzzy(self, candidates: list[str]) -> list[str]:
        """
        Remove dangerous commands from fuzzy matching candidates.
        These commands should ONLY be triggered by exact match.
        
        Args:
            candidates: List of command keys.
        
        Returns:
            Filtered list with dangerous commands removed.
        """
        safe = [c for c in candidates if not self.contains_safeguard_word(c)]
        removed = len(candidates) - len(safe)
        if removed > 0:
            log.debug("Removed %d dangerous commands from fuzzy candidates", removed)
        return safe

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #

    def get_stats(self) -> dict:
        """Get safety gate statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {"blocked": 0, "confirmed": 0, "passed": 0}


# ====================================================================== #
# Singleton
# ====================================================================== #

_engine: CommandSafetyEngine | None = None


def get_safety_engine() -> CommandSafetyEngine:
    """Get or create the singleton safety engine."""
    global _engine
    if _engine is None:
        _engine = CommandSafetyEngine()
    return _engine
