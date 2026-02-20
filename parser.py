"""
VARNA v1.5 - Command Parser
Maps spoken text to safe, whitelisted PowerShell commands.

v1.5 additions:
  - Universal app scan / list / dynamic close
  - All v1.4 features (NLP, window, typing, tabs, smart search)

Matching strategy (in order):
  1. Context — pronoun resolution
  2. Exact match — static / developer / system
  3. Clipboard
  4. App scan / list commands (v1.5)
  5. Tab control (v1.4)
  6. Window commands (v1.4)
  7. Dynamic close (v1.5)
  8. Macro list/delete
  9. Scheduler
 10. Monitor
 11. Smart screenshot
 12. File search
 13. Voice typing (v1.4)
 14. Macro record
 15. Parameterized (browser-aware)
 16. Chain match
 17. Smart open/close — via WindowManager + AppManager
 18. Keyword/substring fallback
 19. Fuzzy match fallback (v1.4)
 20. Intent-based fallback (v1.4)
 21. Macro trigger fallback
"""

import json
import re
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus
from utils.logger import get_logger
from nlp import TextNormalizer

log = get_logger(__name__)

_COMMANDS_FILE = Path(__file__).resolve().parent / "commands.json"

# Instantiate the NLP normalizer
_nlp = TextNormalizer()


