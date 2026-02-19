"""
VARNA v1 - Speech-to-Text Listener
Uses the `speech_recognition` library for microphone capture
and Google's free Web Speech API for recognition.

Falls back cleanly on errors and ambient-noise conditions.
"""

import speech_recognition as sr
from utils.logger import get_logger

log = get_logger(__name__)


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
            text = self.recogniser.recognize_google(audio)
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
