"""
VARNA v2.0 - Enhanced Fuzzy Matcher
Advanced fuzzy string matching with phonetic support.

Features:
  - Standard fuzzy matching (difflib)
  - Phonetic matching (metaphone/soundex for pronunciation variants)
  - Levenshtein distance calculation
  - Adaptive thresholds based on input length
"""

from difflib import get_close_matches, SequenceMatcher
from functools import lru_cache
from utils.logger import get_logger

log = get_logger(__name__)

# Phonetic encoding tables
_METAPHONE_RULES = {
    # Common letter mappings for Double Metaphone approximation
    'ph': 'f', 'gh': 'f', 'gn': 'n', 'kn': 'n', 'pn': 'n',
    'wr': 'r', 'ps': 's', 'wh': 'w', 'ck': 'k', 'dg': 'j',
    'sc': 's', 'ce': 's', 'ci': 's', 'cy': 's',
    'ge': 'j', 'gi': 'j', 'gy': 'j',
}

# Vowel replacements for phonetic encoding
_VOWELS = set('aeiou')


def _simple_metaphone(word: str) -> str:
    """
    Simple phonetic encoding similar to metaphone.
    
    Converts words to their phonetic representation for
    matching pronunciation variants.
    
    Args:
        word: Input word.
    
    Returns:
        Phonetic code.
    """
    if not word:
        return ""
    
    word = word.lower().strip()
    
    # Apply digraph rules
    for digraph, replacement in _METAPHONE_RULES.items():
        word = word.replace(digraph, replacement)
    
    # Remove vowels except at start
    if len(word) > 1:
        word = word[0] + ''.join(c for c in word[1:] if c not in _VOWELS)
    
    # Remove consecutive duplicate letters
    result = []
    prev = None
    for c in word:
        if c != prev:
            result.append(c)
            prev = c
    
    return ''.join(result).upper()


def _soundex(word: str) -> str:
    """
    Soundex phonetic algorithm.
    
    Classic algorithm for matching names that sound similar.
    
    Args:
        word: Input word.
    
    Returns:
        4-character soundex code.
    """
    if not word:
        return "0000"
    
    word = ''.join(c for c in word.upper() if c.isalpha())
    if not word:
        return "0000"
    
    # Soundex letter-to-digit mapping
    mapping = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6',
    }
    
    first_letter = word[0]
    rest = word[1:]
    
    # Encode remaining letters
    coded = []
    prev_code = mapping.get(first_letter, '')
    for char in rest:
        code = mapping.get(char, '')
        if code and code != prev_code:
            coded.append(code)
        prev_code = code if code else prev_code
    
    # Build soundex: first letter + 3 digits
    soundex = first_letter + ''.join(coded)
    soundex = soundex[:4].ljust(4, '0')
    
    return soundex


@lru_cache(maxsize=1000)
def phonetic_encode(word: str) -> tuple[str, str]:
    """
    Get both metaphone and soundex encodings for a word.
    
    Args:
        word: Input word.
    
    Returns:
        Tuple of (metaphone_code, soundex_code).
    """
    return (_simple_metaphone(word), _soundex(word))


def phonetic_match(
    text: str, 
    candidates: list[str],
    threshold: float = 0.8
) -> tuple[str, float] | None:
    """
    Find phonetically similar matches.
    
    Useful for handling speech recognition errors where the
    recognized word sounds like the intended word.
    
    Args:
        text: User input.
        candidates: Valid command strings.
        threshold: Minimum similarity for phonetic codes.
    
    Returns:
        Tuple of (best_match, confidence) or None.
    """
    if not text or not candidates:
        return None
    
    text_codes = phonetic_encode(text.split()[0] if ' ' in text else text)
    best_match = None
    best_score = 0.0
    
    for candidate in candidates:
        # Get first word of candidate for comparison
        candidate_word = candidate.split()[0] if ' ' in candidate else candidate
        candidate_codes = phonetic_encode(candidate_word)
        
        # Check metaphone match
        if text_codes[0] and candidate_codes[0]:
            meta_score = SequenceMatcher(
                None, text_codes[0], candidate_codes[0]
            ).ratio()
        else:
            meta_score = 0.0
        
        # Check soundex match
        if text_codes[1] == candidate_codes[1]:
            soundex_score = 0.9  # Exact soundex match
        else:
            # Partial soundex comparison
            soundex_score = SequenceMatcher(
                None, text_codes[1], candidate_codes[1]
            ).ratio() * 0.8
        
        # Combine scores
        score = max(meta_score, soundex_score)
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate
    
    if best_match:
        log.info("Phonetic match: '%s' → '%s' (score=%.2f)", text, best_match, best_score)
        return (best_match, best_score)
    
    return None


