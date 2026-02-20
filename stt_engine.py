"""
VARNA v2.1 - Offline Speech-to-Text Engine
Provides fully offline STT using either Whisper or Vosk.

Supported engines:
  - faster-whisper: Higher accuracy, requires more resources (~1-2s latency)
  - vosk: Lower latency (<500ms), lightweight, works well on CPU

Performance modes:
  - ultra_fast: Whisper tiny model, lowest latency
  - balanced: Whisper base model, good balance (default)
  - accuracy: Whisper small model, best accuracy

Dynamic switching:
  - Auto-switches to tiny model when CPU > 70%

Usage:
    from stt_engine import create_stt_engine
    engine = create_stt_engine("whisper")  # or "vosk"
    text = engine.transcribe(audio_data)
"""

import json
import os
import io
import wave
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from enum import Enum
from utils.logger import get_logger

log = get_logger(__name__)

# Load config
_CONFIG_PATH = Path(__file__).parent / "config.json"


class PerformanceMode(Enum):
    """STT performance modes."""
    ULTRA_FAST = "ultra_fast"   # Whisper tiny
    BALANCED = "balanced"       # Whisper base (default)
    ACCURACY = "accuracy"       # Whisper small


# Performance mode to Whisper model mapping
_MODE_MODEL_MAP = {
    PerformanceMode.ULTRA_FAST: "tiny",
    PerformanceMode.BALANCED: "base",
    PerformanceMode.ACCURACY: "small",
}


def _load_config() -> dict:
    """Load configuration from config.json."""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        log.warning("config.json not found, using defaults")
        return {}


def _get_cpu_usage() -> float:
    """Get current CPU usage percentage."""
    try:
        import psutil
        return psutil.cpu_percent(interval=0.1)
    except ImportError:
        return 0.0
    except Exception:
        return 0.0


