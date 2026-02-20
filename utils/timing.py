"""
VARNA v2.1 - Performance Timing Utilities
Debug timing for end-to-end latency measurement.

Tracks:
  - Mic capture time
  - STT time
  - NLP time
  - Execution time
  - TTS time

Use to identify and optimize the slowest layers.
"""

import time
import json
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable
from contextlib import contextmanager
from functools import wraps
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class TimingResult:
    """Single timing measurement."""
    name: str
    duration_ms: float
    timestamp: float = field(default_factory=time.time)
    
    def __str__(self) -> str:
        return f"{self.name}: {self.duration_ms:.1f}ms"


@dataclass
class PipelineMetrics:
    """Complete pipeline timing metrics."""
    mic_capture: float = 0.0
    stt: float = 0.0
    nlp_clean: float = 0.0
    nlp_match: float = 0.0
    execution: float = 0.0
    tts: float = 0.0
    total: float = 0.0
    
    @property
    def nlp_total(self) -> float:
        """Total NLP time."""
        return self.nlp_clean + self.nlp_match
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mic_capture_ms": round(self.mic_capture, 1),
            "stt_ms": round(self.stt, 1),
            "nlp_clean_ms": round(self.nlp_clean, 1),
            "nlp_match_ms": round(self.nlp_match, 1),
            "execution_ms": round(self.execution, 1),
            "tts_ms": round(self.tts, 1),
            "total_ms": round(self.total, 1),
        }
    
    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"Total: {self.total:.0f}ms | "
            f"STT: {self.stt:.0f}ms | "
            f"NLP: {self.nlp_total:.0f}ms | "
            f"Exec: {self.execution:.0f}ms | "
            f"TTS: {self.tts:.0f}ms"
        )
    
    def identify_bottleneck(self) -> str:
        """Identify the slowest layer."""
        layers = {
            "mic_capture": self.mic_capture,
            "stt": self.stt,
            "nlp": self.nlp_total,
            "execution": self.execution,
            "tts": self.tts,
        }
        return max(layers, key=layers.get)


class PerformanceTimer:
    """
    Performance timing utility for measuring pipeline latency.
    
    Usage:
        timer = PerformanceTimer()
        
        with timer.measure("stt"):
            text = listener.listen()
        
        with timer.measure("nlp"):
            result = parser.parse(text)
        
        metrics = timer.get_metrics()
        print(metrics.summary())
    """
    
    def __init__(self, enabled: bool = True):
        """
        Initialize the timer.
        
        Args:
            enabled: Whether timing is enabled.
        """
        self.enabled = enabled
        self._timings: dict[str, float] = {}
        self._start_time: float = 0.0
        self._lock = threading.Lock()
        
        # History for averaging
        self._history: list[PipelineMetrics] = []
        self._max_history = 100
    
    def start(self) -> None:
        """Start a new timing session."""
        with self._lock:
            self._timings.clear()
            self._start_time = time.perf_counter()
    
    @contextmanager
    def measure(self, name: str):
        """
        Context manager to measure a code block.
        
        Args:
            name: Name of the operation being measured.
        """
        if not self.enabled:
            yield
            return
        
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            with self._lock:
                self._timings[name] = elapsed_ms
            log.debug("⏱ %s: %.1fms", name, elapsed_ms)
    
    def record(self, name: str, duration_ms: float) -> None:
        """
        Manually record a timing.
        
        Args:
            name: Name of the operation.
            duration_ms: Duration in milliseconds.
        """
        if not self.enabled:
            return
        
        with self._lock:
            self._timings[name] = duration_ms
    
    def get_metrics(self) -> PipelineMetrics:
        """
        Get complete pipeline metrics.
        
        Returns:
            PipelineMetrics object with all timings.
        """
        with self._lock:
            metrics = PipelineMetrics(
                mic_capture=self._timings.get("mic_capture", 0.0),
                stt=self._timings.get("stt", 0.0),
                nlp_clean=self._timings.get("nlp_clean", 0.0),
                nlp_match=self._timings.get("nlp_match", 0.0),
                execution=self._timings.get("execution", 0.0),
                tts=self._timings.get("tts", 0.0),
                total=(time.perf_counter() - self._start_time) * 1000 if self._start_time else 0.0,
            )
            
            # Add to history
            self._history.append(metrics)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            
            return metrics
    
    def get_average_metrics(self) -> PipelineMetrics:
        """Get average metrics over history."""
        if not self._history:
            return PipelineMetrics()
        
        n = len(self._history)
        return PipelineMetrics(
            mic_capture=sum(m.mic_capture for m in self._history) / n,
            stt=sum(m.stt for m in self._history) / n,
            nlp_clean=sum(m.nlp_clean for m in self._history) / n,
            nlp_match=sum(m.nlp_match for m in self._history) / n,
            execution=sum(m.execution for m in self._history) / n,
            tts=sum(m.tts for m in self._history) / n,
            total=sum(m.total for m in self._history) / n,
        )
    
    def print_summary(self) -> None:
        """Print timing summary to log."""
        metrics = self.get_metrics()
        log.info("⏱ Pipeline: %s", metrics.summary())
        
        bottleneck = metrics.identify_bottleneck()
        if bottleneck:
            log.info("⏱ Bottleneck: %s", bottleneck)
    
    def export_history(self, filepath: str = None) -> None:
        """Export timing history to JSON file."""
        filepath = filepath or str(
            Path(__file__).parent / "logs" / "timing_history.json"
        )
        
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    [m.to_dict() for m in self._history],
                    f, indent=2
                )
            log.info("Exported timing history to %s", filepath)
        except Exception as e:
            log.error("Failed to export timing history: %s", e)


def timed(name: str = None):
    """
    Decorator to time a function.
    
    Args:
        name: Optional name (defaults to function name).
    
    Usage:
        @timed("stt")
        def recognize_audio(audio):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = name or func.__name__
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                log.debug("⏱ %s: %.1fms", func_name, elapsed_ms)
        return wrapper
    return decorator


class StartupTimer:
    """Timer specifically for measuring startup performance."""
    
    def __init__(self):
        self.start_time = time.perf_counter()
        self.checkpoints: list[tuple[str, float]] = []
    
    def checkpoint(self, name: str) -> None:
        """Record a startup checkpoint."""
        elapsed = (time.perf_counter() - self.start_time) * 1000
        self.checkpoints.append((name, elapsed))
        log.info("⏱ Startup: %s at %.0fms", name, elapsed)
    
    def total_time(self) -> float:
        """Get total startup time in milliseconds."""
        return (time.perf_counter() - self.start_time) * 1000
    
    def summary(self) -> str:
        """Get startup time summary."""
        lines = ["Startup timing:"]
        prev_time = 0.0
        for name, elapsed in self.checkpoints:
            delta = elapsed - prev_time
            lines.append(f"  {name}: +{delta:.0f}ms (total: {elapsed:.0f}ms)")
            prev_time = elapsed
        lines.append(f"  Total: {self.total_time():.0f}ms")
        return "\n".join(lines)


# Global timer instance
_global_timer: Optional[PerformanceTimer] = None


def get_timer() -> PerformanceTimer:
    """Get or create the global timer instance."""
    global _global_timer
    if _global_timer is None:
        _global_timer = PerformanceTimer()
    return _global_timer


def enable_timing(enabled: bool = True) -> None:
    """Enable or disable global timing."""
    get_timer().enabled = enabled
