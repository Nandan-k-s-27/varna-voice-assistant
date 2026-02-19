"""
VARNA v1.2 - Command Parser
Loads the structured whitelist (commands.json) and maps spoken text
to PowerShell commands.

Supports command types:
  1. Static        – exact key → single PS command.
  2. Parameterized – extract parameters from speech, inject into template.
  3. Chains        – multi-step sequential command pipeline.
  4. Developer     – developer-productivity shortcuts.
  5. System        – system-level commands (shutdown, restart, etc.)
  6. Scheduler     – time-based scheduled tasks (v1.2)
  7. Monitoring    – process monitoring commands (v1.2)
  8. Context       – pronoun-based context-aware commands (v1.2)

Matching strategy (in order):
  1. Context match – pronoun resolution  ("close it" → last app).
  2. Exact match   – spoken text matches a key exactly (static → developer → system).
  3. Scheduler     – "schedule shutdown at 10 PM"
  4. Monitoring    – "monitor chrome memory usage"
  5. Parameterized – spoken text starts with a trigger keyword.
  6. Chain match   – spoken text matches a chain key.
  7. Keyword match – spoken text *contains* a key as a substring.
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
    needs_confirmation: bool = False    # v1.2 — dangerous command flag
    is_scheduler: bool = False          # v1.2 — scheduler command flag
    is_monitor: bool = False            # v1.2 — monitoring command flag
    monitor_action: str | None = None   # "start" | "stop" | "check"
    monitor_process: str | None = None  # e.g. "chrome"
    is_context: bool = False            # v1.2 — context-aware command flag
    is_info: bool = False               # v1.2 — info query (session status, etc.)
    info_text: str | None = None        # text for info responses

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

            # v1.2 additions
            self.dangerous: list[str] = data.get("dangerous", [])
            self.system: dict[str, str] = data.get("system", {})
            self.scheduler: dict[str, dict] = data.get("scheduler", {})
            self.monitoring: dict[str, dict] = data.get("monitoring", {})
            self.context_cmds: dict[str, str] = data.get("context", {})

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
                + len(self.system)
                + len(self.scheduler)
                + len(self.monitoring)
                + len(self.context_cmds)
            )
            log.info(
                "Loaded %d commands from %s  "
                "(static=%d, param=%d, chains=%d, dev=%d, sys=%d, sched=%d, mon=%d, ctx=%d)",
                total,
                commands_path.name,
                len(self.static),
                len(self.parameterized),
                len(self.chains),
                len(self.developer),
                len(self.system),
                len(self.scheduler),
                len(self.monitoring),
                len(self.context_cmds),
            )

        except FileNotFoundError:
            log.error("Command file not found: %s", commands_path)
            self.static = {}
            self.parameterized = {}
            self.chains = {}
            self.developer = {}
            self.dangerous = []
            self.system = {}
            self.scheduler = {}
            self.monitoring = {}
            self.context_cmds = {}
        except json.JSONDecodeError as exc:
            log.error("Invalid JSON in %s: %s", commands_path, exc)
            self.static = {}
            self.parameterized = {}
            self.chains = {}
            self.developer = {}
            self.dangerous = []
            self.system = {}
            self.scheduler = {}
            self.monitoring = {}
            self.context_cmds = {}

    # ------------------------------------------------------------------ #
    def parse(self, text: str, context=None) -> ParseResult:
        """
        Match *text* against the whitelist.

        Resolution order:
          1. Context-aware match (pronoun resolution — v1.2)
          2. Exact match in static
          3. Exact match in developer
          4. Exact match in system
          5. Scheduler match (v1.2)
          6. Monitor match (v1.2)
          7. Parameterized match (keyword + extracted parameter)
          8. Chain match
          9. Keyword/substring fallback across static + developer + system

        Args:
            text: The spoken text to parse.
            context: Optional SessionContext for pronoun resolution.

        Returns:
            ParseResult with matched_key, commands list, and flags.
        """
        if not text:
            return ParseResult()

        text = text.lower().strip()

        # 0. Context-aware — session info queries
        if text in ("what was my last app", "session status", "what's my context"):
            if context:
                info = context.get_status()
                return ParseResult(
                    matched_key=text,
                    is_info=True,
                    info_text=info,
                )
            else:
                return ParseResult(
                    matched_key=text,
                    is_info=True,
                    info_text="No context tracking available.",
                )

        # 1. Context-aware — pronoun resolution
        if context and text in self.context_cmds:
            resolved = context.resolve_pronoun(text)
            if resolved:
                matched_key, ps_cmd = resolved
                # Check if the resolved command is dangerous
                needs_confirm = matched_key in self.dangerous
                log.info("Context match: '%s' → '%s'", text, matched_key)
                return ParseResult(
                    matched_key=matched_key,
                    commands=[ps_cmd],
                    is_context=True,
                    needs_confirmation=needs_confirm,
                )
            else:
                return ParseResult(
                    matched_key=text,
                    is_info=True,
                    info_text="I don't have enough context to understand that. Try being more specific.",
                )

        # 2. Exact match — static
        if text in self.static:
            log.info("Static exact match: '%s'", text)
            needs_confirm = text in self.dangerous
            return ParseResult(
                matched_key=text,
                commands=[self.static[text]],
                needs_confirmation=needs_confirm,
            )

        # 3. Exact match — developer
        if text in self.developer:
            log.info("Developer exact match: '%s'", text)
            needs_confirm = text in self.dangerous
            return ParseResult(
                matched_key=text,
                commands=[self.developer[text]],
                needs_confirmation=needs_confirm,
            )

        # 4. Exact match — system
        if text in self.system:
            log.info("System exact match: '%s'", text)
            needs_confirm = text in self.dangerous
            return ParseResult(
                matched_key=text,
                commands=[self.system[text]],
                needs_confirmation=needs_confirm,
            )

        # 5. Scheduler match
        result = self._match_scheduler(text)
        if result.matched:
            return result

        # 6. Monitor match
        result = self._match_monitor(text)
        if result.matched:
            return result

        # 7. Parameterized match
        result = self._match_parameterized(text)
        if result.matched:
            return result

        # 8. Chain match
        result = self._match_chain(text)
        if result.matched:
            return result

        # 9. Keyword / substring fallback (longest key first for accuracy)
        all_flat = {**self.static, **self.developer, **self.system}
        for key in sorted(all_flat, key=len, reverse=True):
            if key in text:
                log.info("Keyword match: '%s' found in '%s'", key, text)
                needs_confirm = key in self.dangerous
                return ParseResult(
                    matched_key=key,
                    commands=[all_flat[key]],
                    needs_confirmation=needs_confirm,
                )

        log.info("No match for: '%s'", text)
        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_parameterized(self, text: str) -> ParseResult:
        """
        Check if text starts with a parameterized trigger keyword
        and extract the dynamic portion.
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
    def _match_scheduler(self, text: str) -> ParseResult:
        """
        Parse scheduler commands like:
          "schedule shutdown at 10 PM"
          "schedule restart at 10:30 PM"
          "schedule shutdown in 30 minutes"
        """
        for key in sorted(self.scheduler, key=len, reverse=True):
            entry = self.scheduler[key]
            extract_after = entry.get("extract_after", key).lower()

            if text.startswith(extract_after):
                time_part = text[len(extract_after):].strip()
                # Remove filler words
                time_part = re.sub(r"^(at|for|in)\s+", "", time_part, count=1)

                if not time_part:
                    log.info("Scheduler match '%s' but no time extracted.", key)
                    return ParseResult()

                sched_type = entry.get("type", "shutdown")

                # Parse time expression
                parsed_time = self._parse_time_expression(time_part)
                if parsed_time is None:
                    log.warning("Could not parse time expression: '%s'", time_part)
                    return ParseResult(
                        matched_key=key,
                        is_info=True,
                        info_text=f"I couldn't understand the time: {time_part}. "
                                  f"Try something like '10 PM' or 'in 30 minutes'.",
                    )

                # Build schtasks command
                task_name = f"VARNA_{'Shutdown' if sched_type == 'shutdown' else 'Restart'}"
                action = "Stop-Computer -Force" if sched_type == "shutdown" else "Restart-Computer -Force"
                ps_cmd = (
                    f"schtasks /Create /TN '{task_name}' /TR "
                    f"\"powershell -NoProfile -Command {action}\" "
                    f"/SC ONCE /ST {parsed_time} /F"
                )

                log.info(
                    "Scheduler match: type='%s', raw_time='%s', parsed='%s'",
                    sched_type, time_part, parsed_time,
                )
                return ParseResult(
                    matched_key=f"{key} at {parsed_time}",
                    commands=[ps_cmd],
                    is_scheduler=True,
                    needs_confirmation=True,
                )

        return ParseResult()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_time_expression(time_str: str) -> str | None:
        """
        Convert natural time expressions to 24-hour HH:MM format.

        Supported formats:
          "10 pm"       → "22:00"
          "10:30 pm"    → "22:30"
          "2 am"        → "02:00"
          "14:00"       → "14:00"
          "30 minutes"  → (current time + 30 min, formatted)

        Returns:
            Time string in HH:MM format, or None if unparsable.
        """
        time_str = time_str.lower().strip()

        # "in X minutes" / "X minutes from now"
        minutes_match = re.match(r"(\d+)\s*minutes?", time_str)
        if minutes_match:
            from datetime import datetime, timedelta
            mins = int(minutes_match.group(1))
            target = datetime.now() + timedelta(minutes=mins)
            return target.strftime("%H:%M")

        # "in X hours"
        hours_match = re.match(r"(\d+)\s*hours?", time_str)
        if hours_match:
            from datetime import datetime, timedelta
            hrs = int(hours_match.group(1))
            target = datetime.now() + timedelta(hours=hrs)
            return target.strftime("%H:%M")

        # "10:30 pm" or "10:30pm"
        ampm_match = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_str)
        if ampm_match:
            hour = int(ampm_match.group(1))
            minute = int(ampm_match.group(2))
            period = ampm_match.group(3)
            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            return f"{hour:02d}:{minute:02d}"

        # "10 pm" or "10pm"
        ampm_match2 = re.match(r"(\d{1,2})\s*(am|pm)", time_str)
        if ampm_match2:
            hour = int(ampm_match2.group(1))
            period = ampm_match2.group(2)
            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            return f"{hour:02d}:00"

        # "14:00" — already 24-hour
        h24_match = re.match(r"(\d{1,2}):(\d{2})$", time_str)
        if h24_match:
            hour = int(h24_match.group(1))
            minute = int(h24_match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"

        return None

    # ------------------------------------------------------------------ #
    def _match_monitor(self, text: str) -> ParseResult:
        """
        Parse monitoring commands:
          "monitor chrome memory usage"  → start monitoring chrome
          "stop monitoring"              → stop the monitor
          "check process chrome"         → one-shot status
        """
        # "stop monitoring"
        if text in ("stop monitoring", "stop monitor"):
            log.info("Monitor stop command detected.")
            return ParseResult(
                matched_key="stop monitoring",
                is_monitor=True,
                monitor_action="stop",
            )

        # "monitor {process} memory usage" / "monitor {process}"
        mon_match = re.match(r"^monitor\s+(\w+)(?:\s+memory\s+usage)?$", text)
        if mon_match:
            process = mon_match.group(1).strip()
            log.info("Monitor start: process='%s'", process)
            return ParseResult(
                matched_key=f"monitor {process}",
                is_monitor=True,
                monitor_action="start",
                monitor_process=process,
            )

        # "check process {name}"
        check_match = re.match(r"^check\s+process\s+(\w+)$", text)
        if check_match:
            process = check_match.group(1).strip()
            log.info("Monitor check: process='%s'", process)
            return ParseResult(
                matched_key=f"check process {process}",
                is_monitor=True,
                monitor_action="check",
                monitor_process=process,
            )

        return ParseResult()

    # ------------------------------------------------------------------ #
    def list_commands(self) -> list[str]:
        """Return all available spoken command phrases."""
        all_keys = []
        all_keys.extend(self.static.keys())
        all_keys.extend(self.developer.keys())
        all_keys.extend(self.system.keys())
        all_keys.extend(f"{k} <...>" for k in self.parameterized.keys())
        all_keys.extend(self.chains.keys())
        all_keys.extend(f"{k} <time>" for k in self.scheduler.keys())
        all_keys.extend(self.context_cmds.keys())
        return all_keys

    # ------------------------------------------------------------------ #
    def list_developer_commands(self) -> list[str]:
        """Return only developer-mode command phrases."""
        return list(self.developer.keys())
