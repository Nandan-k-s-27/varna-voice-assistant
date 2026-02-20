"""
VARNA v2.0 - Text-to-Speech Module
Uses pyttsx3 for completely offline speech synthesis.
Supports async (non-blocking) speech with queue management.

v2.0 improvements:
  • Proper speech queue with background thread
  • Non-blocking say_async() returns immediately
  • Queue management (clear, pause, resume)
  • Configurable voice selection
"""

import threading
import queue
import json
from pathlib import Path
import pyttsx3
import pythoncom
from utils.logger import get_logger

log = get_logger(__name__)


def _load_config() -> dict:
    """Load TTS configuration from config.json."""
    config_path = Path(__file__).parent / "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f).get("tts", {})
    except FileNotFoundError:
        return {}


class Speaker:
    """Handles all text-to-speech output with queue management."""

    def __init__(self, rate: int = None, volume: float = None, voice_index: int = None):
        """
        Initialise the TTS engine.

        Args:
            rate: Words per minute (default from config or 190).
            volume: 0.0 to 1.0 (default from config or 1.0).
            voice_index: Voice index to use (default from config or 1).
        """
        config = _load_config()
        
        self.rate = rate or config.get("rate", 190)
        self.volume = volume or config.get("volume", 1.0)
        self.voice_index = voice_index or config.get("voice_index", 1)
        
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", self.rate)
            self.engine.setProperty("volume", self.volume)

            # Try to use configured voice
            voices = self.engine.getProperty("voices")
            if len(voices) > self.voice_index:
                self.engine.setProperty("voice", voices[self.voice_index].id)
                log.info("Voice set to: %s", voices[self.voice_index].name)
            else:
                log.info("Voice set to: %s", voices[0].name)

            log.info("Speaker initialised (rate=%d, volume=%.1f)", self.rate, self.volume)
        except Exception as exc:
            log.error("Failed to initialise TTS engine: %s", exc)
            raise

        self._lock = threading.Lock()
        
        # Speech queue for async operations
        self._speech_queue = queue.Queue()
        self._queue_thread = None
        self._running = False
        self._paused = False
        
        # Start the background queue processor
        self._start_queue_processor()

    # ------------------------------------------------------------------ #
    def _start_queue_processor(self) -> None:
        """Start the background thread that processes the speech queue."""
        if self._queue_thread is not None and self._queue_thread.is_alive():
            return
        
        self._running = True
        self._queue_thread = threading.Thread(
            target=self._process_queue, 
            daemon=True, 
            name="TTS-Queue"
        )
        self._queue_thread.start()
        log.debug("TTS queue processor started")

    # ------------------------------------------------------------------ #
    def _process_queue(self) -> None:
        """Background thread that processes speech queue."""
        pythoncom.CoInitialize()
        try:
            while self._running:
                try:
                    # Wait for speech item with timeout
                    text = self._speech_queue.get(timeout=0.5)
                    
                    # Skip if paused
                    if self._paused:
                        continue
                    
                    # Speak the text
                    if text:
                        self._speak_internal(text)
                    
                    self._speech_queue.task_done()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    log.error("Queue processor error: %s", e)
        finally:
            pythoncom.CoUninitialize()

    # ------------------------------------------------------------------ #
    def _speak_internal(self, text: str) -> None:
        """Internal method to speak text (called from queue thread)."""
        try:
            with self._lock:
                self.engine.say(text)
                self.engine.runAndWait()
        except Exception as exc:
            log.error("TTS error: %s", exc)

    # ------------------------------------------------------------------ #
    def say(self, text: str) -> None:
        """Speak the given text aloud and block until finished."""
        if not text:
            return
        log.info("Speaking: %s", text)
        try:
            with self._lock:
                self.engine.say(text)
                self.engine.runAndWait()
        except Exception as exc:
            log.error("TTS error: %s", exc)

    # ------------------------------------------------------------------ #
    def say_async(self, text: str) -> None:
        """
        Add text to speech queue — returns immediately without blocking.
        
        Text will be spoken in order by the background queue processor.
        
        Args:
            text: Text to speak.
        """
        if not text:
            return
        
        log.debug("Queuing speech: %s", text)
        self._speech_queue.put(text)

    # ------------------------------------------------------------------ #
    def clear_queue(self) -> int:
        """
        Clear all pending speech from the queue.
        
        Returns:
            Number of items cleared.
        """
        count = 0
        try:
            while True:
                self._speech_queue.get_nowait()
                count += 1
        except queue.Empty:
            pass
        
        if count > 0:
            log.info("Cleared %d items from speech queue", count)
        return count

    # ------------------------------------------------------------------ #
    def pause(self) -> None:
        """Pause speech queue processing."""
        self._paused = True
        log.info("Speech queue paused")

    # ------------------------------------------------------------------ #
    def resume(self) -> None:
        """Resume speech queue processing."""
        self._paused = False
        log.info("Speech queue resumed")

    # ------------------------------------------------------------------ #
    def is_speaking(self) -> bool:
        """Check if there are items in the speech queue."""
        return not self._speech_queue.empty()

    # ------------------------------------------------------------------ #
    def queue_size(self) -> int:
        """Get the number of items waiting in the speech queue."""
        return self._speech_queue.qsize()

    # ------------------------------------------------------------------ #
    def greet(self) -> None:
        """Play a startup greeting."""
        self.say("VARNA online. How can I help you?")

    # ------------------------------------------------------------------ #
    def goodbye(self) -> None:
        """Play a shutdown farewell."""
        self.say("Goodbye. VARNA shutting down.")

    # ------------------------------------------------------------------ #
    def shutdown(self) -> None:
        """Gracefully shutdown the speaker and queue processor."""
        self._running = False
        self.clear_queue()
        if self._queue_thread and self._queue_thread.is_alive():
            self._queue_thread.join(timeout=2.0)
        log.info("Speaker shutdown complete")

