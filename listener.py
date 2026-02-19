"""
VARNA v1.2 - Speech-to-Text Listener
Uses the `speech_recognition` library for microphone capture
and Google's free Web Speech API for recognition.

v1.2 additions:
  • Wake-word detection  ("hey varna" / "hi varna")
  • Yes/No confirmation   listener for the safety layer
"""

import speech_recognition as sr
from utils.logger import get_logger

log = get_logger(__name__)

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

            text = self.recogniser.recognize_google(audio).lower().strip()
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

            text = self.recogniser.recognize_google(audio).lower().strip()
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
