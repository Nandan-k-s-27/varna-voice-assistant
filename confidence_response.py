"""
VARNA v2.2 - Confidence-Based Response Handler
Tiered execution based on match confidence.

Response Tiers:
  > 0.9: Execute immediately (silent or brief)
  0.7-0.9: Execute with confirmation speech
  0.5-0.7: Confirm before executing
  < 0.5: Suggest alternatives

This reduces mistakes without annoying confirmations.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable
from utils.logger import get_logger

log = get_logger(__name__)


class ResponseTier(Enum):
    """Response tier based on confidence."""
    IMMEDIATE = auto()      # > 0.9: Execute silently
    CONFIRMED = auto()      # 0.7-0.9: Execute with speech
    ASK_USER = auto()       # 0.5-0.7: Confirm before executing
    SUGGEST = auto()        # < 0.5: Suggest alternatives


@dataclass
class ResponseAction:
    """Action to take based on confidence."""
    tier: ResponseTier
    should_execute: bool
    should_speak: bool
    speech_template: str
    needs_confirmation: bool = False


class ConfidenceResponseHandler:
    """
    Handles response behavior based on match confidence.
    
    Provides appropriate feedback:
    - High confidence: Quick, silent execution
    - Medium confidence: Execute with verbal confirmation
    - Low confidence: Ask before executing
    - Very low: Suggest alternatives
    """
    
    # Configurable thresholds
    THRESHOLD_IMMEDIATE = 0.90
    THRESHOLD_CONFIRMED = 0.70
    THRESHOLD_ASK = 0.50
    
    def __init__(
        self,
        threshold_immediate: float = 0.90,
        threshold_confirmed: float = 0.70,
        threshold_ask: float = 0.50
    ):
        """
        Initialize handler.
        
        Args:
            threshold_immediate: Confidence for silent execution.
            threshold_confirmed: Confidence for confirmed execution.
            threshold_ask: Confidence for asking user.
        """
        self.threshold_immediate = threshold_immediate
        self.threshold_confirmed = threshold_confirmed
        self.threshold_ask = threshold_ask
        
        # Callbacks
        self._speaker: Callable | None = None
        self._confirm_handler: Callable | None = None
        
        log.info("ConfidenceResponseHandler initialized (thresholds: %.2f/%.2f/%.2f)",
                threshold_immediate, threshold_confirmed, threshold_ask)
    
    def set_speaker(self, speaker: Callable) -> None:
        """Set TTS speaker callback."""
        self._speaker = speaker
    
    def set_confirm_handler(self, handler: Callable) -> None:
        """Set confirmation handler callback."""
        self._confirm_handler = handler
    
    def get_response_action(
        self,
        confidence: float,
        command: str,
        matched_text: str = None
    ) -> ResponseAction:
        """
        Determine response action based on confidence.
        
        Args:
            confidence: Match confidence (0.0-1.0).
            command: The command to execute.
            matched_text: What was matched (for speech).
            
        Returns:
            ResponseAction with execution instructions.
        """
        matched = matched_text or command
        
        if confidence >= self.threshold_immediate:
            return ResponseAction(
                tier=ResponseTier.IMMEDIATE,
                should_execute=True,
                should_speak=False,  # Silent
                speech_template="",
                needs_confirmation=False
            )
        
        elif confidence >= self.threshold_confirmed:
            return ResponseAction(
                tier=ResponseTier.CONFIRMED,
                should_execute=True,
                should_speak=True,
                speech_template=self._get_confirmation_speech(matched),
                needs_confirmation=False
            )
        
        elif confidence >= self.threshold_ask:
            return ResponseAction(
                tier=ResponseTier.ASK_USER,
                should_execute=False,  # Wait for confirmation
                should_speak=True,
                speech_template=f"Did you mean '{matched}'?",
                needs_confirmation=True
            )
        
        else:
            return ResponseAction(
                tier=ResponseTier.SUGGEST,
                should_execute=False,
                should_speak=True,
                speech_template=f"I'm not sure what you meant. Did you say '{matched}'?",
                needs_confirmation=True
            )
    
    def execute_with_response(
        self,
        confidence: float,
        command: str,
        executor: Callable,
        matched_text: str = None,
        suggestions: list[str] = None
    ) -> tuple[bool, str]:
        """
        Execute command with appropriate response.
        
        Args:
            confidence: Match confidence.
            command: Command to execute.
            executor: Function to execute the command.
            matched_text: What was matched.
            suggestions: Alternative suggestions if low confidence.
            
        Returns:
            Tuple of (executed, response_message).
        """
        action = self.get_response_action(confidence, command, matched_text)
        matched = matched_text or command
        
        if action.tier == ResponseTier.IMMEDIATE:
            # Execute immediately and silently
            try:
                executor()
                log.info("Immediate execution: '%s' (conf=%.2f)", command, confidence)
                return True, ""
            except Exception as e:
                return False, f"Error: {str(e)}"
        
        elif action.tier == ResponseTier.CONFIRMED:
            # Execute with verbal confirmation
            if self._speaker:
                self._speaker(action.speech_template)
            
            try:
                executor()
                log.info("Confirmed execution: '%s' (conf=%.2f)", command, confidence)
                return True, action.speech_template
            except Exception as e:
                return False, f"Error: {str(e)}"
        
        elif action.tier == ResponseTier.ASK_USER:
            # Ask for confirmation
            if self._speaker:
                self._speaker(action.speech_template)
            
            confirmed = False
            if self._confirm_handler:
                confirmed = self._confirm_handler()
            
            if confirmed:
                try:
                    executor()
                    log.info("User-confirmed execution: '%s' (conf=%.2f)", command, confidence)
                    return True, "Done."
                except Exception as e:
                    return False, f"Error: {str(e)}"
            else:
                return False, "Cancelled."
        
        else:  # SUGGEST
            # Suggest alternatives
            if suggestions:
                suggest_text = ", ".join(suggestions[:3])
                response = f"I couldn't understand. Did you mean: {suggest_text}?"
            else:
                response = action.speech_template
            
            if self._speaker:
                self._speaker(response)
            
            return False, response
    
    def _get_confirmation_speech(self, command: str) -> str:
        """Generate confirmation speech for a command."""
        # Extract key parts for natural speech
        words = command.lower().split()
        
        if words[0] in ('open', 'launch', 'start'):
            target = ' '.join(words[1:])
            return f"Opening {target}."
        
        elif words[0] in ('close', 'exit', 'quit'):
            target = ' '.join(words[1:])
            return f"Closing {target}."
        
        elif words[0] == 'search':
            query = ' '.join(words[1:])
            return f"Searching for {query}."
        
        elif words[0] == 'type':
            return "Typing."
        
        elif words[0] in ('switch', 'go'):
            return f"Switching."
        
        elif words[0] in ('minimize', 'maximize', 'restore'):
            return f"{words[0].capitalize()}ing."
        
        else:
            return f"Executing {command}."
    
    def adjust_thresholds(
        self,
        immediate: float = None,
        confirmed: float = None,
        ask: float = None
    ) -> None:
        """Adjust confidence thresholds dynamically."""
        if immediate is not None:
            self.threshold_immediate = max(0.5, min(1.0, immediate))
        if confirmed is not None:
            self.threshold_confirmed = max(0.3, min(0.9, confirmed))
        if ask is not None:
            self.threshold_ask = max(0.2, min(0.7, ask))
        
        log.info("Thresholds adjusted: %.2f/%.2f/%.2f",
                self.threshold_immediate, self.threshold_confirmed, self.threshold_ask)


# Singleton
_handler: ConfidenceResponseHandler | None = None


def get_response_handler() -> ConfidenceResponseHandler:
    """Get or create the singleton handler."""
    global _handler
    if _handler is None:
        _handler = ConfidenceResponseHandler()
    return _handler
