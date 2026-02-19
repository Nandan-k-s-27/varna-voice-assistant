"""
VARNA v1.3 - Command Parser
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
  9. Clipboard     – clipboard read/speak (v1.3)
 10. File Search   – find files by name/type/date (v1.3)
 11. Smart Screenshot – screenshot with custom name (v1.3)
 12. Macros        – user-defined command sequences (v1.3)

Matching strategy (in order):
  1. Context match – pronoun resolution  ("close it" → last app).
  2. Exact match   – spoken text matches a key exactly (static → developer → system).
  3. Clipboard match (v1.3)
  4. Macro match (v1.3)
  5. Scheduler     – "schedule shutdown at 10 PM"
  6. Monitoring    – "monitor chrome memory usage"
  7. Smart screenshot – "screenshot as ReactBug"   (v1.3)
  8. File search   – "find PDF downloaded yesterday" (v1.3)
  9. Macro record  – "whenever I say X do Y"     (v1.3)
 10. Parameterized – spoken text starts with a trigger keyword.
 11. Chain match   – spoken text matches a chain key.
 12. Keyword match – spoken text *contains* a key as a substring.
"""

import json
import re
import os
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
    # v1.3 additions
    is_clipboard: bool = False          # clipboard read/speak
    is_file_search: bool = False        # file search command
    file_search_query: str | None = None
    is_screenshot: bool = False         # smart screenshot
    screenshot_name: str | None = None  # custom screenshot filename
    is_macro: bool = False              # macro command
    macro_action: str | None = None     # "record" | "play" | "list" | "delete"
    macro_name: str | None = None
    macro_steps: list[str] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        return self.matched_key is not None


