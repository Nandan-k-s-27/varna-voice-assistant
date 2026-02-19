"""
VARNA v1 - Text-to-Speech Module
Uses pyttsx3 for completely offline speech synthesis.
"""

import pyttsx3
from utils.logger import get_logger

log = get_logger(__name__)


class Speaker:
    """Handles all text-to-speech output."""

    def __init__(self, rate: int = 170, volume: float = 1.0):
        """
        Initialise the TTS engine.

        Args:
            rate: Words per minute (default 170 — natural pace).
            volume: 0.0 to 1.0 (default 1.0).
        """
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", rate)
            self.engine.setProperty("volume", volume)

            # Try to use a female voice if available (index 1 on Windows)
            voices = self.engine.getProperty("voices")
            if len(voices) > 1:
                self.engine.setProperty("voice", voices[1].id)
                log.info("Voice set to: %s", voices[1].name)
            else:
                log.info("Voice set to: %s", voices[0].name)

            log.info("Speaker initialised (rate=%d, volume=%.1f)", rate, volume)
        except Exception as exc:
            log.error("Failed to initialise TTS engine: %s", exc)
            raise

    # ------------------------------------------------------------------ #
    def say(self, text: str) -> None:
        """Speak the given text aloud and block until finished."""
        if not text:
            return
        log.info("Speaking: %s", text)
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as exc:
            log.error("TTS error: %s", exc)

    # ------------------------------------------------------------------ #
    def greet(self) -> None:
        """Play a startup greeting."""
        self.say("VARNA online. How can I help you?")

    def goodbye(self) -> None:
        """Play a shutdown farewell."""
        self.say("Goodbye. VARNA shutting down.")
