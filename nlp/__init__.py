"""
VARNA v2.0 - Enhanced NLP Package
Provides layered natural language processing for command recognition.

Architecture:
    Input → Normalize → Exact match → Fuzzy (≥0.85) → Phonetic → Semantic (≥0.65) → Fail

Modules:
    - normalizer: Filler word removal, text cleaning
    - fuzzy_matcher: Enhanced fuzzy matching with phonetic support
    - semantic_matcher: ML-based semantic similarity (sentence-transformers)

Usage:
    from nlp import NLPProcessor
    processor = NLPProcessor()
    match, confidence, method = processor.match("launch crome", commands)
"""

from .normalizer import TextNormalizer, clean_text
from .fuzzy_matcher import FuzzyMatcher, phonetic_match
from .semantic_matcher import SemanticMatcher

__all__ = [
    "NLPProcessor",
    "TextNormalizer",
    "FuzzyMatcher", 
    "SemanticMatcher",
    "clean_text",
    "phonetic_match",
]


class NLPProcessor:
    """
    Unified NLP processor with layered matching strategy.
    
    Tries matching methods in order of speed, falling back as needed:
    1. Exact match (fastest)
    2. Fuzzy string matching (fast, handles typos)
    3. Phonetic matching (fast, handles pronunciation variants)
    4. Semantic matching (slower, handles paraphrases)
    """
    
    def __init__(self, config: dict = None):
        """
        Initialize the NLP processor.
        
        Args:
            config: Optional config dict. If None, loads from config.json.
        """
        import json
        from pathlib import Path
        
        if config is None:
            config_path = Path(__file__).parent.parent / "config.json"
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except FileNotFoundError:
                config = {}
        
        nlp_config = config.get("nlp", {})
        
        self.fuzzy_threshold = nlp_config.get("fuzzy_threshold", 0.70)
        self.semantic_threshold = nlp_config.get("semantic_threshold", 0.65)
        self.phonetic_enabled = nlp_config.get("phonetic_enabled", True)
        self.use_semantic = nlp_config.get("use_semantic_fallback", True)
        
        # Initialize matchers
        self.normalizer = TextNormalizer()
        self.fuzzy_matcher = FuzzyMatcher(threshold=self.fuzzy_threshold)
        self.semantic_matcher = None  # Lazy loaded
        
        self._commands_embedded = False
        
    def _ensure_semantic(self) -> bool:
        """Lazy-load semantic matcher."""
        if self.semantic_matcher is None and self.use_semantic:
            try:
                self.semantic_matcher = SemanticMatcher(
                    threshold=self.semantic_threshold
                )
                return True
            except Exception as e:
                from utils.logger import get_logger
                log = get_logger(__name__)
                log.warning("Semantic matcher unavailable: %s", e)
                self.use_semantic = False
                return False
        return self.semantic_matcher is not None
    
    def preload_commands(self, commands: list[str]) -> None:
        """
        Pre-embed commands for faster semantic matching.
        Call this at startup with your command list.
        
        Args:
            commands: List of command strings to embed.
        """
        if self._ensure_semantic() and self.semantic_matcher:
            self.semantic_matcher.embed_commands(commands)
            self._commands_embedded = True
    
    def clean(self, text: str) -> str:
        """Remove filler words and normalize text."""
        return self.normalizer.clean(text)
    
    def match(
        self, 
        text: str, 
        candidates: list[str],
        skip_semantic: bool = False
    ) -> tuple[str | None, float, str]:
        """
        Find the best matching command using layered strategy.
        
        Args:
            text: User input (already cleaned).
            candidates: List of valid command strings.
            skip_semantic: If True, skip semantic matching (for speed).
        
        Returns:
            Tuple of (matched_command, confidence, method_used).
            method_used is one of: "exact", "fuzzy", "phonetic", "semantic", "none"
        """
        if not text or not candidates:
            return None, 0.0, "none"
        
        text_lower = text.lower().strip()
        
        # 1. Exact match
        if text_lower in candidates:
            return text_lower, 1.0, "exact"
        
        # Also check normalized versions
        candidates_lower = {c.lower(): c for c in candidates}
        if text_lower in candidates_lower:
            return candidates_lower[text_lower], 1.0, "exact"
        
        # 2. High-confidence fuzzy match (≥0.85)
        fuzzy_result = self.fuzzy_matcher.match(
            text_lower, candidates, threshold=0.85
        )
        if fuzzy_result:
            return fuzzy_result[0], fuzzy_result[1], "fuzzy"
        
        # 3. Phonetic match
        if self.phonetic_enabled:
            phonetic_result = self.fuzzy_matcher.phonetic_match(
                text_lower, candidates
            )
            if phonetic_result:
                return phonetic_result[0], phonetic_result[1], "phonetic"
        
        # 4. Lower-threshold fuzzy match (≥0.70)
        fuzzy_result = self.fuzzy_matcher.match(
            text_lower, candidates, threshold=self.fuzzy_threshold
        )
        if fuzzy_result:
            return fuzzy_result[0], fuzzy_result[1], "fuzzy"
        
        # 5. Semantic match (slowest, but handles paraphrases)
        if not skip_semantic and self.use_semantic and self._ensure_semantic():
            semantic_result = self.semantic_matcher.match(text_lower, candidates)
            if semantic_result:
                return semantic_result[0], semantic_result[1], "semantic"
        
        return None, 0.0, "none"
    
    def extract_intent(self, text: str) -> tuple[str | None, str | None, str | None]:
        """
        Extract (intent, object, parameter) from natural speech.
        
        Delegates to TextNormalizer.extract_intent.
        """
        return self.normalizer.extract_intent(text)
    
    def get_suggestions(
        self, 
        text: str, 
        candidates: list[str], 
        n: int = 3
    ) -> list[tuple[str, float]]:
        """
        Get top N suggestions for ambiguous input.
        
        Args:
            text: User input.
            candidates: Valid command strings.
            n: Number of suggestions to return.
        
        Returns:
            List of (command, confidence) tuples, sorted by confidence.
        """
        suggestions = []
        text_lower = text.lower().strip()
        
        # Get fuzzy suggestions
        fuzzy_matches = self.fuzzy_matcher.match_all(
            text_lower, candidates, n=n, threshold=0.5
        )
        suggestions.extend(fuzzy_matches)
        
        # Get semantic suggestions if available
        if self.use_semantic and self._ensure_semantic() and self.semantic_matcher:
            semantic_matches = self.semantic_matcher.match_all(
                text_lower, candidates, n=n
            )
            suggestions.extend(semantic_matches)
        
        # Deduplicate and sort by confidence
        seen = set()
        unique = []
        for cmd, conf in sorted(suggestions, key=lambda x: -x[1]):
            if cmd not in seen:
                seen.add(cmd)
                unique.append((cmd, conf))
        
        return unique[:n]