# ====================================================================== #
class Parser:
    """Maps natural-language text to safe, whitelisted PowerShell commands."""

    def __init__(self, commands_path: Path = _COMMANDS_FILE):
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

            # v1.3 additions
            self.clipboard_cmds: dict[str, str] = data.get("clipboard", {})
            self.file_search_cfg: dict = data.get("file_search", {})
            self.macro_cmds: dict[str, str] = data.get("macros", {})

            # Backward compatibility
            if not any(k in data for k in ("static", "parameterized", "chains", "developer")):
                self.static = data
                log.info("Loaded v1.0-style flat command file — treating all as static.")

            total = (
                len(self.static) + len(self.parameterized) + len(self.chains)
                + len(self.developer) + len(self.system) + len(self.scheduler)
                + len(self.monitoring) + len(self.context_cmds)
                + len(self.clipboard_cmds) + len(self.macro_cmds)
            )
            log.info("Loaded %d command entries from %s", total, commands_path.name)

        except FileNotFoundError:
            log.error("Command file not found: %s", commands_path)
            self._init_empty()
        except json.JSONDecodeError as exc:
            log.error("Invalid JSON in %s: %s", commands_path, exc)
            self._init_empty()

    def _init_empty(self):
        self.static = {}
        self.parameterized = {}
        self.chains = {}
        self.developer = {}
        self.dangerous = []
        self.system = {}
        self.scheduler = {}
        self.monitoring = {}
        self.context_cmds = {}
        self.clipboard_cmds = {}
        self.file_search_cfg = {}
        self.macro_cmds = {}

    # ------------------------------------------------------------------ #
    def parse(self, text: str, context=None, macro_manager=None) -> ParseResult:
        """
        Match *text* against the whitelist.

        Resolution order:
          1. Context-aware match (pronoun resolution)
          2. Exact match in static / developer / system
          3. Clipboard commands (v1.3)
          4. Macro list/delete/play (v1.3)
          5. Scheduler match
          6. Monitor match
          7. Smart screenshot (v1.3)
          8. File search (v1.3)
          9. Macro record (v1.3)
         10. Parameterized match (browser-aware)
         11. Chain match
         12. Keyword/substring fallback
         13. Macro trigger fallback (v1.3)
        """
        if not text:
            return ParseResult()

        text = text.lower().strip()

        # 0. Context-aware — session info queries
        if text in ("what was my last app", "session status", "what's my context"):
            if context:
                info = context.get_status()
                return ParseResult(matched_key=text, is_info=True, info_text=info)
            else:
                return ParseResult(matched_key=text, is_info=True,
                                   info_text="No context tracking available.")

        # 1. Context-aware — pronoun resolution
        if context and text in self.context_cmds:
            resolved = context.resolve_pronoun(text)
            if resolved:
                matched_key, ps_cmd = resolved
                needs_confirm = matched_key in self.dangerous
                log.info("Context match: '%s' → '%s'", text, matched_key)
                return ParseResult(
                    matched_key=matched_key, commands=[ps_cmd],
                    is_context=True, needs_confirmation=needs_confirm,
                )
            else:
                return ParseResult(
                    matched_key=text, is_info=True,
                    info_text="I don't have enough context to understand that. Try being more specific.",
                )

        # 2. Exact match — static
        if text in self.static:
            log.info("Static exact match: '%s'", text)
            needs_confirm = text in self.dangerous
            return ParseResult(matched_key=text, commands=[self.static[text]],
                               needs_confirmation=needs_confirm)

        # 3. Exact match — developer
        if text in self.developer:
            log.info("Developer exact match: '%s'", text)
            needs_confirm = text in self.dangerous
            return ParseResult(matched_key=text, commands=[self.developer[text]],
                               needs_confirmation=needs_confirm)

        # 4. Exact match — system
        if text in self.system:
            log.info("System exact match: '%s'", text)
            needs_confirm = text in self.dangerous
            return ParseResult(matched_key=text, commands=[self.system[text]],
                               needs_confirmation=needs_confirm)

        # 5. Clipboard commands (v1.3)
        if text in self.clipboard_cmds:
            log.info("Clipboard match: '%s'", text)
            return ParseResult(matched_key=text, is_clipboard=True)

        # 6. Macro list/delete (v1.3)
        if text in self.macro_cmds:
            log.info("Macro list command: '%s'", text)
            return ParseResult(matched_key=text, is_macro=True, macro_action="list")

        result = self._match_macro_delete(text)
        if result.matched:
            return result

        # 7. Scheduler match
        result = self._match_scheduler(text)
        if result.matched:
            return result

        # 8. Monitor match
        result = self._match_monitor(text)
        if result.matched:
            return result

        # 9. Smart screenshot (v1.3) — "screenshot as ReactBug"
        result = self._match_screenshot(text)
        if result.matched:
            return result

        # 10. File search (v1.3) — "find PDF downloaded yesterday"
        result = self._match_file_search(text)
        if result.matched:
            return result

        # 11. Macro record (v1.3) — "whenever I say X do Y"
        result = self._match_macro_record(text)
        if result.matched:
            return result

        # 12. Parameterized match (browser-aware via context)
        result = self._match_parameterized(text, context=context)
        if result.matched:
            return result

        # 13. Chain match
        result = self._match_chain(text)
        if result.matched:
            return result

        # 14. Keyword / substring fallback (longest key first)
        all_flat = {**self.static, **self.developer, **self.system}
        for key in sorted(all_flat, key=len, reverse=True):
            if key in text:
                log.info("Keyword match: '%s' found in '%s'", key, text)
                needs_confirm = key in self.dangerous
                return ParseResult(matched_key=key, commands=[all_flat[key]],
                                   needs_confirmation=needs_confirm)

        # 15. Macro trigger fallback (v1.3) — check if it matches a saved macro
        if macro_manager and macro_manager.has(text):
            steps = macro_manager.get(text)
            log.info("Macro trigger: '%s' → %d steps", text, len(steps))
            return ParseResult(
                matched_key=f"macro: {text}", is_macro=True,
                macro_action="play", macro_name=text, macro_steps=steps,
            )

        log.info("No match for: '%s'", text)
        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_parameterized(self, text: str, context=None) -> ParseResult:
        """Check if text starts with a parameterized trigger keyword."""
        for key in sorted(self.parameterized, key=len, reverse=True):
            entry = self.parameterized[key]
            extract_after = entry.get("extract_after", key).lower()

            if text.startswith(extract_after):
                raw_query = text[len(extract_after):].strip()
                raw_query = re.sub(r"^(for|about|on|the)\s+", "", raw_query, count=1)

                if not raw_query:
                    log.info("Parameterized match '%s' but no query extracted.", key)
                    return ParseResult()

                encoded_query = quote_plus(raw_query)
                command = entry["template"].replace("{query}", encoded_query)

                # Browser-aware context (v1.2)
                if context and hasattr(context, "last_browser") and context.last_browser:
                    browser = context.last_browser
                    command = re.sub(
                        r"Start-Process\s+(chrome|firefox|msedge)",
                        f"Start-Process {browser}",
                        command, count=1,
                    )
                    log.info("Browser-aware: using '%s' for this command.", browser)

                log.info("Parameterized match: key='%s', query='%s'", key, raw_query)
                return ParseResult(matched_key=f"{key} {raw_query}", commands=[command])

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_chain(self, text: str) -> ParseResult:
        """Check if text matches a multi-step command chain."""
        if text in self.chains:
            entry = self.chains[text]
            steps = entry.get("steps", [])
            log.info("Chain exact match: '%s' (%d steps)", text, len(steps))
            return ParseResult(matched_key=text, commands=steps, is_chain=True)

        for key in sorted(self.chains, key=len, reverse=True):
            if key in text:
                entry = self.chains[key]
                steps = entry.get("steps", [])
                log.info("Chain keyword match: '%s' in '%s'", key, text)
                return ParseResult(matched_key=key, commands=steps, is_chain=True)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_scheduler(self, text: str) -> ParseResult:
        """Parse scheduler commands like 'schedule shutdown at 10 PM'."""
        for key in sorted(self.scheduler, key=len, reverse=True):
            entry = self.scheduler[key]
            extract_after = entry.get("extract_after", key).lower()

            if text.startswith(extract_after):
                time_part = text[len(extract_after):].strip()
                time_part = re.sub(r"^(at|for|in)\s+", "", time_part, count=1)

                if not time_part:
                    log.info("Scheduler match '%s' but no time extracted.", key)
                    return ParseResult()

                sched_type = entry.get("type", "shutdown")
                parsed_time = self._parse_time_expression(time_part)

                if parsed_time is None:
                    return ParseResult(
                        matched_key=key, is_info=True,
                        info_text=f"I couldn't understand the time: {time_part}. "
                                  f"Try something like '10 PM' or 'in 30 minutes'.",
                    )

                task_name = f"VARNA_{'Shutdown' if sched_type == 'shutdown' else 'Restart'}"
                action = "Stop-Computer -Force" if sched_type == "shutdown" else "Restart-Computer -Force"
                ps_cmd = (
                    f"schtasks /Create /TN '{task_name}' /TR "
                    f"\"powershell -NoProfile -Command {action}\" "
                    f"/SC ONCE /ST {parsed_time} /F"
                )

                log.info("Scheduler match: type='%s', time='%s'", sched_type, parsed_time)
                return ParseResult(
                    matched_key=f"{key} at {parsed_time}", commands=[ps_cmd],
                    is_scheduler=True, needs_confirmation=True,
                )

        return ParseResult()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_time_expression(time_str: str) -> str | None:
        """Convert natural time expressions to 24-hour HH:MM format."""
        time_str = time_str.lower().strip()

        minutes_match = re.match(r"(\d+)\s*minutes?", time_str)
        if minutes_match:
            from datetime import datetime, timedelta
            mins = int(minutes_match.group(1))
            target = datetime.now() + timedelta(minutes=mins)
            return target.strftime("%H:%M")

        hours_match = re.match(r"(\d+)\s*hours?", time_str)
        if hours_match:
            from datetime import datetime, timedelta
            hrs = int(hours_match.group(1))
            target = datetime.now() + timedelta(hours=hrs)
            return target.strftime("%H:%M")

        ampm_match = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_str)
        if ampm_match:
            hour, minute = int(ampm_match.group(1)), int(ampm_match.group(2))
            period = ampm_match.group(3)
            if period == "pm" and hour != 12: hour += 12
            elif period == "am" and hour == 12: hour = 0
            return f"{hour:02d}:{minute:02d}"

        ampm_match2 = re.match(r"(\d{1,2})\s*(am|pm)", time_str)
        if ampm_match2:
            hour = int(ampm_match2.group(1))
            period = ampm_match2.group(2)
            if period == "pm" and hour != 12: hour += 12
            elif period == "am" and hour == 12: hour = 0
            return f"{hour:02d}:00"

        h24_match = re.match(r"(\d{1,2}):(\d{2})$", time_str)
        if h24_match:
            hour, minute = int(h24_match.group(1)), int(h24_match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"

        return None

    # ------------------------------------------------------------------ #
    def _match_monitor(self, text: str) -> ParseResult:
        """Parse monitoring commands."""
        if text in ("stop monitoring", "stop monitor"):
            log.info("Monitor stop command detected.")
            return ParseResult(matched_key="stop monitoring", is_monitor=True,
                               monitor_action="stop")

        mon_match = re.match(r"^monitor\s+(\w+)(?:\s+memory\s+usage)?$", text)
        if mon_match:
            process = mon_match.group(1).strip()
            log.info("Monitor start: process='%s'", process)
            return ParseResult(matched_key=f"monitor {process}", is_monitor=True,
                               monitor_action="start", monitor_process=process)

        check_match = re.match(r"^check\s+process\s+(\w+)$", text)
        if check_match:
            process = check_match.group(1).strip()
            log.info("Monitor check: process='%s'", process)
            return ParseResult(matched_key=f"check process {process}", is_monitor=True,
                               monitor_action="check", monitor_process=process)

        return ParseResult()

    # ------------------------------------------------------------------ #
    # v1.3 — Smart Screenshot
    # ------------------------------------------------------------------ #
    def _match_screenshot(self, text: str) -> ParseResult:
        """
        Match smart screenshot commands:
          "screenshot as ReactBug"
          "take screenshot as LoginPage"
          "save screenshot as dashboard"
        """
        patterns = [
            r"^(?:take\s+)?screenshot\s+as\s+(.+)$",
            r"^save\s+screenshot\s+as\s+(.+)$",
            r"^capture\s+screen\s+as\s+(.+)$",
        ]
        for pattern in patterns:
            m = re.match(pattern, text)
            if m:
                name = m.group(1).strip().replace(" ", "_")
                # Sanitize filename
                name = re.sub(r"[^\w\-]", "", name)
                if not name:
                    name = "screenshot"
                log.info("Smart screenshot: name='%s'", name)
                return ParseResult(
                    matched_key=f"screenshot as {name}",
                    is_screenshot=True,
                    screenshot_name=name,
                )
        return ParseResult()

    # ------------------------------------------------------------------ #
    # v1.3 — File Search
    # ------------------------------------------------------------------ #
    def _match_file_search(self, text: str) -> ParseResult:
        """
        Match file search commands:
          "find PDF downloaded yesterday"
          "find files named report"
          "find document report"
          "locate file budget"
        """
        triggers = self.file_search_cfg.get("triggers", ["find", "locate"])

        for trigger in sorted(triggers, key=len, reverse=True):
            if text.startswith(trigger):
                query = text[len(trigger):].strip()
                # Remove filler words
                query = re.sub(r"^(file|files|named|called|document|documents)\s+", "", query)
                if not query:
                    return ParseResult()

                log.info("File search: query='%s'", query)
                return ParseResult(
                    matched_key=f"find {query}",
                    is_file_search=True,
                    file_search_query=query,
                )

        return ParseResult()

    # ------------------------------------------------------------------ #
    # v1.3 — Macro Record
    # ------------------------------------------------------------------ #
    def _match_macro_record(self, text: str) -> ParseResult:
        """
        Match macro recording commands:
          "whenever I say focus mode do open vscode and open chrome"
          "when I say coding time do open vscode and open chrome and kill port 3000"
          "create macro study mode open chrome and open notepad"
        """
        patterns = [
            r"^(?:whenever|when)\s+i\s+say\s+(.+?)\s+do\s+(.+)$",
            r"^create\s+macro\s+(.+?)\s+do\s+(.+)$",
            r"^save\s+macro\s+(.+?)\s+do\s+(.+)$",
        ]
        for pattern in patterns:
            m = re.match(pattern, text)
            if m:
                name = m.group(1).strip()
                steps_raw = m.group(2).strip()
                # Split on " and " to get individual step names
                steps = [s.strip() for s in re.split(r"\s+and\s+", steps_raw) if s.strip()]
                if name and steps:
                    log.info("Macro record: name='%s', steps=%s", name, steps)
                    return ParseResult(
                        matched_key=f"create macro: {name}",
                        is_macro=True,
                        macro_action="record",
                        macro_name=name,
                        macro_steps=steps,
                    )
        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_macro_delete(self, text: str) -> ParseResult:
        """Match macro delete commands: 'delete macro focus mode'"""
        m = re.match(r"^delete\s+macro\s+(.+)$", text)
        if m:
            name = m.group(1).strip()
            log.info("Macro delete: '%s'", name)
            return ParseResult(
                matched_key=f"delete macro: {name}",
                is_macro=True,
                macro_action="delete",
                macro_name=name,
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
        all_keys.extend(self.clipboard_cmds.keys())
        all_keys.extend(self.macro_cmds.keys())
        return all_keys

    # ------------------------------------------------------------------ #
    def list_developer_commands(self) -> list[str]:
        """Return only developer-mode command phrases."""
        return list(self.developer.keys())
