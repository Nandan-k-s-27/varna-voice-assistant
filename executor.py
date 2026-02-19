"""
VARNA v1 - Safe PowerShell Executor
Runs ONLY whitelisted commands via subprocess.
Never accepts raw user text — all input must pass through the Parser first.
"""

import subprocess
from utils.logger import get_logger

log = get_logger(__name__)


class Executor:
    """Executes validated PowerShell commands safely."""

    @staticmethod
    def run(command: str) -> tuple[bool, str]:
        """
        Execute a single PowerShell command.

        Args:
            command: The PowerShell command string (already validated by Parser).

        Returns:
            (success: bool, output_or_error: str)
        """
        if not command:
            log.warning("Empty command — skipping execution.")
            return False, "No command provided."

        log.info("Executing: %s", command)

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=30,          # prevent runaway commands
                creationflags=subprocess.CREATE_NO_WINDOW,  # no popup window
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode == 0:
                log.info("Command succeeded. Output: %s", stdout[:200] if stdout else "(none)")
                return True, stdout if stdout else "Command executed successfully."
            else:
                log.warning("Command returned code %d. Stderr: %s", result.returncode, stderr[:200])
                return False, stderr if stderr else f"Command failed (exit code {result.returncode})."

        except subprocess.TimeoutExpired:
            log.error("Command timed out after 30 s: %s", command)
            return False, "Command timed out."
        except FileNotFoundError:
            log.error("PowerShell not found on this system.")
            return False, "PowerShell is not available on this system."
        except Exception as exc:
            log.error("Unexpected execution error: %s", exc)
            return False, str(exc)
