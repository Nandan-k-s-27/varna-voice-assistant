"""
VARNA v1.2 - Process Monitor
Monitors a named process in a background thread and alerts
via TTS when memory usage exceeds a configurable threshold.
"""

import threading
import subprocess
import time
from utils.logger import get_logger

log = get_logger(__name__)


class ProcessMonitor:
    """
    Polls a Windows process at regular intervals and fires a
    voice alert when memory exceeds the threshold.
    """

    def __init__(self, speaker, poll_interval: int = 5):
        """
        Args:
            speaker: Speaker instance used for TTS alerts.
            poll_interval: Seconds between each check (default 5).
        """
        self.speaker = speaker
        self.poll_interval = poll_interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._process_name: str | None = None
        self._threshold_mb: float = 500.0
        self._alerted = False  # avoid repeating the same alert

    # ------------------------------------------------------------------ #
    @property
    def is_running(self) -> bool:
        """Return True if a monitor thread is currently active."""
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ #
    def start(self, process_name: str, threshold_mb: float = 500.0) -> str:
        """
        Start monitoring a process in the background.

        Args:
            process_name: Name of the process (e.g. "chrome").
            threshold_mb: Memory threshold in MB before alerting.

        Returns:
            A confirmation message.
        """
        if self.is_running:
            self.stop()

        self._process_name = process_name
        self._threshold_mb = threshold_mb
        self._stop_event.clear()
        self._alerted = False

        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name=f"monitor-{process_name}",
        )
        self._thread.start()

        msg = (
            f"Monitoring {process_name} started. "
            f"I will alert if memory exceeds {int(threshold_mb)} MB."
        )
        log.info(msg)
        return msg

    # ------------------------------------------------------------------ #
    def stop(self) -> str:
        """Stop the background monitoring thread."""
        if not self.is_running:
            return "No active monitor to stop."

        name = self._process_name or "process"
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.poll_interval + 2)
        self._thread = None

        msg = f"Stopped monitoring {name}."
        log.info(msg)
        return msg

    # ------------------------------------------------------------------ #
    def _poll_loop(self) -> None:
        """Background loop that checks process memory every N seconds."""
        process = self._process_name
        log.info("Monitor thread started for '%s' (threshold=%.0f MB).", process, self._threshold_mb)

        while not self._stop_event.is_set():
            try:
                memory_mb = self._get_memory_usage(process)

                if memory_mb is None:
                    log.warning("Process '%s' not found. Retrying …", process)
                elif memory_mb > self._threshold_mb and not self._alerted:
                    alert = (
                        f"Warning! {process} is using {memory_mb:.0f} megabytes "
                        f"of memory, exceeding the {int(self._threshold_mb)} megabyte threshold."
                    )
                    log.warning(alert)
                    self.speaker.say(alert)
                    self._alerted = True
                elif memory_mb <= self._threshold_mb:
                    # Reset alert so it can fire again if usage climbs back
                    self._alerted = False
                    log.debug(
                        "Monitor: %s — %.1f MB (under threshold).", process, memory_mb
                    )

            except Exception as exc:
                log.error("Monitor error: %s", exc)

            self._stop_event.wait(self.poll_interval)

        log.info("Monitor thread for '%s' exiting.", process)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _get_memory_usage(process_name: str) -> float | None:
        """
        Get total WorkingSet memory (MB) for all instances of a process.

        Returns:
            Memory in MB, or None if the process is not running.
        """
        ps_cmd = (
            f"(Get-Process -Name '{process_name}' -ErrorAction SilentlyContinue "
            f"| Measure-Object WorkingSet -Sum).Sum"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = result.stdout.strip()
            if output and output != "":
                total_bytes = float(output)
                return total_bytes / (1024 * 1024)
            return None

        except (subprocess.TimeoutExpired, ValueError, Exception) as exc:
            log.error("Failed to query process '%s': %s", process_name, exc)
            return None

    # ------------------------------------------------------------------ #
    def get_status(self, process_name: str | None = None) -> str:
        """
        Get a one-shot memory and CPU report for a process.
        Used for non-monitoring queries.
        """
        name = process_name or self._process_name
        if not name:
            return "No process specified."

        ps_cmd = (
            f"Get-Process -Name '{name}' -ErrorAction SilentlyContinue | "
            f"Select-Object Name, "
            f"@{{N='CPU_Seconds';E={{[math]::Round($_.CPU,2)}}}}, "
            f"@{{N='Memory_MB';E={{[math]::Round($_.WorkingSet/1MB,2)}}}} | "
            f"Format-Table -AutoSize | Out-String"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = result.stdout.strip()
            return output if output else f"Process '{name}' is not running."
        except Exception as exc:
            return f"Error querying process: {exc}"
