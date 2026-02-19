"""
VARNA v1.1 - Safe PowerShell Executor
Runs ONLY whitelisted commands via subprocess.
Never accepts raw user text — all input must pass through the Parser first.

Supports:
  - Single command execution (v1.0 compatible)
  - Sequential chain execution (v1.1)
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

    # ------------------------------------------------------------------ #
    @staticmethod
    def run_chain(commands: list[str]) -> tuple[bool, str]:
        """
        Execute a sequence of PowerShell commands one by one.

        Stops on the first failure and reports which step failed.
        Collects output from all successful steps.

        Args:
            commands: List of PowerShell command strings (already validated).

        Returns:
            (all_succeeded: bool, combined_output_or_error: str)
        """
        if not commands:
            log.warning("Empty chain — skipping execution.")
            return False, "No commands provided."

        log.info("Executing chain of %d steps.", len(commands))
        all_output: list[str] = []

        for i, cmd in enumerate(commands, start=1):
            log.info("  Chain step %d/%d: %s", i, len(commands), cmd)

            success, output = Executor.run(cmd)

            if success:
                if output and output != "Command executed successfully.":
                    all_output.append(f"[Step {i}] {output}")
                log.info("  Step %d succeeded.", i)
            else:
                error_msg = f"Chain failed at step {i}/{len(commands)}: {output}"
                log.warning(error_msg)
                return False, error_msg

        combined = "\n".join(all_output) if all_output else "All steps completed successfully."
        log.info("Chain completed successfully (%d steps).", len(commands))
        return True, combined
