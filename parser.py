"""
VARNA v1.1 - Command Parser
Loads the structured whitelist (commands.json) and maps spoken text
to PowerShell commands.

Supports four command types:
  1. Static      – exact key → single PS command.
  2. Parameterized – extract parameters from speech, inject into template.
  3. Chains      – multi-step sequential command pipeline.
  4. Developer   – developer-productivity shortcuts.

Matching strategy (in order):
  1. Exact match  – spoken text matches a key exactly (static → developer).
  2. Parameterized – spoken text starts with a trigger keyword.
  3. Chain match  – spoken text matches a chain key.
  4. Keyword match – spoken text *contains* a key as a substring.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus
from utils.logger import get_logger

log = get_logger(__name__)

# Path to the command whitelist
_COMMANDS_FILE = Path(__file__).resolve().parent / "commands.json"


# ====================================================================== #
@dataclass
class ParseResult:
    """Result of parsing a spoken command."""
    matched_key: str | None = None
    commands: list[str] = field(default_factory=list)
    is_chain: bool = False

    @property
    def matched(self) -> bool:
        return self.matched_key is not None


# ====================================================================== #
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
                data = json.load(fh)

            # v1.1 structured schema
            self.static: dict[str, str] = data.get("static", {})
            self.parameterized: dict[str, dict] = data.get("parameterized", {})
            self.chains: dict[str, dict] = data.get("chains", {})
            self.developer: dict[str, str] = data.get("developer", {})

            # Backward compatibility: if the file is a flat dict (v1.0),
            # treat everything as static commands.
            if not any(k in data for k in ("static", "parameterized", "chains", "developer")):
                self.static = data
                log.info("Loaded v1.0-style flat command file — treating all as static.")

            total = (
                len(self.static)
                + len(self.parameterized)
                + len(self.chains)
                + len(self.developer)
            )
            log.info(
                "Loaded %d commands from %s  (static=%d, param=%d, chains=%d, dev=%d)",
                total,
                commands_path.name,
                len(self.static),
                len(self.parameterized),
                len(self.chains),
                len(self.developer),
            )

        except FileNotFoundError:
            log.error("Command file not found: %s", commands_path)
            self.static = {}
            self.parameterized = {}
            self.chains = {}
            self.developer = {}
        except json.JSONDecodeError as exc:
            log.error("Invalid JSON in %s: %s", commands_path, exc)
            self.static = {}
            self.parameterized = {}
            self.chains = {}
            self.developer = {}

    # ------------------------------------------------------------------ #
    def parse(self, text: str) -> ParseResult:
        """
        Match *text* against the whitelist.

        Resolution order:
          1. Exact match in static
          2. Exact match in developer
          3. Parameterized match (keyword + extracted parameter)
          4. Chain match
          5. Keyword/substring fallback across static + developer

        Returns:
            ParseResult with matched_key, commands list, and is_chain flag.
        """
        if not text:
            return ParseResult()

        text = text.lower().strip()

        # 1. Exact match — static
        if text in self.static:
            log.info("Static exact match: '%s'", text)
            return ParseResult(matched_key=text, commands=[self.static[text]])

        # 2. Exact match — developer
        if text in self.developer:
            log.info("Developer exact match: '%s'", text)
            return ParseResult(matched_key=text, commands=[self.developer[text]])

        # 3. Parameterized match
        result = self._match_parameterized(text)
        if result.matched:
            return result

        # 4. Chain match
        result = self._match_chain(text)
        if result.matched:
            return result

        # 5. Keyword / substring fallback (longest key first for accuracy)
        all_flat = {**self.static, **self.developer}
        for key in sorted(all_flat, key=len, reverse=True):
            if key in text:
                log.info("Keyword match: '%s' found in '%s'", key, text)
                return ParseResult(matched_key=key, commands=[all_flat[key]])

        log.info("No match for: '%s'", text)
        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_parameterized(self, text: str) -> ParseResult:
        """
        Check if text starts with a parameterized trigger keyword
        and extract the dynamic portion.

        Example:
          text = "search react hooks tutorial"
          trigger = "search", extract_after = "search"
          query = "react hooks tutorial"
          template = "Start-Process chrome 'https://www.google.com/search?q={query}'"
          result command = "Start-Process chrome 'https://www.google.com/search?q=react+hooks+tutorial'"
        """
        # Sort by key length descending so "search youtube" matches before "search"
        for key in sorted(self.parameterized, key=len, reverse=True):
            entry = self.parameterized[key]
            extract_after = entry.get("extract_after", key).lower()

            if text.startswith(extract_after):
                # Extract everything after the trigger keyword
                raw_query = text[len(extract_after):].strip()

                # Remove common filler words at the start
                raw_query = re.sub(r"^(for|about|on|the)\s+", "", raw_query, count=1)

                if not raw_query:
                    log.info("Parameterized match '%s' but no query extracted.", key)
                    return ParseResult()

                # URL-encode the query for web searches
                encoded_query = quote_plus(raw_query)
                command = entry["template"].replace("{query}", encoded_query)

                log.info(
                    "Parameterized match: key='%s', query='%s', encoded='%s'",
                    key, raw_query, encoded_query,
                )
                return ParseResult(matched_key=f"{key} {raw_query}", commands=[command])

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_chain(self, text: str) -> ParseResult:
        """
        Check if text matches a multi-step command chain.
        Returns all steps as a list.
        """
        # Exact match first
        if text in self.chains:
            entry = self.chains[text]
            steps = entry.get("steps", [])
            log.info("Chain exact match: '%s' (%d steps)", text, len(steps))
            return ParseResult(matched_key=text, commands=steps, is_chain=True)

        # Keyword / substring fallback for chains
        for key in sorted(self.chains, key=len, reverse=True):
            if key in text:
                entry = self.chains[key]
                steps = entry.get("steps", [])
                log.info("Chain keyword match: '%s' in '%s' (%d steps)", key, text, len(steps))
                return ParseResult(matched_key=key, commands=steps, is_chain=True)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def list_commands(self) -> list[str]:
        """Return all available spoken command phrases."""
        all_keys = []
        all_keys.extend(self.static.keys())
        all_keys.extend(self.developer.keys())
        all_keys.extend(f"{k} <...>" for k in self.parameterized.keys())
        all_keys.extend(self.chains.keys())
        return all_keys

    # ------------------------------------------------------------------ #
    def list_developer_commands(self) -> list[str]:
        """Return only developer-mode command phrases."""
        return list(self.developer.keys())
