"""
VARNA v2.1 - Startup Prewarmer
Pre-loads all expensive resources at startup for instant first-command response.

Loads:
  - Whisper/Vosk STT model
  - Semantic embeddings model
  - Command embeddings cache
  - App index
  - Pre-compiled regex patterns
  - Phonetic maps
"""

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional
from utils.logger import get_logger
from utils.timing import StartupTimer

log = get_logger(__name__)


class StartupPrewarmer:
    """
    Pre-loads expensive resources at application startup.
    
    Makes first command feel instant at the cost of slightly
    slower startup time.
    
    Usage:
        prewarmer = StartupPrewarmer()
        prewarmer.prewarm_all()
        # or async:
        prewarmer.prewarm_all_async(callback=on_ready)
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize the prewarmer.
        
        Args:
            config_path: Path to config.json.
        """
        self.config_path = config_path or str(
            Path(__file__).parent / "config.json"
        )
        self.config = self._load_config()
        self.timer = StartupTimer()
        
        # Cached resources
        self.stt_engine = None
        self.semantic_matcher = None
        self.grammar_matcher = None
        self.nlp_processor = None
        self.app_index = None
        
        self._ready = False
        self._ready_callbacks: list[Callable] = []
    
    def _load_config(self) -> dict:
        """Load configuration."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            log.warning("config.json not found, using defaults")
            return {}
    
    @property
    def is_ready(self) -> bool:
        """Check if prewarming is complete."""
        return self._ready
    
    def on_ready(self, callback: Callable) -> None:
        """
        Register a callback for when prewarming completes.
        
        Args:
            callback: Function to call when ready.
        """
        if self._ready:
            callback()
        else:
            self._ready_callbacks.append(callback)
    
    def _notify_ready(self) -> None:
        """Notify all ready callbacks."""
        self._ready = True
        for callback in self._ready_callbacks:
            try:
                callback()
            except Exception as e:
                log.error("Ready callback error: %s", e)
        self._ready_callbacks.clear()
    
    def prewarm_stt(self) -> bool:
        """Pre-load the STT engine."""
        try:
            from stt_engine import get_stt_engine
            
            log.info("Pre-warming STT engine...")
            self.stt_engine = get_stt_engine()
            
            if self.stt_engine and self.stt_engine.is_available():
                self.timer.checkpoint("stt_loaded")
                log.info("STT engine ready")
                return True
            else:
                log.warning("STT engine not available")
                return False
                
        except Exception as e:
            log.error("Failed to pre-warm STT: %s", e)
            return False
    
    def prewarm_semantic(self) -> bool:
        """Pre-load the semantic matcher and embeddings."""
        if not self.config.get("nlp", {}).get("use_semantic_fallback", True):
            log.info("Semantic matching disabled, skipping")
            return True
        
        try:
            from nlp.semantic_matcher import SemanticMatcher
            
            log.info("Pre-warming semantic matcher...")
            self.semantic_matcher = SemanticMatcher()
            
            # Try to load pre-computed embeddings
            embeddings_path = Path(__file__).parent / "models" / "embeddings.npz"
            if embeddings_path.exists():
                self.semantic_matcher.load_embeddings(str(embeddings_path))
                log.info("Loaded pre-computed command embeddings")
            else:
                # Pre-embed commands if no cache exists
                self._precompute_embeddings()
            
            self.timer.checkpoint("semantic_loaded")
            return True
            
        except ImportError as e:
            log.warning("Semantic matcher not available: %s", e)
            return False
        except Exception as e:
            log.error("Failed to pre-warm semantic: %s", e)
            return False
    
    def _precompute_embeddings(self) -> None:
        """Pre-compute and cache command embeddings."""
        try:
            # Load commands from commands.json
            commands_path = Path(__file__).parent / "commands.json"
            if not commands_path.exists():
                return
            
            with open(commands_path, "r", encoding="utf-8") as f:
                commands_data = json.load(f)
            
            # Extract all command phrases
            all_commands = set()
            
            # Static commands
            for cmd, data in commands_data.get("static", {}).items():
                all_commands.add(cmd)
                all_commands.update(data.get("synonyms", []))
            
            # Parameterized commands
            for cmd in commands_data.get("parameterized", {}).keys():
                all_commands.add(cmd)
            
            # Convert to list
            commands_list = list(all_commands)
            
            if commands_list and self.semantic_matcher:
                log.info("Pre-computing embeddings for %d commands...", len(commands_list))
                self.semantic_matcher.embed_commands(commands_list)
                self.semantic_matcher.save_embeddings()
                log.info("Command embeddings cached")
                
        except Exception as e:
            log.warning("Failed to pre-compute embeddings: %s", e)
    
    def prewarm_grammar(self) -> bool:
        """Pre-load the grammar matcher."""
        try:
            from nlp.grammar_matcher import GrammarMatcher
            
            log.info("Pre-warming grammar matcher...")
            self.grammar_matcher = GrammarMatcher()
            self.timer.checkpoint("grammar_loaded")
            return True
            
        except Exception as e:
            log.error("Failed to pre-warm grammar: %s", e)
            return False
    
    def prewarm_nlp(self) -> bool:
        """Pre-load the NLP processor."""
        try:
            from nlp import NLPProcessor
            
            log.info("Pre-warming NLP processor...")
            self.nlp_processor = NLPProcessor()
            
            # Pre-compile regex patterns by cleaning some sample text
            samples = [
                "can you please open chrome for me",
                "hey varna search for python tutorials",
                "would you help me close notepad",
            ]
            for sample in samples:
                self.nlp_processor.clean(sample)
            
            self.timer.checkpoint("nlp_loaded")
            return True
            
        except Exception as e:
            log.error("Failed to pre-warm NLP: %s", e)
            return False
    
    def prewarm_apps(self) -> bool:
        """Pre-load the app index."""
        try:
            apps_path = Path(__file__).parent / "apps.json"
            
            if apps_path.exists():
                log.info("Pre-loading app index...")
                with open(apps_path, "r", encoding="utf-8") as f:
                    self.app_index = json.load(f)
                log.info("Loaded %d apps from cache", len(self.app_index))
            else:
                log.info("No app cache found, will scan on first use")
            
            self.timer.checkpoint("apps_loaded")
            return True
            
        except Exception as e:
            log.error("Failed to pre-load apps: %s", e)
            return False
    
    def prewarm_all(self, parallel: bool = True) -> None:
        """
        Pre-load all resources.
        
        Args:
            parallel: If True, load resources in parallel threads.
        """
        log.info("=== Starting VARNA pre-warm ===")
        self.timer = StartupTimer()  # Reset timer
        
        if parallel:
            self._prewarm_parallel()
        else:
            self._prewarm_sequential()
        
        self.timer.checkpoint("prewarm_complete")
        log.info(self.timer.summary())
        log.info("=== Pre-warm complete in %.0fms ===", self.timer.total_time())
        
        self._notify_ready()
    
    def _prewarm_sequential(self) -> None:
        """Sequential prewarming."""
        self.prewarm_grammar()    # Fastest
        self.prewarm_nlp()        # Fast
        self.prewarm_apps()       # Fast
        self.prewarm_stt()        # Slower (model load)
        self.prewarm_semantic()   # Slowest (model load)
    
    def _prewarm_parallel(self) -> None:
        """Parallel prewarming using threads."""
        threads = []
        
        # Start heavier loads in parallel
        def load_stt():
            self.prewarm_stt()
        
        def load_semantic():
            self.prewarm_semantic()
        
        def load_fast():
            self.prewarm_grammar()
            self.prewarm_nlp()
            self.prewarm_apps()
        
        threads.append(threading.Thread(target=load_stt, name="Prewarm-STT"))
        threads.append(threading.Thread(target=load_semantic, name="Prewarm-Semantic"))
        threads.append(threading.Thread(target=load_fast, name="Prewarm-Fast"))
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
    
    def prewarm_all_async(self, callback: Callable = None) -> threading.Thread:
        """
        Pre-load all resources asynchronously.
        
        Args:
            callback: Optional callback when complete.
        
        Returns:
            The background thread.
        """
        if callback:
            self.on_ready(callback)
        
        thread = threading.Thread(
            target=self.prewarm_all,
            name="Prewarm-All",
            daemon=True
        )
        thread.start()
        return thread
    
    def get_status(self) -> dict:
        """Get prewarming status."""
        return {
            "ready": self._ready,
            "stt_loaded": self.stt_engine is not None,
            "semantic_loaded": self.semantic_matcher is not None,
            "grammar_loaded": self.grammar_matcher is not None,
            "nlp_loaded": self.nlp_processor is not None,
            "apps_loaded": self.app_index is not None,
            "startup_time_ms": self.timer.total_time() if self._ready else None,
        }


# Singleton instance
_prewarmer: Optional[StartupPrewarmer] = None


def get_prewarmer() -> StartupPrewarmer:
    """Get or create the global prewarmer instance."""
    global _prewarmer
    if _prewarmer is None:
        _prewarmer = StartupPrewarmer()
    return _prewarmer


def prewarm() -> None:
    """Convenience function to prewarm all resources."""
    get_prewarmer().prewarm_all()


def prewarm_async(callback: Callable = None) -> threading.Thread:
    """Convenience function to prewarm all resources asynchronously."""
    return get_prewarmer().prewarm_all_async(callback)
