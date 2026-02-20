"""
VARNA v2.2 - Usage Analytics (Offline)
Track usage patterns for optimization.

Features:
  - Most used commands
  - Time-of-day usage patterns
  - Failure patterns
  - Auto-prioritize frequent commands

All data stored locally - no cloud analytics.
"""

import json
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, asdict
from utils.logger import get_logger

log = get_logger(__name__)

_ANALYTICS_FILE = Path(__file__).parent / "usage_analytics.json"


@dataclass
class CommandUsage:
    """Usage data for a single command."""
    command: str
    count: int = 0
    success_count: int = 0
    fail_count: int = 0
    avg_response_ms: float = 0.0
    last_used: str = ""
    hour_distribution: dict = None  # Hour -> count
    
    def __post_init__(self):
        if self.hour_distribution is None:
            self.hour_distribution = {}


@dataclass
class SessionStats:
    """Statistics for a single session."""
    start_time: str
    end_time: str = ""
    total_commands: int = 0
    successful_commands: int = 0
    failed_commands: int = 0
    total_response_time_ms: float = 0.0


class UsageAnalytics:
    """
    Offline usage analytics system.
    
    Tracks:
      - Command usage frequency
      - Success/failure rates
      - Response times
      - Time-of-day patterns
      - Misrecognition patterns
    
    Benefits:
      - Auto-prioritize frequent commands in matching
      - Identify problem areas
      - Optimize based on real usage
    """
    
    def __init__(self, filepath: Path = _ANALYTICS_FILE):
        """Initialize analytics system."""
        self.filepath = filepath
        self._lock = threading.Lock()
        
        self._data = {
            "version": "2.2",
            "commands": {},       # command -> CommandUsage
            "sessions": [],       # List of SessionStats
            "misrecognitions": {},  # wrong -> {correct: count}
            "daily_usage": {},    # date -> count
            "hourly_totals": defaultdict(int),  # hour -> count
            "created": datetime.now().isoformat(),
            "last_updated": None
        }
        
        self._current_session: SessionStats | None = None
        self._load()
        
        log.info("UsageAnalytics loaded: %d commands tracked", 
                len(self._data["commands"]))
    
    def _load(self) -> None:
        """Load analytics from file."""
        try:
            if self.filepath.exists():
                with open(self.filepath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._data.update(loaded)
                    # Convert back to defaultdict
                    self._data["hourly_totals"] = defaultdict(
                        int, 
                        self._data.get("hourly_totals", {})
                    )
        except Exception as e:
            log.warning("Failed to load analytics: %s", e)
    
    def _save(self) -> None:
        """Save analytics to file."""
        try:
            self._data["last_updated"] = datetime.now().isoformat()
            # Convert defaultdict for JSON
            save_data = dict(self._data)
            save_data["hourly_totals"] = dict(self._data["hourly_totals"])
            
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, default=str)
        except Exception as e:
            log.error("Failed to save analytics: %s", e)
    
    def start_session(self) -> None:
        """Start a new usage session."""
        self._current_session = SessionStats(
            start_time=datetime.now().isoformat()
        )
        log.debug("Analytics session started")
    
    def end_session(self) -> None:
        """End current session and save."""
        if self._current_session:
            self._current_session.end_time = datetime.now().isoformat()
            
            with self._lock:
                self._data["sessions"].append(asdict(self._current_session))
                # Keep only last 100 sessions
                self._data["sessions"] = self._data["sessions"][-100:]
                self._save()
            
            self._current_session = None
            log.debug("Analytics session ended")
    
    def record_command(
        self,
        command: str,
        success: bool,
        response_time_ms: float = 0.0
    ) -> None:
        """
        Record a command execution.
        
        Args:
            command: Normalized command text.
            success: Whether command executed successfully.
            response_time_ms: Response time in milliseconds.
        """
        command = command.lower().strip()
        now = datetime.now()
        hour = str(now.hour)
        date = now.strftime("%Y-%m-%d")
        
        with self._lock:
            # Update command stats
            if command not in self._data["commands"]:
                self._data["commands"][command] = {
                    "count": 0,
                    "success_count": 0,
                    "fail_count": 0,
                    "avg_response_ms": 0.0,
                    "last_used": "",
                    "hour_distribution": {}
                }
            
            cmd_data = self._data["commands"][command]
            cmd_data["count"] += 1
            
            if success:
                cmd_data["success_count"] += 1
            else:
                cmd_data["fail_count"] += 1
            
            # Update average response time
            old_avg = cmd_data["avg_response_ms"]
            old_count = cmd_data["count"] - 1
            if old_count > 0:
                cmd_data["avg_response_ms"] = (
                    (old_avg * old_count + response_time_ms) / cmd_data["count"]
                )
            else:
                cmd_data["avg_response_ms"] = response_time_ms
            
            cmd_data["last_used"] = now.isoformat()
            
            # Hour distribution
            if hour not in cmd_data["hour_distribution"]:
                cmd_data["hour_distribution"][hour] = 0
            cmd_data["hour_distribution"][hour] += 1
            
            # Global hourly totals
            self._data["hourly_totals"][hour] += 1
            
            # Daily usage
            if date not in self._data["daily_usage"]:
                self._data["daily_usage"][date] = 0
            self._data["daily_usage"][date] += 1
            
            # Update session
            if self._current_session:
                self._current_session.total_commands += 1
                if success:
                    self._current_session.successful_commands += 1
                else:
                    self._current_session.failed_commands += 1
                self._current_session.total_response_time_ms += response_time_ms
            
            # Save periodically
            total_cmds = sum(c["count"] for c in self._data["commands"].values())
            if total_cmds % 20 == 0:
                self._save()
    
    def record_misrecognition(self, wrong: str, correct: str) -> None:
        """Record a misrecognition for pattern analysis."""
        if wrong == correct:
            return
        
        wrong = wrong.lower().strip()
        correct = correct.lower().strip()
        
        with self._lock:
            if wrong not in self._data["misrecognitions"]:
                self._data["misrecognitions"][wrong] = {}
            
            if correct not in self._data["misrecognitions"][wrong]:
                self._data["misrecognitions"][wrong][correct] = 0
            
            self._data["misrecognitions"][wrong][correct] += 1
    
    def get_top_commands(self, n: int = 10) -> list[tuple[str, int]]:
        """Get most frequently used commands."""
        sorted_cmds = sorted(
            self._data["commands"].items(),
            key=lambda x: -x[1]["count"]
        )
        return [(cmd, data["count"]) for cmd, data in sorted_cmds[:n]]
    
    def get_command_priority_boost(self, command: str) -> float:
        """
        Get a priority boost for a command based on usage.
        
        Returns 0.0-0.2 boost for frequent commands.
        """
        command = command.lower().strip()
        
        if command not in self._data["commands"]:
            return 0.0
        
        count = self._data["commands"][command]["count"]
        max_count = max(
            (c["count"] for c in self._data["commands"].values()),
            default=1
        )
        
        # Scale to 0.0-0.2 boost
        if max_count > 0:
            return min(0.2, (count / max_count) * 0.2)
        return 0.0
    
    def get_failure_prone_commands(self, n: int = 5) -> list[tuple[str, float]]:
        """Get commands with highest failure rates."""
        failure_rates = []
        
        for cmd, data in self._data["commands"].items():
            if data["count"] >= 3:  # Minimum sample size
                fail_rate = data["fail_count"] / data["count"]
                failure_rates.append((cmd, fail_rate))
        
        failure_rates.sort(key=lambda x: -x[1])
        return failure_rates[:n]
    
    def get_peak_hours(self, n: int = 3) -> list[tuple[int, int]]:
        """Get peak usage hours."""
        hourly = dict(self._data["hourly_totals"])
        sorted_hours = sorted(hourly.items(), key=lambda x: -x[1])
        return [(int(h), c) for h, c in sorted_hours[:n]]
    
    def get_misrecognition_patterns(self) -> dict[str, list[tuple[str, int]]]:
        """Get common misrecognition patterns."""
        patterns = {}
        
        for wrong, corrections in self._data["misrecognitions"].items():
            sorted_corrections = sorted(corrections.items(), key=lambda x: -x[1])
            patterns[wrong] = sorted_corrections
        
        return patterns
    
    def get_summary(self) -> dict:
        """Get analytics summary."""
        total_commands = sum(c["count"] for c in self._data["commands"].values())
        total_success = sum(c["success_count"] for c in self._data["commands"].values())
        total_fail = sum(c["fail_count"] for c in self._data["commands"].values())
        
        avg_response = 0.0
        if self._data["commands"]:
            total_weighted_time = sum(
                c["avg_response_ms"] * c["count"] 
                for c in self._data["commands"].values()
            )
            if total_commands > 0:
                avg_response = total_weighted_time / total_commands
        
        return {
            "total_commands": total_commands,
            "unique_commands": len(self._data["commands"]),
            "success_rate": (total_success / total_commands * 100) if total_commands else 0,
            "failure_rate": (total_fail / total_commands * 100) if total_commands else 0,
            "avg_response_ms": round(avg_response, 2),
            "total_sessions": len(self._data["sessions"]),
            "peak_hours": self.get_peak_hours(3),
            "top_commands": self.get_top_commands(5),
            "last_updated": self._data.get("last_updated")
        }
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics for dashboard."""
        cmds = self._data["commands"]
        
        if not cmds:
            return {
                "avg_stt_time": 0,
                "avg_nlp_time": 0,
                "avg_exec_time": 0,
                "avg_total_time": 0,
                "most_used": [],
                "most_misrecognized": []
            }
        
        # Calculate averages
        total_time = sum(c["avg_response_ms"] * c["count"] for c in cmds.values())
        total_count = sum(c["count"] for c in cmds.values())
        
        # Top commands
        top_cmds = self.get_top_commands(5)
        
        # Most misrecognized
        misrec = []
        for wrong, corrections in self._data["misrecognitions"].items():
            total = sum(corrections.values())
            misrec.append((wrong, total))
        misrec.sort(key=lambda x: -x[1])
        
        return {
            "avg_total_time_ms": round(total_time / total_count, 2) if total_count else 0,
            "total_commands": total_count,
            "most_used": top_cmds,
            "most_misrecognized": misrec[:5]
        }


# Singleton
_analytics: UsageAnalytics | None = None


def get_analytics() -> UsageAnalytics:
    """Get or create the singleton analytics instance."""
    global _analytics
    if _analytics is None:
        _analytics = UsageAnalytics()
    return _analytics
