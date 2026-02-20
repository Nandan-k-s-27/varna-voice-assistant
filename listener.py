"""
VARNA v2.0 - Speech-to-Text Listener
Uses the `speech_recognition` library for microphone capture
with offline STT (Whisper/Vosk) or Google fallback.

v2.0 additions:
  • Offline STT support (Whisper/Vosk)
  • Configurable STT engine selection
  • Improved error handling and fallback
  • Wake-word detection  ("hey varna" / "hi varna")
  • Yes/No confirmation listener for the safety layer
"""

import json
from pathlib import Path
import speech_recognition as sr
from utils.logger import get_logger

log = get_logger(__name__)

# Try to import offline STT engine
_OFFLINE_STT_AVAILABLE = False
_stt_engine = None


def _init_stt_engine():
    """Initialize the offline STT engine."""
    global _OFFLINE_STT_AVAILABLE, _stt_engine
    try:
        from stt_engine import get_stt_engine
        _stt_engine = get_stt_engine()
        _OFFLINE_STT_AVAILABLE = _stt_engine.is_available()
        if _OFFLINE_STT_AVAILABLE:
            log.info("Offline STT engine initialized")
        else:
            log.warning("Offline STT engine not available, using Google fallback")
    except ImportError as e:
        log.warning("Offline STT not available: %s", e)
        _OFFLINE_STT_AVAILABLE = False
    except Exception as e:
        log.warning("Failed to initialize offline STT: %s", e)
        _OFFLINE_STT_AVAILABLE = False

# Wake-word phrases that activate VARNA
WAKE_WORDS = {"hey varna", "hi varna", "hello varna", "ok varna", "varna"}