class STTEngine(ABC):
    """Abstract base class for speech-to-text engines."""

    @abstractmethod
    def transcribe(self, audio_data) -> str | None:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes or speech_recognition AudioData object.

        Returns:
            Transcribed text (lowercase, stripped) or None on failure.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the engine is properly initialized."""
        pass


class WhisperEngine(STTEngine):
    """
    Offline STT using faster-whisper (CTranslate2 optimized Whisper).

    Models (sorted by size/accuracy):
      - tiny: ~75MB, fastest, lower accuracy
      - base: ~150MB, good balance (recommended)
      - small: ~500MB, better accuracy
      - medium: ~1.5GB, high accuracy
      - large-v2: ~3GB, best accuracy

    Performance Modes:
      - ultra_fast: Uses tiny model
      - balanced: Uses base model (default)
      - accuracy: Uses small model

    Auto-Switch:
      - When auto_switch=True, dynamically switches to tiny model when CPU > 70%
    """

    def __init__(
        self,
        model_name: str = "base",
        compute_type: str = "int8",
        performance_mode: PerformanceMode | str | None = None,
        auto_switch: bool = False
    ):
        """
        Initialize the Whisper engine.

        Args:
            model_name: Whisper model size (tiny/base/small/medium/large-v2).
            compute_type: Quantization type (int8/float16/float32).
            performance_mode: Performance mode (overrides model_name if set).
            auto_switch: If True, auto-switch to tiny when CPU > 70%.
        """
        # Handle performance mode
        if performance_mode is not None:
            if isinstance(performance_mode, str):
                performance_mode = PerformanceMode(performance_mode)
            self.performance_mode = performance_mode
            self.model_name = _MODE_MODEL_MAP[performance_mode]
        else:
            self.performance_mode = None
            self.model_name = model_name

        self.compute_type = compute_type
        self.auto_switch = auto_switch
        self.model = None
        self._models_cache: dict[str, object] = {}  # Cache loaded models
        self._initialized = False
        self._lock = threading.Lock()
        self._current_model_name = self.model_name

        self._load_model()

    def _load_model(self, model_name: str | None = None) -> None:
        """Load the Whisper model."""
        target_model = model_name or self.model_name
        
        # Check cache first
        if target_model in self._models_cache:
            self.model = self._models_cache[target_model]
            self._current_model_name = target_model
            log.debug("Using cached Whisper model '%s'", target_model)
            return

        try:
            from faster_whisper import WhisperModel

            log.info("Loading Whisper model '%s' (compute_type=%s)...",
                     target_model, self.compute_type)

            # Use CPU with int8 quantization for best compatibility
            model = WhisperModel(
                target_model,
                device="cpu",
                compute_type=self.compute_type,
                download_root=str(Path(__file__).parent / "models" / "whisper")
            )

            # Cache the model
            self._models_cache[target_model] = model
            self.model = model
            self._current_model_name = target_model
            self._initialized = True
            log.info("Whisper model loaded successfully")

        except ImportError:
            log.error("faster-whisper not installed. Run: pip install faster-whisper")
            self._initialized = False
        except Exception as e:
            log.error("Failed to load Whisper model: %s", e)
            self._initialized = False

    def _check_auto_switch(self) -> None:
        """Check CPU usage and switch models if needed."""
        if not self.auto_switch:
            return
        
        cpu_usage = _get_cpu_usage()
        
        with self._lock:
            if cpu_usage > 70.0 and self._current_model_name != "tiny":
                log.info("CPU usage %.1f%% > 70%%, switching to tiny model", cpu_usage)
                self._load_model("tiny")
            elif cpu_usage < 50.0 and self._current_model_name == "tiny":
                # Switch back to configured model when CPU is low
                if self._current_model_name != self.model_name:
                    log.info("CPU usage %.1f%% < 50%%, switching back to %s", 
                             cpu_usage, self.model_name)
                    self._load_model(self.model_name)

    def transcribe(self, audio_data) -> str | None:
        """Transcribe audio using Whisper."""
        if not self._initialized or self.model is None:
            log.error("Whisper engine not initialized")
            return None

        # Check if we need to auto-switch models based on CPU
        self._check_auto_switch()

        try:
            # Convert AudioData to WAV bytes
            wav_bytes = self._audio_to_wav(audio_data)
            if wav_bytes is None:
                return None

            # Write to temp file (faster-whisper needs file path)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(wav_bytes)
                tmp_path = tmp.name

            try:
                # Transcribe
                segments, info = self.model.transcribe(
                    tmp_path,
                    language="en",
                    beam_size=5,
                    vad_filter=True,  # Filter out non-speech
                    vad_parameters=dict(min_silence_duration_ms=500)
                )

                # Collect all segments
                text_parts = []
                for segment in segments:
                    text_parts.append(segment.text.strip())

                text = " ".join(text_parts).lower().strip()

                if text:
                    log.info("Whisper recognized: '%s'", text)
                    return text
                else:
                    log.debug("Whisper returned empty transcription")
                    return None

            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass

        except Exception as e:
            log.error("Whisper transcription error: %s", e)
            return None

    def _audio_to_wav(self, audio_data) -> bytes | None:
        """Convert speech_recognition AudioData to WAV bytes."""
        try:
            # If it's already bytes, assume it's raw PCM
            if isinstance(audio_data, bytes):
                return audio_data

            # If it's AudioData from speech_recognition
            if hasattr(audio_data, 'get_wav_data'):
                return audio_data.get_wav_data()

            # If it's AudioData with frame_data
            if hasattr(audio_data, 'frame_data'):
                sample_rate = getattr(audio_data, 'sample_rate', 16000)
                sample_width = getattr(audio_data, 'sample_width', 2)

                buffer = io.BytesIO()
                with wave.open(buffer, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(sample_width)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_data.frame_data)
                return buffer.getvalue()

            log.error("Unknown audio data type: %s", type(audio_data))
            return None

        except Exception as e:
            log.error("Failed to convert audio to WAV: %s", e)
            return None

    def is_available(self) -> bool:
        """Check if Whisper is ready."""
        return self._initialized and self.model is not None


class VoskEngine(STTEngine):
    """
    Offline STT using Vosk (Kaldi-based).

    Lightweight and fast, good for real-time applications.
    Download models from: https://alphacephei.com/vosk/models
    """

    def __init__(self, model_path: str = None):
        """
        Initialize the Vosk engine.

        Args:
            model_path: Path to Vosk model directory.
                       If None, uses default path from config.
        """
        config = _load_config()
        self.model_path = model_path or config.get("stt", {}).get(
            "vosk_model_path", "models/vosk-model-small-en-us"
        )
        self.model = None
        self._initialized = False

        self._load_model()

    def _load_model(self) -> None:
        """Load the Vosk model."""
        try:
            from vosk import Model, SetLogLevel

            # Suppress Vosk's verbose logging
            SetLogLevel(-1)

            model_path = Path(__file__).parent / self.model_path

            if not model_path.exists():
                log.error("Vosk model not found at: %s", model_path)
                log.info("Download from: https://alphacephei.com/vosk/models")
                self._initialized = False
                return

            log.info("Loading Vosk model from '%s'...", model_path)
            self.model = Model(str(model_path))
            self._initialized = True
            log.info("Vosk model loaded successfully")

        except ImportError:
            log.error("vosk not installed. Run: pip install vosk")
            self._initialized = False
        except Exception as e:
            log.error("Failed to load Vosk model: %s", e)
            self._initialized = False

    def transcribe(self, audio_data) -> str | None:
        """Transcribe audio using Vosk."""
        if not self._initialized or self.model is None:
            log.error("Vosk engine not initialized")
            return None

        try:
            from vosk import KaldiRecognizer

            # Get raw audio data
            if hasattr(audio_data, 'frame_data'):
                raw_data = audio_data.frame_data
                sample_rate = getattr(audio_data, 'sample_rate', 16000)
            elif hasattr(audio_data, 'get_raw_data'):
                raw_data = audio_data.get_raw_data(
                    convert_rate=16000, convert_width=2
                )
                sample_rate = 16000
            else:
                raw_data = audio_data
                sample_rate = 16000

            # Create recognizer
            recognizer = KaldiRecognizer(self.model, sample_rate)
            recognizer.SetWords(True)

            # Process audio
            recognizer.AcceptWaveform(raw_data)
            result = json.loads(recognizer.FinalResult())

            text = result.get("text", "").lower().strip()

            if text:
                log.info("Vosk recognized: '%s'", text)
                return text
            else:
                log.debug("Vosk returned empty transcription")
                return None

        except Exception as e:
            log.error("Vosk transcription error: %s", e)
            return None

    def is_available(self) -> bool:
        """Check if Vosk is ready."""
        return self._initialized and self.model is not None


class GoogleFallbackEngine(STTEngine):
    """
    Fallback to Google Web Speech API when offline engines fail.
    Requires internet connection.
    """

    def __init__(self):
        """Initialize Google fallback engine."""
        import speech_recognition as sr
        self.recognizer = sr.Recognizer()
        self._initialized = True
        log.info("Google fallback engine initialized")

    def transcribe(self, audio_data) -> str | None:
        """Transcribe using Google Web Speech API."""
        import speech_recognition as sr

        try:
            text = self.recognizer.recognize_google(audio_data)
            text = text.lower().strip()
            log.info("Google recognized: '%s'", text)
            return text
        except sr.UnknownValueError:
            log.warning("Google could not understand audio")
            return None
        except sr.RequestError as e:
            log.error("Google API error: %s", e)
            return None

    def is_available(self) -> bool:
        """Google is always available (requires internet)."""
        return self._initialized


class HybridEngine(STTEngine):
    """
    Hybrid engine that tries offline first, falls back to Google.

    Order: Whisper/Vosk → Google (if offline fails)
    """

    def __init__(self, primary: str = "whisper"):
        """
        Initialize hybrid engine.

        Args:
            primary: Primary offline engine ("whisper" or "vosk").
        """
        self.primary_engine = None
        self.fallback_engine = None

        # Initialize primary
        if primary == "whisper":
            self.primary_engine = WhisperEngine()
        elif primary == "vosk":
            self.primary_engine = VoskEngine()

        # Initialize Google fallback
        self.fallback_engine = GoogleFallbackEngine()

        log.info("Hybrid engine initialized (primary=%s)", primary)

    def transcribe(self, audio_data) -> str | None:
        """Try primary engine, fall back to Google."""
        # Try primary offline engine
        if self.primary_engine and self.primary_engine.is_available():
            result = self.primary_engine.transcribe(audio_data)
            if result:
                return result

        # Fall back to Google
        log.warning("Primary STT failed, falling back to Google")
        if self.fallback_engine and self.fallback_engine.is_available():
            return self.fallback_engine.transcribe(audio_data)

        return None

    def is_available(self) -> bool:
        """Available if either engine works."""
        return (
            (self.primary_engine and self.primary_engine.is_available()) or
            (self.fallback_engine and self.fallback_engine.is_available())
        )


def create_stt_engine(engine_type: str = None) -> STTEngine:
    """
    Factory function to create the appropriate STT engine.

    Args:
        engine_type: Engine type ("whisper", "vosk", "google", "hybrid").
                    If None, reads from config.json.

    Returns:
        Initialized STT engine.
    """
    config = _load_config()

    if engine_type is None:
        engine_type = config.get("stt", {}).get("engine", "whisper")

    engine_type = engine_type.lower()

    log.info("Creating STT engine: %s", engine_type)

    if engine_type == "whisper":
        stt_config = config.get("stt", {})
        perf_config = config.get("performance", {})
        
        # Get performance mode from config
        perf_mode_str = perf_config.get("mode", "balanced")
        auto_switch = perf_config.get("auto_switch", False)
        
        try:
            perf_mode = PerformanceMode(perf_mode_str)
        except ValueError:
            log.warning("Invalid performance mode '%s', using balanced", perf_mode_str)
            perf_mode = PerformanceMode.BALANCED
        
        return WhisperEngine(
            model_name=stt_config.get("whisper_model", "base"),
            compute_type=stt_config.get("compute_type", "int8"),
            performance_mode=perf_mode,
            auto_switch=auto_switch
        )
    elif engine_type == "vosk":
        stt_config = config.get("stt", {})
        return VoskEngine(
            model_path=stt_config.get("vosk_model_path")
        )
    elif engine_type == "google":
        return GoogleFallbackEngine()
    elif engine_type == "hybrid":
        primary = config.get("stt", {}).get("engine", "whisper")
        if primary == "hybrid":
            primary = "whisper"  # Avoid infinite recursion
        return HybridEngine(primary=primary)
    else:
        log.warning("Unknown engine type '%s', defaulting to Whisper", engine_type)
        return WhisperEngine()


# Singleton instance for reuse
_engine_instance: STTEngine | None = None


def get_stt_engine() -> STTEngine:
    """Get or create the singleton STT engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = create_stt_engine()
    return _engine_instance
