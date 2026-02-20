"""
VARNA v2.2 - Smart Failure Recovery
Self-healing behavior when commands fail.

Features:
  - Suggest closest matches on failure
  - Auto-rescan apps when app not found
  - Retry matching with relaxed thresholds
  - Learn from failures to improve future matching
"""

import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable
from utils.logger import get_logger

log = get_logger(__name__)


class FailureType(Enum):
    """Types of command failures."""
    APP_NOT_FOUND = auto()
    COMMAND_NOT_RECOGNIZED = auto()
    EXECUTION_ERROR = auto()
    PERMISSION_DENIED = auto()
    TIMEOUT = auto()
    UNKNOWN = auto()


@dataclass
class RecoveryAction:
    """Action to take for recovery."""
    action_type: str
    description: str
    handler: Callable | None = None
    auto_execute: bool = False


@dataclass
class RecoveryResult:
    """Result of recovery attempt."""
    recovered: bool
    action_taken: str
    new_result: str | None = None
    suggestions: list[str] | None = None


class SmartRecovery:
    """
    Self-healing failure recovery system.
    
    When a command fails:
    1. Identify failure type
    2. Suggest alternatives
    3. Attempt auto-recovery
    4. Learn from failure
    """
    
    def __init__(self):
        """Initialize recovery system."""
        self._failure_history: list[dict] = []
        self._recovery_handlers: dict[FailureType, list[Callable]] = {
            ft: [] for ft in FailureType
        }
        self._lock = threading.Lock()
        
        # External dependencies (set by main app)
        self._app_manager = None
        self._fuzzy_matcher = None
        self._speaker = None
        
        log.info("SmartRecovery initialized")
    
    def set_dependencies(
        self,
        app_manager=None,
        fuzzy_matcher=None,
        speaker=None
    ) -> None:
        """Set external dependencies."""
        self._app_manager = app_manager
        self._fuzzy_matcher = fuzzy_matcher
        self._speaker = speaker
    
    def register_handler(
        self, 
        failure_type: FailureType, 
        handler: Callable
    ) -> None:
        """Register a recovery handler for a failure type."""
        self._recovery_handlers[failure_type].append(handler)
    
    def handle_failure(
        self,
        failure_type: FailureType,
        original_input: str,
        error_message: str = "",
        context: dict = None
    ) -> RecoveryResult:
        """
        Handle a command failure.
        
        Args:
            failure_type: Type of failure.
            original_input: What the user said.
            error_message: Error details.
            context: Additional context.
            
        Returns:
            RecoveryResult with recovery actions.
        """
        context = context or {}
        
        # Record failure
        with self._lock:
            self._failure_history.append({
                "type": failure_type.name,
                "input": original_input,
                "error": error_message,
                "timestamp": time.time()
            })
        
        log.info("Handling failure: %s for '%s'", failure_type.name, original_input)
        
        # Dispatch to specific handler
        if failure_type == FailureType.APP_NOT_FOUND:
            return self._recover_app_not_found(original_input, context)
        elif failure_type == FailureType.COMMAND_NOT_RECOGNIZED:
            return self._recover_command_not_recognized(original_input, context)
        elif failure_type == FailureType.EXECUTION_ERROR:
            return self._recover_execution_error(original_input, error_message, context)
        else:
            return self._generic_recovery(failure_type, original_input, error_message)
    
    def _recover_app_not_found(
        self, 
        original_input: str, 
        context: dict
    ) -> RecoveryResult:
        """Recover from app not found error."""
        suggestions = []
        recovered = False
        new_result = None
        
        # Extract app name from input
        app_name = context.get("app_name", "")
        if not app_name:
            # Try to extract from common patterns
            words = original_input.lower().split()
            if "open" in words:
                idx = words.index("open")
                if idx + 1 < len(words):
                    app_name = " ".join(words[idx + 1:])
        
        # 1. Try fuzzy matching with relaxed threshold
        if self._fuzzy_matcher and app_name:
            from nlp.fuzzy_matcher import FuzzyMatcher
            if self._app_manager:
                app_names = list(self._app_manager.get_app_index().keys())
                matches = self._fuzzy_matcher.match_all(
                    app_name, 
                    app_names, 
                    n=3, 
                    threshold=0.4  # Very relaxed
                )
                suggestions = [m[0] for m in matches]
        
        # 2. Auto-rescan apps
        if not suggestions and self._app_manager:
            log.info("Auto-rescanning apps due to app not found")
            try:
                self._app_manager.scan_apps()
                
                # Retry matching after rescan
                if app_name:
                    result = self._app_manager.find_app(app_name)
                    if result:
                        recovered = True
                        new_result = result.get("name", app_name)
            except Exception as e:
                log.error("Auto-rescan failed: %s", e)
        
        # 3. Prepare response
        if recovered:
            return RecoveryResult(
                recovered=True,
                action_taken="rescan_and_retry",
                new_result=new_result
            )
        elif suggestions:
            return RecoveryResult(
                recovered=False,
                action_taken="suggest_alternatives",
                suggestions=suggestions
            )
        else:
            return RecoveryResult(
                recovered=False,
                action_taken="no_recovery_possible",
                suggestions=["Try saying 'scan apps' to refresh the app list"]
            )
    
    def _recover_command_not_recognized(
        self, 
        original_input: str, 
        context: dict
    ) -> RecoveryResult:
        """Recover from command not recognized error."""
        suggestions = []
        
        # Get list of valid commands from context
        valid_commands = context.get("valid_commands", [])
        
        if self._fuzzy_matcher and valid_commands:
            # Find similar commands
            matches = self._fuzzy_matcher.match_all(
                original_input,
                valid_commands,
                n=3,
                threshold=0.3
            )
            suggestions = [m[0] for m in matches]
        
        # Provide helpful suggestions
        if not suggestions:
            suggestions = [
                "Try 'help' to see available commands",
                "Try 'list commands' for full command list",
                "Speak more clearly and try again"
            ]
        
        return RecoveryResult(
            recovered=False,
            action_taken="suggest_similar_commands",
            suggestions=suggestions
        )
    
    def _recover_execution_error(
        self,
        original_input: str,
        error_message: str,
        context: dict
    ) -> RecoveryResult:
        """Recover from execution error."""
        suggestions = []
        
        # Analyze error message
        error_lower = error_message.lower()
        
        if "permission" in error_lower or "access denied" in error_lower:
            suggestions = [
                "This action requires administrator privileges",
                "Try running VARNA as administrator"
            ]
        elif "not found" in error_lower or "does not exist" in error_lower:
            suggestions = [
                "The target file or application may have been moved or deleted",
                "Try 'scan apps' to refresh"
            ]
        elif "timeout" in error_lower:
            suggestions = [
                "The operation timed out",
                "Try again or check if the system is busy"
            ]
        else:
            suggestions = [
                f"Error: {error_message}",
                "Try again or rephrase your command"
            ]
        
        return RecoveryResult(
            recovered=False,
            action_taken="provide_error_guidance",
            suggestions=suggestions
        )
    
    def _generic_recovery(
        self,
        failure_type: FailureType,
        original_input: str,
        error_message: str
    ) -> RecoveryResult:
        """Generic recovery for unhandled failure types."""
        return RecoveryResult(
            recovered=False,
            action_taken="generic_error",
            suggestions=[
                f"Command failed: {error_message}" if error_message else "Command failed",
                "Please try again"
            ]
        )
    
    def get_failure_stats(self) -> dict:
        """Get failure statistics."""
        with self._lock:
            type_counts = {}
            for failure in self._failure_history:
                ft = failure["type"]
                type_counts[ft] = type_counts.get(ft, 0) + 1
            
            return {
                "total_failures": len(self._failure_history),
                "by_type": type_counts,
                "recent_failures": self._failure_history[-5:]
            }
    
    def get_frequent_failures(self, n: int = 5) -> list[str]:
        """Get most frequent failure inputs."""
        with self._lock:
            input_counts = {}
            for failure in self._failure_history:
                inp = failure["input"]
                input_counts[inp] = input_counts.get(inp, 0) + 1
            
            sorted_inputs = sorted(input_counts.items(), key=lambda x: -x[1])
            return [inp for inp, _ in sorted_inputs[:n]]


# Singleton
_recovery: SmartRecovery | None = None


def get_recovery() -> SmartRecovery:
    """Get or create the singleton recovery instance."""
    global _recovery
    if _recovery is None:
        _recovery = SmartRecovery()
    return _recovery
