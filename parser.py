"""
VARNA v1 - Command Parser
Loads the whitelist (commands.json) and maps spoken text → PowerShell command.

Matching strategy (in order):
  1. Exact match   – spoken text matches a key exactly.
  2. Keyword match  – spoken text *contains* a key as a substring.
"""

import json
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

# Path to the command whitelist
_COMMANDS_FILE = Path(__file__).resolve().parent / "commands.json"


class Parser:
    """Maps natural-language text to safe, whitelisted PowerShell commands."""

    def __init__(self, commands_path: Path = _COMMANDS_FILE):
        """
        Load the command whitelist from disk.

        Args:
            commands_path: Path to the JSON whitelist file.
        """
        try:
            with open(commands_path, "r", encoding="utf-8") as fh:
                self.commands: dict[str, str] = json.load(fh)
            log.info(
                "Loaded %d whitelisted commands from %s",
                len(self.commands),
                commands_path.name,
            )
        except FileNotFoundError:
            log.error("Command file not found: %s", commands_path)
            self.commands = {}
        except json.JSONDecodeError as exc:
            log.error("Invalid JSON in %s: %s", commands_path, exc)
            self.commands = {}

    # ------------------------------------------------------------------ #
    def parse(self, text: str) -> tuple[str | None, str | None]:
        """
        Match *text* against the whitelist.

        Returns:
            (matched_key, powershell_command) on success.
            (None, None) if no match is found.
        """
        if not text:
            return None, None

        text = text.lower().strip()

        # 1. Exact match
        if text in self.commands:
            log.info("Exact match: '%s'", text)
            return text, self.commands[text]

        # 2. Keyword / substring match (longest key first for accuracy)
        for key in sorted(self.commands, key=len, reverse=True):
            if key in text:
                log.info("Keyword match: '%s' found in '%s'", key, text)
                return key, self.commands[key]

        log.info("No match for: '%s'", text)
        return None, None

    # ------------------------------------------------------------------ #
    def list_commands(self) -> list[str]:
        """Return all available spoken command phrases."""
        return list(self.commands.keys())
