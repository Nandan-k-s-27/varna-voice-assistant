"""
VARNA v2.1 - Intent Scoring Engine
Weighted scoring system for intelligent command matching.

Replaces rigid thresholds with weighted composite scoring:
    score = exact * 1.0 + fuzzy * 0.6 + phonetic * 0.5 + semantic * 0.8 + context * 0.3

This makes VARNA deterministic but intelligent.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class IntentScore:
    """Represents a scored intent match."""
    command: str
    exact_score: float = 0.0
    fuzzy_score: float = 0.0
    phonetic_score: float = 0.0
    semantic_score: float = 0.0
    context_bonus: float = 0.0
    grammar_score: float = 0.0
    
    # Weights for each scoring component
    WEIGHTS = {
        "exact": 1.0,
        "fuzzy": 0.6,
        "phonetic": 0.5,
        "semantic": 0.8,
        "context": 0.3,
        "grammar": 0.7,
    }
    
    @property
    def total_score(self) -> float:
        """Calculate weighted total score."""
        return (
            self.exact_score * self.WEIGHTS["exact"] +
            self.fuzzy_score * self.WEIGHTS["fuzzy"] +
            self.phonetic_score * self.WEIGHTS["phonetic"] +
            self.semantic_score * self.WEIGHTS["semantic"] +
            self.context_bonus * self.WEIGHTS["context"] +
            self.grammar_score * self.WEIGHTS["grammar"]
        )
    
    @property
    def primary_method(self) -> str:
        """Get the highest-contributing method."""
        scores = {
            "exact": self.exact_score * self.WEIGHTS["exact"],
            "fuzzy": self.fuzzy_score * self.WEIGHTS["fuzzy"],
            "phonetic": self.phonetic_score * self.WEIGHTS["phonetic"],
            "semantic": self.semantic_score * self.WEIGHTS["semantic"],
            "grammar": self.grammar_score * self.WEIGHTS["grammar"],
        }
        return max(scores, key=scores.get)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "command": self.command,
            "total": round(self.total_score, 3),
            "exact": self.exact_score,
            "fuzzy": self.fuzzy_score,
            "phonetic": self.phonetic_score,
            "semantic": self.semantic_score,
            "context": self.context_bonus,
            "grammar": self.grammar_score,
            "method": self.primary_method,
        }


class IntentScoringEngine:
    """
    Intelligent intent matching using weighted composite scoring.
    
    Instead of rigid thresholds, calculates weighted scores from
    multiple matching methods and picks the highest-scoring intent.
    """
    
    # Minimum total score to consider a match valid
    MIN_CONFIDENCE = 0.45
    
    # Score boost for recently used commands
    RECENCY_BOOST = 0.15
    
    # Score boost for frequently used commands
    FREQUENCY_BOOST = 0.10
    
    def __init__(
        self, 
        fuzzy_matcher=None,
        semantic_matcher=None,
        grammar_matcher=None,
        context_engine=None
    ):
        """
        Initialize the scoring engine.
        
        Args:
            fuzzy_matcher: FuzzyMatcher instance.
            semantic_matcher: SemanticMatcher instance.
            grammar_matcher: GrammarMatcher instance.
            context_engine: SessionContext instance.
        """
        self.fuzzy_matcher = fuzzy_matcher
        self.semantic_matcher = semantic_matcher
        self.grammar_matcher = grammar_matcher
        self.context_engine = context_engine
        
        # Track command usage for context bonuses
        self._recent_commands: list[str] = []
        self._command_frequency: dict[str, int] = {}
        
        # User corrections for learning
        self._corrections_path = Path(__file__).parent / "user_corrections.json"
        self._corrections: dict[str, str] = self._load_corrections()
    
    def _load_corrections(self) -> dict:
        """Load user corrections from file."""
        try:
            if self._corrections_path.exists():
                with open(self._corrections_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            log.warning("Failed to load corrections: %s", e)
        return {}
    
    def _save_corrections(self) -> None:
        """Save user corrections to file."""
        try:
            with open(self._corrections_path, "w", encoding="utf-8") as f:
                json.dump(self._corrections, f, indent=2)
        except Exception as e:
            log.error("Failed to save corrections: %s", e)
    
    def add_correction(self, misheard: str, intended: str) -> None:
        """
        Record a user correction for learning.
        
        Args:
            misheard: What VARNA heard/matched.
            intended: What the user actually meant.
        """
        self._corrections[misheard.lower()] = intended.lower()
        self._save_corrections()
        log.info("Learned correction: '%s' → '%s'", misheard, intended)
    
    def score_all(
        self, 
        text: str, 
        candidates: list[str],
        current_mode: str = None
    ) -> list[IntentScore]:
        """
        Score all candidates against the input text.
        
        Args:
            text: User input (cleaned).
            candidates: List of valid command strings.
            current_mode: Current context mode for bonus.
        
        Returns:
            List of IntentScore objects, sorted by total_score descending.
        """
        if not text or not candidates:
            return []
        
        text_lower = text.lower().strip()
        
        # Check for learned corrections first
        if text_lower in self._corrections:
            corrected = self._corrections[text_lower]
            log.info("Applying learned correction: '%s' → '%s'", text_lower, corrected)
            text_lower = corrected
        
        scores = []
        
        for candidate in candidates:
            score = self._score_candidate(text_lower, candidate, current_mode)
            scores.append(score)
        
        # Sort by total score descending
        scores.sort(key=lambda s: s.total_score, reverse=True)
        
        return scores
    
    def _score_candidate(
        self, 
        text: str, 
        candidate: str, 
        current_mode: str = None
    ) -> IntentScore:
        """Score a single candidate."""
        score = IntentScore(command=candidate)
        candidate_lower = candidate.lower()
        
        # 1. Exact match
        if text == candidate_lower:
            score.exact_score = 1.0
            return score  # Perfect match, no need for other checks
        
        # 2. Fuzzy match
        if self.fuzzy_matcher:
            fuzzy_result = self.fuzzy_matcher.match(
                text, [candidate], threshold=0.0  # Get score regardless of threshold
            )
            if fuzzy_result:
                score.fuzzy_score = fuzzy_result[1]
        
        # 3. Phonetic match
        if self.fuzzy_matcher:
            phonetic_result = self.fuzzy_matcher.phonetic_match(
                text, [candidate], threshold=0.0
            )
            if phonetic_result:
                score.phonetic_score = phonetic_result[1]
        
        # 4. Semantic match
        if self.semantic_matcher:
            try:
                semantic_result = self.semantic_matcher.match(
                    text, [candidate], threshold=0.0
                )
                if semantic_result:
                    score.semantic_score = semantic_result[1]
            except Exception as e:
                log.debug("Semantic scoring failed: %s", e)
        
        # 5. Grammar pattern match
        if self.grammar_matcher:
            grammar_result = self.grammar_matcher.match(text, candidate)
            if grammar_result:
                score.grammar_score = grammar_result
        
        # 6. Context bonus
        score.context_bonus = self._calculate_context_bonus(
            candidate, current_mode
        )
        
        return score
    
    def _calculate_context_bonus(
        self, 
        candidate: str, 
        current_mode: str = None
    ) -> float:
        """Calculate context-aware bonus for a candidate."""
        bonus = 0.0
        candidate_lower = candidate.lower()
        
        # Recency bonus (recently used commands)
        if candidate_lower in self._recent_commands[-5:]:
            bonus += self.RECENCY_BOOST
        
        # Frequency bonus (frequently used commands)
        freq = self._command_frequency.get(candidate_lower, 0)
        if freq > 5:
            bonus += self.FREQUENCY_BOOST
        elif freq > 2:
            bonus += self.FREQUENCY_BOOST * 0.5
        
        # Mode-based bonus
        if current_mode and self.context_engine:
            mode_commands = self._get_mode_commands(current_mode)
            if candidate_lower in mode_commands:
                bonus += 0.2
        
        return min(bonus, 1.0)  # Cap at 1.0
    
    def _get_mode_commands(self, mode: str) -> set[str]:
        """Get commands associated with a mode."""
        mode_map = {
            "browsing": {"search", "new tab", "close tab", "go back", "go forward", "refresh"},
            "coding": {"save", "undo", "redo", "copy", "paste", "select all", "find"},
            "chatting": {"send", "type", "emoji"},
            "system": {"shutdown", "restart", "lock", "sleep"},
        }
        return mode_map.get(mode, set())
    
    def match(
        self, 
        text: str, 
        candidates: list[str],
        current_mode: str = None
    ) -> tuple[str | None, float, str]:
        """
        Find the best matching command using weighted scoring.
        
        Args:
            text: User input.
            candidates: Valid command strings.
            current_mode: Current context mode.
        
        Returns:
            Tuple of (best_command, confidence, method).
        """
        scores = self.score_all(text, candidates, current_mode)
        
        if not scores:
            return None, 0.0, "none"
        
        best = scores[0]
        
        if best.total_score >= self.MIN_CONFIDENCE:
            # Record usage
            self._record_usage(best.command)
            
            log.info(
                "Intent match: '%s' → '%s' (score=%.2f, method=%s)",
                text, best.command, best.total_score, best.primary_method
            )
            return best.command, best.total_score, best.primary_method
        
        # Low confidence - return for confirmation
        log.info(
            "Low confidence match: '%s' → '%s' (score=%.2f)",
            text, best.command, best.total_score
        )
        return best.command, best.total_score, "low_confidence"
    
    def _record_usage(self, command: str) -> None:
        """Record command usage for context bonuses."""
        command_lower = command.lower()
        
        # Update recent commands
        self._recent_commands.append(command_lower)
        if len(self._recent_commands) > 20:
            self._recent_commands = self._recent_commands[-20:]
        
        # Update frequency
        self._command_frequency[command_lower] = (
            self._command_frequency.get(command_lower, 0) + 1
        )
    
    def get_suggestions(
        self, 
        text: str, 
        candidates: list[str],
        n: int = 3
    ) -> list[tuple[str, float]]:
        """
        Get top N suggestions for ambiguous input.
        
        Returns:
            List of (command, score) tuples.
        """
        scores = self.score_all(text, candidates)
        return [(s.command, s.total_score) for s in scores[:n]]
    
    def needs_confirmation(self, score: float) -> bool:
        """Check if a match score needs user confirmation."""
        return self.MIN_CONFIDENCE <= score < 0.75
