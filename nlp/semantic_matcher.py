"""
VARNA v2.0 - Semantic Matcher
ML-based semantic similarity matching using sentence transformers.

Uses pre-trained sentence embeddings to find semantically similar
commands even when the wording is completely different.

Example:
    "launch the web browser" → matches "open chrome"
    "terminate the application" → matches "close app"
"""

import json
from pathlib import Path
from functools import lru_cache
from utils.logger import get_logger

log = get_logger(__name__)

# Try to import sentence-transformers
_SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    log.warning("sentence-transformers not installed. Semantic matching disabled.")
    log.info("Install with: pip install sentence-transformers")


def _cosine_similarity(vec1, vec2) -> float:
    """Calculate cosine similarity between two vectors."""
    if not _SENTENCE_TRANSFORMERS_AVAILABLE:
        return 0.0
    
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))


class SemanticMatcher:
    """
    Semantic similarity matcher using sentence embeddings.
    
    Uses a lightweight sentence transformer model (MiniLM-L6-v2)
    for fast, accurate semantic matching.
    
    Model info:
        - Size: ~80MB
        - Embedding dim: 384
        - Inference: ~20-50ms per sentence on CPU
    """
    
    # Default model - small, fast, good accuracy
    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    
    def __init__(
        self, 
        model_name: str = None,
        threshold: float = 0.65,
        cache_embeddings: bool = True
    ):
        """
        Initialize the semantic matcher.
        
        Args:
            model_name: Sentence transformer model name.
            threshold: Minimum similarity threshold (0.0 to 1.0).
            cache_embeddings: Whether to cache command embeddings.
        """
        if not _SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required for semantic matching. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name or self.DEFAULT_MODEL
        self.threshold = threshold
        self.cache_embeddings = cache_embeddings
        
        self.model = None
        self._command_embeddings = {}
        self._embedding_cache = {}
        
        self._load_model()
    
    def _load_model(self) -> None:
        """Load the sentence transformer model."""
        try:
            log.info("Loading semantic model '%s'...", self.model_name)
            
            # Set cache directory
            cache_dir = Path(__file__).parent.parent / "models" / "sentence-transformers"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            self.model = SentenceTransformer(
                self.model_name,
                cache_folder=str(cache_dir)
            )
            
            log.info("Semantic model loaded successfully")
            
        except Exception as e:
            log.error("Failed to load semantic model: %s", e)
            raise
    
    def embed(self, text: str):
        """
        Get embedding vector for text.
        
        Args:
            text: Input text to embed.
        
        Returns:
            Embedding vector (numpy array).
        """
        if self.model is None:
            return None
        
        # Check cache
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        
        # Generate embedding
        embedding = self.model.encode(text, convert_to_numpy=True)
        
        # Cache if enabled
        if self.cache_embeddings:
            self._embedding_cache[text] = embedding
        
        return embedding
    
    def embed_commands(self, commands: list[str]) -> None:
        """
        Pre-embed a list of commands for faster matching.
        
        Call this at startup with your command list.
        
        Args:
            commands: List of command strings to embed.
        """
        if self.model is None:
            return
        
        log.info("Pre-embedding %d commands...", len(commands))
        
        # Batch encode for efficiency
        embeddings = self.model.encode(commands, convert_to_numpy=True)
        
        for cmd, emb in zip(commands, embeddings):
            self._command_embeddings[cmd] = emb
            self._embedding_cache[cmd] = emb
        
        log.info("Command embeddings cached")
    
    def match(
        self, 
        text: str, 
        candidates: list[str],
        threshold: float = None
    ) -> tuple[str, float] | None:
        """
        Find the best semantic match for text.
        
        Args:
            text: User input.
            candidates: List of valid command strings.
            threshold: Similarity threshold (uses default if None).
        
        Returns:
            Tuple of (best_match, confidence) or None.
        """
        if self.model is None or not text or not candidates:
            return None
        
        threshold = threshold if threshold is not None else self.threshold
        
        # Get input embedding
        text_embedding = self.embed(text)
        if text_embedding is None:
            return None
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            # Get candidate embedding (from cache if available)
            if candidate in self._command_embeddings:
                candidate_embedding = self._command_embeddings[candidate]
            else:
                candidate_embedding = self.embed(candidate)
            
            if candidate_embedding is None:
                continue
            
            # Calculate similarity
            score = _cosine_similarity(text_embedding, candidate_embedding)
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        if best_match and best_score >= threshold:
            log.info("Semantic match: '%s' → '%s' (score=%.2f)", text, best_match, best_score)
            return (best_match, best_score)
        
        log.debug("No semantic match for '%s' (best=%.2f, threshold=%.2f)", 
                  text, best_score, threshold)
        return None
    
    def match_all(
        self, 
        text: str, 
        candidates: list[str],
        n: int = 5,
        threshold: float = None
    ) -> list[tuple[str, float]]:
        """
        Get all semantic matches above threshold, sorted by score.
        
        Args:
            text: User input.
            candidates: Valid command strings.
            n: Maximum number of matches to return.
            threshold: Minimum similarity threshold.
        
        Returns:
            List of (match, score) tuples sorted by score descending.
        """
        if self.model is None or not text or not candidates:
            return []
        
        threshold = threshold if threshold is not None else self.threshold * 0.7
        
        # Get input embedding
        text_embedding = self.embed(text)
        if text_embedding is None:
            return []
        
        # Score all candidates
        scores = []
        for candidate in candidates:
            if candidate in self._command_embeddings:
                candidate_embedding = self._command_embeddings[candidate]
            else:
                candidate_embedding = self.embed(candidate)
            
            if candidate_embedding is not None:
                score = _cosine_similarity(text_embedding, candidate_embedding)
                if score >= threshold:
                    scores.append((candidate, score))
        
        # Sort by score descending
        scores.sort(key=lambda x: -x[1])
        
        return scores[:n]
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts.
        
        Args:
            text1: First text.
            text2: Second text.
        
        Returns:
            Similarity score between 0 and 1.
        """
        if self.model is None:
            return 0.0
        
        emb1 = self.embed(text1)
        emb2 = self.embed(text2)
        
        if emb1 is None or emb2 is None:
            return 0.0
        
        return _cosine_similarity(emb1, emb2)
    
    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._embedding_cache.clear()
        # Keep command embeddings (they're expensive to recompute)
    
    def save_embeddings(self, filepath: str = None) -> None:
        """
        Save pre-computed command embeddings to file.
        
        Args:
            filepath: Path to save embeddings. Defaults to models/embeddings.json.
        """
        if not self._command_embeddings:
            return
        
        filepath = filepath or str(
            Path(__file__).parent.parent / "models" / "embeddings.npz"
        )
        
        # Save as numpy archive
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        commands = list(self._command_embeddings.keys())
        embeddings = np.array([self._command_embeddings[c] for c in commands])
        
        np.savez(
            filepath,
            commands=commands,
            embeddings=embeddings
        )
        
        log.info("Saved %d command embeddings to %s", len(commands), filepath)
    
    def load_embeddings(self, filepath: str = None) -> bool:
        """
        Load pre-computed command embeddings from file.
        
        Args:
            filepath: Path to load embeddings from.
        
        Returns:
            True if loaded successfully, False otherwise.
        """
        filepath = filepath or str(
            Path(__file__).parent.parent / "models" / "embeddings.npz"
        )
        
        try:
            data = np.load(filepath, allow_pickle=True)
            commands = data['commands']
            embeddings = data['embeddings']
            
            for cmd, emb in zip(commands, embeddings):
                self._command_embeddings[cmd] = emb
                self._embedding_cache[cmd] = emb
            
            log.info("Loaded %d command embeddings from %s", len(commands), filepath)
            return True
            
        except FileNotFoundError:
            log.debug("No saved embeddings found at %s", filepath)
            return False
        except Exception as e:
            log.warning("Failed to load embeddings: %s", e)
            return False
