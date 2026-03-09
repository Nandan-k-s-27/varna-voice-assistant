"""
VARNA v2.3 - Safe PowerShell Executor
Runs ONLY whitelisted commands via subprocess.
Never accepts raw user text — all input must pass through the Parser first.

Supports:
  - Single command execution (v1.0 compatible)
  - Sequential chain execution (v1.1)
  - Robust app-launch fallback (v2.4): tries PATH → common install dirs
"""

import subprocess
import re
from utils.logger import get_logger

log = get_logger(__name__)

# Common install locations searched as fallback when Start-Process fails.
# The placeholder {app} is replaced with the target exe name.
_APP_FALLBACK_PATHS = [
    r"C:\Program Files\{app}\{app}.exe",
    r"C:\Program Files (x86)\{app}\{app}.exe",
    r"C:\Users\{username}\AppData\Local\{app}\{app}.exe",
    r"C:\Users\{username}\AppData\Roaming\{app}\{app}.exe",
]

# Map of well-known exe names → common absolute paths (prioritised lookup)
_KNOWN_PATHS: dict[str, list[str]] = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "msedge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "code": [
        r"C:\Users\{username}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "spotify": [
        r"C:\Users\{username}\AppData\Roaming\Spotify\Spotify.exe",
    ],
    "discord": [
        r"C:\Users\{username}\AppData\Local\Discord\Update.exe",
        r"C:\Users\{username}\AppData\Local\Discord\app-*/Discord.exe",
    ],
    "steam": [
        r"C:\Program Files (x86)\Steam\steam.exe",
        r"C:\Program Files\Steam\steam.exe",
    ],
    "slack": [
        r"C:\Users\{username}\AppData\Local\slack\slack.exe",
    ],
    "zoom": [
        r"C:\Users\{username}\AppData\Roaming\Zoom\bin\Zoom.exe",
    ],
    "teams": [
        r"C:\Users\{username}\AppData\Local\Microsoft\Teams\Update.exe",
        r"C:\Program Files\Microsoft\Teams\current\Teams.exe",
    ],
    "vlc": [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ],
    "winrar": [
        r"C:\Program Files\WinRAR\WinRAR.exe",
        r"C:\Program Files (x86)\WinRAR\WinRAR.exe",
    ],
    "7zip": [
        r"C:\Program Files\7-Zip\7zFM.exe",
        r"C:\Program Files (x86)\7-Zip\7zFM.exe",
    ],
    "obs": [
        r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    ],
}

# Regex to extract the target exe name from a Start-Process command
_START_PROCESS_RE = re.compile(
    r"Start-Process\s+(?:-FilePath\s+)?['\"]?([A-Za-z0-9_\-\.]+)['\"]?",
    re.IGNORECASE,
)


def _build_robust_launch(command: str) -> str:
    """
    Wrap a Start-Process command into a script that:
      1. Tries the bare name (works if the app is on PATH).
      2. Falls back to known absolute paths if that fails.
      3. Returns a meaningful error if nothing works.
    """
    m = _START_PROCESS_RE.search(command)
    if not m:
        return command  # can't improve it, return as-is

    app_name = m.group(1).lower().rstrip(".exe")
    known = _KNOWN_PATHS.get(app_name, [])

    if not known:
        # Just add -ErrorAction Stop so failures are visible
        return command.replace("Start-Process", "Start-Process", 1)  # unchanged

    # Build a PowerShell try-chain
    known_str = ", ".join(f"'{p}'" for p in known)
    ps_script = (
        f"$appName = '{app_name}';\n"
        f"$knownPaths = @({known_str});\n"
        f"$launched = $false;\n"
        f"# Try PATH first\n"
        f"try {{ Start-Process '{app_name}' -ErrorAction Stop; $launched = $true }} catch {{}}\n"
        f"# Try known install paths\n"
        f"if (-not $launched) {{\n"
        f"  foreach ($p in $knownPaths) {{\n"
        f"    $expanded = [System.Environment]::ExpandEnvironmentVariables($p -replace '{{username}}', $env:USERNAME);\n"
        f"    if (Test-Path $expanded) {{ Start-Process $expanded; $launched = $true; break }}\n"
        f"  }}\n"
        f"}}\n"
        f"if (-not $launched) {{ Write-Error \"Could not find '$appName' on this system.\" }}"
    )
    return ps_script


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

        # Upgrade bare Start-Process commands to use fallback path resolution
        if "Start-Process" in command and "\n" not in command:
            command = _build_robust_launch(command)

        log.info("Executing: %s", command[:200])

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