# ====================================================================== #
@dataclass
class ParseResult:
    """Result of parsing a spoken command."""
    matched_key: str | None = None
    commands: list[str] = field(default_factory=list)
    is_chain: bool = False
    needs_confirmation: bool = False
    is_scheduler: bool = False
    is_monitor: bool = False
    monitor_action: str | None = None
    monitor_process: str | None = None
    is_context: bool = False
    is_info: bool = False
    info_text: str | None = None
    # v1.3
    is_clipboard: bool = False
    is_file_search: bool = False
    file_search_query: str | None = None
    is_screenshot: bool = False
    screenshot_name: str | None = None
    is_macro: bool = False
    macro_action: str | None = None
    macro_name: str | None = None
    macro_steps: list[str] = field(default_factory=list)
    # v1.4
    is_window: bool = False                # window control command
    window_action: str | None = None       # "smart_open" | "minimize" | "maximize" | "restore" | "switch" | "show_desktop" | "open_new"
    window_target: str | None = None       # app name
    is_typing: bool = False                # voice typing
    typing_text: str | None = None         # text to type
    is_tab: bool = False                   # tab control
    tab_action: str | None = None          # "close" | "new" | "next" | "prev" | "reopen"
    is_in_tab_search: bool = False         # search in current tab
    search_query: str | None = None        # query for in-tab search
    # v1.5
    is_app_scan: bool = False              # scan / refresh / list installed apps
    app_scan_action: str | None = None     # "scan" | "list"
    is_dynamic_close: bool = False         # close any app via psutil
    close_target: str | None = None        # app name to close
    is_key_press: bool = False             # press a keyboard key
    key_name: str | None = None            # "enter" | "escape" | "tab" | "backspace" | "delete"

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

            self.static: dict[str, str] = data.get("static", {})
            self.parameterized: dict[str, dict] = data.get("parameterized", {})
            self.chains: dict[str, dict] = data.get("chains", {})
            self.developer: dict[str, str] = data.get("developer", {})
            self.dangerous: list[str] = data.get("dangerous", [])
            self.system: dict[str, str] = data.get("system", {})
            self.scheduler: dict[str, dict] = data.get("scheduler", {})
            self.monitoring: dict[str, dict] = data.get("monitoring", {})
            self.context_cmds: dict[str, str] = data.get("context", {})
            self.clipboard_cmds: dict[str, str] = data.get("clipboard", {})
            self.file_search_cfg: dict = data.get("file_search", {})
            self.macro_cmds: dict[str, str] = data.get("macros", {})
            self.window_cmds: dict[str, str] = data.get("window", {})
            self.tab_cmds: dict[str, str] = data.get("tabs", {})

            if not any(k in data for k in ("static", "parameterized", "chains")):
                self.static = data

            total = (
                len(self.static) + len(self.parameterized) + len(self.chains)
                + len(self.developer) + len(self.system) + len(self.scheduler)
                + len(self.monitoring) + len(self.context_cmds)
                + len(self.clipboard_cmds) + len(self.macro_cmds)
                + len(self.window_cmds) + len(self.tab_cmds)
            )
            log.info("Loaded %d command entries from %s", total, commands_path.name)

        except (FileNotFoundError, json.JSONDecodeError) as exc:
            log.error("Command file error: %s", exc)
            self._init_empty()

    def _init_empty(self):
        for attr in ("static", "parameterized", "chains", "developer",
                      "system", "scheduler", "monitoring", "context_cmds",
                      "clipboard_cmds", "file_search_cfg", "macro_cmds",
                      "window_cmds", "tab_cmds"):
            setattr(self, attr, {})
        self.dangerous = []

    # ------------------------------------------------------------------ #
    def parse(self, text: str, context=None, macro_manager=None) -> ParseResult:
        """
        Match text against the whitelist with NLP preprocessing.
        """
        if not text:
            return ParseResult()

        # v1.4 — NLP preprocessing: clean filler words
        original = text.lower().strip()
        text = _nlp.clean(original)

        if text != original:
            log.info("NLP cleaned: '%s' → '%s'", original, text)

        # 0. Context info queries
        if text in ("what was my last app", "session status", "what's my context"):
            if context:
                return ParseResult(matched_key=text, is_info=True, info_text=context.get_status())
            return ParseResult(matched_key=text, is_info=True, info_text="No context tracking available.")

        # 1. Context — pronoun resolution
        if context and text in self.context_cmds:
            resolved = context.resolve_pronoun(text)
            if resolved:
                mk, ps = resolved
                return ParseResult(matched_key=mk, commands=[ps], is_context=True,
                                   needs_confirmation=mk in self.dangerous)
            return ParseResult(matched_key=text, is_info=True,
                               info_text="I don't have enough context. Try being more specific.")

        # 2. Exact match — static
        if text in self.static:
            # v1.4: route "open X" through window intelligence
            result = self._try_smart_open(text)
            if result:
                return result
            return ParseResult(matched_key=text, commands=[self.static[text]],
                               needs_confirmation=text in self.dangerous)

        # 3. Exact — developer
        if text in self.developer:
            return ParseResult(matched_key=text, commands=[self.developer[text]],
                               needs_confirmation=text in self.dangerous)

        # 4. Exact — system
        if text in self.system:
            return ParseResult(matched_key=text, commands=[self.system[text]],
                               needs_confirmation=text in self.dangerous)

        # 5. Clipboard (v1.3)
        if text in self.clipboard_cmds:
            return ParseResult(matched_key=text, is_clipboard=True)

        # 5.5 App scan / list (v1.5)
        if text in ("scan apps", "refresh app list", "refresh apps", "rescan apps"):
            return ParseResult(matched_key=text, is_app_scan=True, app_scan_action="scan")
        if text in ("list installed apps", "list apps", "show installed apps", "what apps do i have"):
            return ParseResult(matched_key=text, is_app_scan=True, app_scan_action="list")

        # 5.6 Key press commands (v1.5 polish)
        key_map = {
            "press enter": "enter",
            "hit enter": "enter",
            "send it": "enter",
            "send this": "enter",
            "send message": "enter",
            "search now": "enter",
            "submit": "enter",
            "press escape": "escape",
            "press backspace": "backspace",
            "undo typing": "backspace",
            "press delete": "delete",
            "press tab key": "tab",
            "select all": "select_all",
            "undo": "undo",
            "redo": "redo",
            "copy this": "copy",
            "paste it": "paste",
            "cut this": "cut",
        }
        if text in key_map:
            key = key_map[text]
            return ParseResult(matched_key=text, is_key_press=True, key_name=key)

        # 6. Tab control (v1.4)
        result = self._match_tab(text)
        if result.matched:
            return result

        # 7. Window commands (v1.4) — switch/minimize/maximize/restore/show desktop
        result = self._match_window(text)
        if result.matched:
            return result

        # 7.5 Dynamic close (v1.5) — "close X" for any app
        m = re.match(r"^close\s+(?:the\s+)?(.+)$", text)
        if m:
            target = m.group(1).strip()
            # Skip if it's a known static command (e.g. "close tab")
            if target not in ("tab", "this tab", "the tab", "current tab"):
                # Check if it's in static commands first
                if f"close {target}" not in self.static:
                    return ParseResult(matched_key=f"close {target}",
                                       is_dynamic_close=True, close_target=target)


        # 8. Macro list/delete
        if text in self.macro_cmds:
            return ParseResult(matched_key=text, is_macro=True, macro_action="list")
        result = self._match_macro_delete(text)
        if result.matched:
            return result

        # 9. Scheduler
        result = self._match_scheduler(text)
        if result.matched:
            return result

        # 10. Monitor
        result = self._match_monitor(text)
        if result.matched:
            return result

        # 11. Smart screenshot (v1.3)
        result = self._match_screenshot(text)
        if result.matched:
            return result

        # 12. File search (v1.3)
        result = self._match_file_search(text)
        if result.matched:
            return result

        # 13. Voice typing (v1.4) — "type hello world"
        result = self._match_typing(text)
        if result.matched:
            return result

        # 14. Macro record
        result = self._match_macro_record(text)
        if result.matched:
            return result

        # 15. Parameterized (browser-aware)
        result = self._match_parameterized(text, context=context)
        if result.matched:
            return result

        # 16. Chain match
        result = self._match_chain(text)
        if result.matched:
            return result

        # 17. Keyword/substring fallback
        all_flat = {**self.static, **self.developer, **self.system}
        for key in sorted(all_flat, key=len, reverse=True):
            if key in text:
                result = self._try_smart_open(key)
                if result:
                    return result
                return ParseResult(matched_key=key, commands=[all_flat[key]],
                                   needs_confirmation=key in self.dangerous)

        # 18. v1.4 — Fuzzy match fallback (handles speech recognition errors)
        all_keys = list(all_flat.keys()) + list(self.chains.keys())
        fuzzy = _nlp.fuzzy_match(text, all_keys, threshold=0.75)
        if fuzzy:
            if fuzzy in all_flat:
                result = self._try_smart_open(fuzzy)
                if result:
                    return result
                return ParseResult(matched_key=fuzzy, commands=[all_flat[fuzzy]],
                                   needs_confirmation=fuzzy in self.dangerous)
            if fuzzy in self.chains:
                steps = self.chains[fuzzy].get("steps", [])
                return ParseResult(matched_key=fuzzy, commands=steps, is_chain=True)

        # 19. v1.4 — Intent-based fallback (NLP intent extraction)
        result = self._match_intent(text, context)
        if result.matched:
            return result

        # 20. Macro trigger fallback
        if macro_manager and macro_manager.has(text):
            steps = macro_manager.get(text)
            return ParseResult(matched_key=f"macro: {text}", is_macro=True,
                               macro_action="play", macro_name=text, macro_steps=steps)

        log.info("No match for: '%s'", text)
        return ParseResult()

    # ------------------------------------------------------------------ #
    def _try_smart_open(self, key: str) -> ParseResult | None:
        """
        If key is an 'open X' command (not folder/directory), route through
        window intelligence instead of raw Start-Process.
        """
        m = re.match(r"^open\s+(.+)$", key)
        if m:
            app = m.group(1).strip()
            # Skip folder opens — those go through Start-Process
            if app in ("downloads", "documents", "desktop", "folder"):
                return None
            # Skip open website
            if app.startswith("website"):
                return None
            log.info("Routing 'open %s' through window intelligence.", app)
            return ParseResult(
                matched_key=key, is_window=True,
                window_action="smart_open", window_target=app,
            )
        return None

    # ------------------------------------------------------------------ #
    def _match_window(self, text: str) -> ParseResult:
        """
        Match window control commands:
          "switch to chrome", "minimize edge", "maximize vscode",
          "restore notepad", "show desktop", "minimize all",
          "open new chrome window"
        """
        # Show desktop / minimize all
        if text in ("show desktop", "minimize all"):
            return ParseResult(matched_key=text, is_window=True,
                               window_action="show_desktop")

        # "open new X window"
        m = re.match(r"^open\s+new\s+(\w+)(?:\s+window)?$", text)
        if m:
            app = m.group(1).strip()
            return ParseResult(matched_key=f"open new {app} window", is_window=True,
                               window_action="open_new", window_target=app)

        # "switch to X"
        m = re.match(r"^switch\s+to\s+(.+)$", text)
        if m:
            app = m.group(1).strip()
            return ParseResult(matched_key=f"switch to {app}", is_window=True,
                               window_action="switch", window_target=app)

        # "minimize X"
        m = re.match(r"^minimize\s+(.+)$", text)
        if m:
            app = m.group(1).strip()
            if app not in ("all",):
                return ParseResult(matched_key=f"minimize {app}", is_window=True,
                                   window_action="minimize", window_target=app)

        # "maximize X"
        m = re.match(r"^maximize\s+(.+)$", text)
        if m:
            app = m.group(1).strip()
            return ParseResult(matched_key=f"maximize {app}", is_window=True,
                               window_action="maximize", window_target=app)

        # "restore X"
        m = re.match(r"^restore\s+(.+)$", text)
        if m:
            app = m.group(1).strip()
            if app not in ("last window",):
                return ParseResult(matched_key=f"restore {app}", is_window=True,
                                   window_action="restore", window_target=app)

        # "restore last window"
        if text == "restore last window":
            return ParseResult(matched_key=text, is_window=True,
                               window_action="restore_last")

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_tab(self, text: str) -> ParseResult:
        """Match tab control commands — supports natural variations."""
        tab_map = {
            # Close tab
            "close tab": "close",
            "close this tab": "close",
            "close the tab": "close",
            "close current tab": "close",
            # New tab
            "new tab": "new",
            "open new tab": "new",
            "open a new tab": "new",
            # Next tab
            "next tab": "next",
            "go to next tab": "next",
            "switch to next tab": "next",
            "go next tab": "next",
            # Previous tab
            "previous tab": "prev",
            "go to previous tab": "prev",
            "switch to previous tab": "prev",
            "go previous tab": "prev",
            "go to last tab": "prev",
            "last tab": "prev",
            "prev tab": "prev",
            # Reopen
            "reopen tab": "reopen",
            "reopen last tab": "reopen",
            "reopen closed tab": "reopen",
            "open last closed tab": "reopen",
        }
        if text in tab_map:
            return ParseResult(matched_key=text, is_tab=True, tab_action=tab_map[text])
        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_typing(self, text: str) -> ParseResult:
        """
        Match voice typing commands:
          "type hello world"
          "write good morning"
          "enter username admin"
        """
        m = re.match(r"^(?:type|write|enter)\s+(.+)$", text)
        if m:
            content = m.group(1).strip()
            if content:
                log.info("Voice typing: '%s'", content)
                return ParseResult(matched_key=f"type: {content}",
                                   is_typing=True, typing_text=content)
        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_intent(self, text: str, context=None) -> ParseResult:
        """
        v1.4 — Intent-based fallback using NLP intent extraction.
        Handles natural phrases like "launch chrome" → open chrome.
        """
        intent, obj, param = _nlp.extract_intent(text)

        if not intent:
            return ParseResult()

        log.info("Intent extracted: intent='%s', obj='%s', param='%s'", intent, obj, param)

        # open / launch / start / bring up
        if intent == "open" and obj:
            return ParseResult(
                matched_key=f"open {obj}", is_window=True,
                window_action="smart_open", window_target=obj,
            )

        # close / quit / kill / terminate — use dynamic close (v1.5)
        if intent == "close" and obj:
            return ParseResult(matched_key=f"close {obj}",
                               is_dynamic_close=True, close_target=obj)

        # search
        if intent == "search" and param:
            encoded = quote_plus(param)
            browser = "chrome"
            if context and hasattr(context, "last_browser") and context.last_browser:
                browser = context.last_browser
            cmd = f"Start-Process {browser} 'https://www.google.com/search?q={encoded}'"
            return ParseResult(matched_key=f"search {param}", commands=[cmd])

        # switch to
        if intent == "switch" and obj:
            return ParseResult(matched_key=f"switch to {obj}", is_window=True,
                               window_action="switch", window_target=obj)

        # minimize / maximize / restore
        if intent in ("minimize", "maximize", "restore") and obj:
            return ParseResult(matched_key=f"{intent} {obj}", is_window=True,
                               window_action=intent, window_target=obj)

        # type / write
        if intent == "type" and param:
            return ParseResult(matched_key=f"type: {param}",
                               is_typing=True, typing_text=param)

        # find
        if intent == "find" and param:
            return ParseResult(matched_key=f"find {param}",
                               is_file_search=True, file_search_query=param)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_parameterized(self, text: str, context=None) -> ParseResult:
        """Parameterized command matching with browser-aware context."""
        for key in sorted(self.parameterized, key=len, reverse=True):
            entry = self.parameterized[key]
            extract_after = entry.get("extract_after", key).lower()

            if text.startswith(extract_after):
                raw_query = text[len(extract_after):].strip()
                raw_query = re.sub(r"^(for|about|on|the)\s+", "", raw_query, count=1)

                if not raw_query:
                    return ParseResult()

                encoded_query = quote_plus(raw_query)
                command = entry["template"].replace("{query}", encoded_query)

                # Browser-aware context
                if context and hasattr(context, "last_browser") and context.last_browser:
                    browser = context.last_browser
                    command = re.sub(
                        r"Start-Process\s+(chrome|firefox|msedge)",
                        f"Start-Process {browser}", command, count=1,
                    )

                # v1.4 — Smart search routing: if browser is active, search in current tab
                if key in ("search", "search youtube"):
                    return ParseResult(
                        matched_key=f"{key} {raw_query}",
                        commands=[command],
                        is_in_tab_search=True,
                        search_query=raw_query,
                    )

                return ParseResult(matched_key=f"{key} {raw_query}", commands=[command])

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_chain(self, text: str) -> ParseResult:
        if text in self.chains:
            steps = self.chains[text].get("steps", [])
            return ParseResult(matched_key=text, commands=steps, is_chain=True)
        for key in sorted(self.chains, key=len, reverse=True):
            if key in text:
                steps = self.chains[key].get("steps", [])
                return ParseResult(matched_key=key, commands=steps, is_chain=True)
        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_scheduler(self, text: str) -> ParseResult:
        for key in sorted(self.scheduler, key=len, reverse=True):
            entry = self.scheduler[key]
            extract_after = entry.get("extract_after", key).lower()
            if text.startswith(extract_after):
                time_part = text[len(extract_after):].strip()
                time_part = re.sub(r"^(at|for|in)\s+", "", time_part, count=1)
                if not time_part:
                    return ParseResult()
                sched_type = entry.get("type", "shutdown")
                parsed_time = self._parse_time_expression(time_part)
                if parsed_time is None:
                    return ParseResult(matched_key=key, is_info=True,
                                       info_text=f"I couldn't understand the time: {time_part}.")
                task_name = f"VARNA_{'Shutdown' if sched_type == 'shutdown' else 'Restart'}"
                action = "Stop-Computer -Force" if sched_type == "shutdown" else "Restart-Computer -Force"
                ps_cmd = (f"schtasks /Create /TN '{task_name}' /TR "
                          f"\"powershell -NoProfile -Command {action}\" /SC ONCE /ST {parsed_time} /F")
                return ParseResult(matched_key=f"{key} at {parsed_time}", commands=[ps_cmd],
                                   is_scheduler=True, needs_confirmation=True)
        return ParseResult()

    @staticmethod
    def _parse_time_expression(time_str: str) -> str | None:
        time_str = time_str.lower().strip()
        m = re.match(r"(\d+)\s*minutes?", time_str)
        if m:
            from datetime import datetime, timedelta
            return (datetime.now() + timedelta(minutes=int(m.group(1)))).strftime("%H:%M")
        m = re.match(r"(\d+)\s*hours?", time_str)
        if m:
            from datetime import datetime, timedelta
            return (datetime.now() + timedelta(hours=int(m.group(1)))).strftime("%H:%M")
        m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_str)
        if m:
            h, mi, p = int(m.group(1)), int(m.group(2)), m.group(3)
            if p == "pm" and h != 12: h += 12
            elif p == "am" and h == 12: h = 0
            return f"{h:02d}:{mi:02d}"
        m = re.match(r"(\d{1,2})\s*(am|pm)", time_str)
        if m:
            h, p = int(m.group(1)), m.group(2)
            if p == "pm" and h != 12: h += 12
            elif p == "am" and h == 12: h = 0
            return f"{h:02d}:00"
        m = re.match(r"(\d{1,2}):(\d{2})$", time_str)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            if 0 <= h <= 23 and 0 <= mi <= 59:
                return f"{h:02d}:{mi:02d}"
        return None

    # ------------------------------------------------------------------ #
    def _match_monitor(self, text: str) -> ParseResult:
        if text in ("stop monitoring", "stop monitor"):
            return ParseResult(matched_key="stop monitoring", is_monitor=True, monitor_action="stop")
        m = re.match(r"^monitor\s+(\w+)(?:\s+memory\s+usage)?$", text)
        if m:
            p = m.group(1).strip()
            return ParseResult(matched_key=f"monitor {p}", is_monitor=True,
                               monitor_action="start", monitor_process=p)
        m = re.match(r"^check\s+process\s+(\w+)$", text)
        if m:
            p = m.group(1).strip()
            return ParseResult(matched_key=f"check process {p}", is_monitor=True,
                               monitor_action="check", monitor_process=p)
        return ParseResult()

    def _match_screenshot(self, text: str) -> ParseResult:
        for pat in [r"^(?:take\s+)?screenshot\s+as\s+(.+)$",
                    r"^save\s+screenshot\s+as\s+(.+)$",
                    r"^capture\s+screen\s+as\s+(.+)$"]:
            m = re.match(pat, text)
            if m:
                name = re.sub(r"[^\w\-]", "", m.group(1).strip().replace(" ", "_")) or "screenshot"
                return ParseResult(matched_key=f"screenshot as {name}",
                                   is_screenshot=True, screenshot_name=name)
        return ParseResult()

    def _match_file_search(self, text: str) -> ParseResult:
        triggers = self.file_search_cfg.get("triggers", ["find", "locate"])
        for trigger in sorted(triggers, key=len, reverse=True):
            if text.startswith(trigger):
                query = text[len(trigger):].strip()
                query = re.sub(r"^(file|files|named|called|document|documents)\s+", "", query)
                if query:
                    return ParseResult(matched_key=f"find {query}",
                                       is_file_search=True, file_search_query=query)
        return ParseResult()

    def _match_macro_record(self, text: str) -> ParseResult:
        for pat in [r"^(?:whenever|when)\s+i\s+say\s+(.+?)\s+do\s+(.+)$",
                    r"^create\s+macro\s+(.+?)\s+do\s+(.+)$",
                    r"^save\s+macro\s+(.+?)\s+do\s+(.+)$"]:
            m = re.match(pat, text)
            if m:
                name = m.group(1).strip()
                steps = [s.strip() for s in re.split(r"\s+and\s+", m.group(2).strip()) if s.strip()]
                if name and steps:
                    return ParseResult(matched_key=f"create macro: {name}", is_macro=True,
                                       macro_action="record", macro_name=name, macro_steps=steps)
        return ParseResult()

    def _match_macro_delete(self, text: str) -> ParseResult:
        m = re.match(r"^delete\s+macro\s+(.+)$", text)
        if m:
            name = m.group(1).strip()
            return ParseResult(matched_key=f"delete macro: {name}", is_macro=True,
                               macro_action="delete", macro_name=name)
        return ParseResult()

    # ------------------------------------------------------------------ #
    def list_commands(self) -> list[str]:
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
        all_keys.extend(self.tab_cmds.keys())
        all_keys.extend(self.window_cmds.keys())
        return all_keys

    def list_developer_commands(self) -> list[str]:
        return list(self.developer.keys())