class Listener:
    """Captures microphone audio and returns transcribed text."""

    def __init__(self, energy_threshold: int = 300, pause_threshold: float = 1.0):
        """
        Initialise the recogniser and microphone.

        Args:
            energy_threshold: Mic sensitivity (raise in noisy rooms).
            pause_threshold: Seconds of silence before a phrase is considered complete.
        """
        self.recogniser = sr.Recognizer()
        self.recogniser.energy_threshold = energy_threshold
        self.recogniser.pause_threshold = pause_threshold
        self.recogniser.dynamic_energy_threshold = True   # auto-adjust to ambient noise

        # Verify that a microphone is available
        try:
            self.mic = sr.Microphone()
            log.info("Microphone initialised successfully.")
        except OSError as exc:
            log.error("No microphone found: %s", exc)
            raise RuntimeError(
                "Microphone not found. Please connect a microphone and try again."
            ) from exc

    # ------------------------------------------------------------------ #
    def calibrate(self, duration: float = 1.0) -> None:
        """Adjust for ambient noise (run once at startup)."""
        log.info("Calibrating for ambient noise (%.1f s) …", duration)
        with self.mic as source:
            self.recogniser.adjust_for_ambient_noise(source, duration=duration)
        log.info(
            "Calibration complete. Energy threshold = %d",
            self.recogniser.energy_threshold,
        )

    # ------------------------------------------------------------------ #
    def listen_for_wake_word(self, timeout: int = 3, phrase_time_limit: int = 4) -> bool:
        """
        Listen for a wake-word phrase (e.g. "hey varna").

        Uses a short listening window to stay responsive and low-power.

        Args:
            timeout: Max seconds to wait for speech to start.
            phrase_time_limit: Max seconds for the entire phrase.

        Returns:
            True if a wake-word was detected, False otherwise.
        """
        try:
            with self.mic as source:
                audio = self.recogniser.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )

            text = self._recognize_audio(audio)
            if not text:
                return False
            
            text = text.lower().strip()
            log.debug("Wake-word listener heard: '%s'", text)

            # Check if any wake word is present in what was said
            for wake in WAKE_WORDS:
                if wake in text:
                    log.info("Wake-word detected: '%s' in '%s'", wake, text)
                    return True

            log.debug("Not a wake-word: '%s'", text)
            return False

        except sr.WaitTimeoutError:
            return False
        except sr.UnknownValueError:
            return False
        except sr.RequestError as exc:
            log.error("Speech recognition service error: %s", exc)
            return False
        except Exception as exc:
            log.error("Unexpected wake-word listener error: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    def listen(self, timeout: int = 5, phrase_time_limit: int = 8) -> str | None:
        """
        Listen for a single phrase and return the transcribed text.

        Args:
            timeout: Max seconds to wait for speech to start.
            phrase_time_limit: Max seconds for the entire phrase.

        Returns:
            Lowercase transcribed string, or None on failure.
        """
        log.info("Listening …")
        try:
            with self.mic as source:
                audio = self.recogniser.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )

            log.info("Processing audio …")
            text = self._recognize_audio(audio)
            if text:
                text = text.lower().strip()
                log.info("Recognised: \"%s\"", text)
            return text

        except sr.WaitTimeoutError:
            log.debug("No speech detected within timeout.")
            return None
        except sr.UnknownValueError:
            log.warning("Could not understand audio.")
            return None
        except sr.RequestError as exc:
            log.error("Speech recognition service error: %s", exc)
            return None
        except Exception as exc:
            log.error("Unexpected listener error: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    def _recognize_audio(self, audio) -> str | None:
        """
        Recognize audio using configured STT engine.
        
        Tries offline engine first (Whisper/Vosk), falls back to Google.
        
        Args:
            audio: AudioData from speech_recognition.
        
        Returns:
            Transcribed text or None.
        """
        global _OFFLINE_STT_AVAILABLE, _stt_engine
        
        # Initialize STT engine on first use (lazy loading)
        if _stt_engine is None:
            _init_stt_engine()
        
        # Try offline STT first
        if _OFFLINE_STT_AVAILABLE and _stt_engine is not None:
            try:
                result = _stt_engine.transcribe(audio)
                if result:
                    log.debug("Offline STT recognized: '%s'", result)
                    return result
                log.debug("Offline STT returned empty, trying Google fallback")
            except Exception as e:
                log.warning("Offline STT error: %s, falling back to Google", e)
        
        # Fallback to Google
        try:
            return self.recogniser.recognize_google(audio)
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            log.error("Google API error: %s", e)
            return None

    # ------------------------------------------------------------------ #
    def ask_yes_no(self, timeout: int = 6, phrase_time_limit: int = 5) -> bool | None:
        """
        Listen for a yes/no confirmation response.

        Returns:
            True  → user said yes / confirm / do it / go ahead
            False → user said no / cancel / stop / never mind
            None  → timeout or unrecognised response
        """
        YES_WORDS = {"yes", "yeah", "yep", "confirm", "do it", "go ahead", "sure", "okay", "ok", "affirmative"}
        NO_WORDS = {"no", "nope", "cancel", "stop", "don't", "dont", "never mind", "nevermind", "abort"}

        log.info("Waiting for yes/no confirmation …")
        try:
            with self.mic as source:
                audio = self.recogniser.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )

            text = self._recognize_audio(audio)
            if not text:
                log.warning("Could not understand confirmation audio.")
                return None
            
            text = text.lower().strip()
            log.info("Confirmation response: '%s'", text)

            # Check for yes
            for word in YES_WORDS:
                if word in text:
                    log.info("Confirmed: YES")
                    return True

            # Check for no
            for word in NO_WORDS:
                if word in text:
                    log.info("Confirmed: NO")
                    return False

            log.warning("Unrecognised confirmation response: '%s'", text)
            return None

        except sr.WaitTimeoutError:
            log.info("Confirmation timed out.")
            return None
        except sr.UnknownValueError:
            log.warning("Could not understand confirmation audio.")
            return None
        except sr.RequestError as exc:
            log.error("Speech recognition service error: %s", exc)
            return None
        except Exception as exc:
            log.error("Unexpected error in ask_yes_no: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    def get_stt_status(self) -> dict:
        """
        Get status of STT engine.
        
        Returns:
            Dict with STT engine status info.
        """
        global _OFFLINE_STT_AVAILABLE, _stt_engine
        
        if _stt_engine is None:
            _init_stt_engine()
        
        return {
            "offline_available": _OFFLINE_STT_AVAILABLE,
            "engine_type": type(_stt_engine).__name__ if _stt_engine else "Google",
            "fallback": "Google" if not _OFFLINE_STT_AVAILABLE else None
        }