class FuzzyMatcher:
    """
    Advanced fuzzy string matcher with multiple strategies.
    
    Combines difflib matching with phonetic algorithms for
    robust command recognition despite speech errors.
    """
    
    def __init__(self, threshold: float = 0.70):
        """
        Initialize the fuzzy matcher.
        
        Args:
            threshold: Default similarity threshold (0.0 to 1.0).
        """
        self.threshold = threshold
        self._cache = {}
    
    def match(
        self, 
        text: str, 
        candidates: list[str],
        threshold: float = None
    ) -> tuple[str, float] | None:
        """
        Find the best fuzzy match for text.
        
        Args:
            text: User input (should be cleaned/normalized).
            candidates: List of valid command strings.
            threshold: Similarity threshold (uses default if None).
        
        Returns:
            Tuple of (best_match, confidence) or None.
        """
        if not text or not candidates:
            return None
        
        threshold = threshold if threshold is not None else self.threshold
        
        # Check cache
        cache_key = (text, tuple(sorted(candidates)), threshold)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Use difflib for fuzzy matching
        matches = get_close_matches(text, candidates, n=1, cutoff=threshold)
        
        if matches:
            # Calculate actual similarity score
            score = SequenceMatcher(None, text, matches[0]).ratio()
            result = (matches[0], score)
            log.info("Fuzzy match: '%s' → '%s' (score=%.2f)", text, matches[0], score)
        else:
            result = None
            log.debug("No fuzzy match for '%s' (threshold=%.2f)", text, threshold)
        
        # Cache result
        self._cache[cache_key] = result
        return result
    
    def match_all(
        self, 
        text: str, 
        candidates: list[str],
        n: int = 5,
        threshold: float = 0.5
    ) -> list[tuple[str, float]]:
        """
        Get all matches above threshold, sorted by score.
        
        Args:
            text: User input.
            candidates: Valid command strings.
            n: Maximum number of matches to return.
            threshold: Minimum similarity threshold.
        
        Returns:
            List of (match, score) tuples sorted by score descending.
        """
        if not text or not candidates:
            return []
        
        matches = get_close_matches(text, candidates, n=n, cutoff=threshold)
        
        results = []
        for match in matches:
            score = SequenceMatcher(None, text, match).ratio()
            results.append((match, score))
        
        return sorted(results, key=lambda x: -x[1])
    
    def phonetic_match(
        self, 
        text: str, 
        candidates: list[str],
        threshold: float = 0.8
    ) -> tuple[str, float] | None:
        """
        Find phonetically similar matches.
        
        Args:
            text: User input.
            candidates: Valid command strings.
            threshold: Minimum phonetic similarity.
        
        Returns:
            Tuple of (best_match, confidence) or None.
        """
        return phonetic_match(text, candidates, threshold)
    
    def adaptive_threshold(self, text: str) -> float:
        """
        Calculate adaptive threshold based on input length.
        
        Shorter inputs need higher threshold (less room for error).
        Longer inputs can use lower threshold (more context).
        
        Args:
            text: User input.
        
        Returns:
            Adjusted threshold value.
        """
        length = len(text)
        
        if length <= 3:
            return 0.90  # Very strict for short inputs
        elif length <= 6:
            return 0.80  # Strict for short-medium
        elif length <= 12:
            return 0.70  # Normal threshold
        else:
            return 0.65  # Relaxed for longer inputs
    
    def levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein (edit) distance between two strings.
        
        Args:
            s1: First string.
            s2: Second string.
        
        Returns:
            Number of single-character edits to transform s1 to s2.
        """
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def similarity_score(self, s1: str, s2: str) -> float:
        """
        Calculate similarity score based on Levenshtein distance.
        
        Args:
            s1: First string.
            s2: Second string.
        
        Returns:
            Similarity score between 0 and 1.
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        distance = self.levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))
        return 1.0 - (distance / max_len)
    
    def clear_cache(self) -> None:
        """Clear the match result cache."""
        self._cache.clear()
