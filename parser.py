"""
VARNA v2.3 - Command Parser
Maps spoken text to safe, whitelisted PowerShell commands.

Matching strategy (in order):
  1. Context — pronoun resolution
  2. Exact match — static / developer / system
  3. Clipboard
  4. App scan / list commands
  5. Tab control
  6. Window commands
  7. Dynamic close
  8. Macro list/delete
  9. Scheduler
 10. Monitor
 11. Smart screenshot
 12. File search
 13. Voice typing
 14. Macro record
 15. Parameterized (browser-aware)
 16. Chain match
 17. Smart open/close — via WindowManager + AppManager
 18. Keyword/substring fallback
 19. Fuzzy match fallback
 20. Intent-based fallback
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
from command_safety import get_safety_engine, CommandSafetyEngine, IntentCategory

log = get_logger(__name__)

_COMMANDS_FILE = Path(__file__).resolve().parent / "commands.json"

# Instantiate the NLP normalizer and safety engine
_nlp = TextNormalizer()
_safety = get_safety_engine()


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
    typing_press_enter: bool = True        # press Enter after typing (default: True for ChatGPT/search)
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
    # v1.5 polish
    is_selection: bool = False             # text selection command
    selection_action: str | None = None    # "select_word_name" | "select_line" | "select_word" | "select_next" | "go_to_line"
    selection_target: str | None = None    # word name or line number
    selection_count: int = 1               # how many words to select
    is_scroll: bool = False               # scroll command
    scroll_direction: str | None = None   # "up" | "down"
    scroll_amount: int = 5                # click count
    scroll_special: str | None = None     # "top" | "bottom" | "page_up" | "page_down"
    is_navigation: bool = False           # browser/explorer nav
    nav_action: str | None = None         # "back" | "forward" | "refresh" | "address_bar" | "drive" | "known_folder" | "this_pc"
    nav_target: str | None = None         # drive letter or folder path
    is_result_click: bool = False         # open search result by number
    result_number: int = 1                # which result (1-based)
    is_clipboard_history: bool = False    # clipboard history command
    clipboard_action: str | None = None   # "open" | "paste_nth"
    clipboard_index: int = 1              # which clipboard item (1-based)
    tab_number: int | None = None         # numbered tab (1-9)
    is_whatsapp: bool = False             # WhatsApp navigation
    whatsapp_action: str | None = None    # "open_chat" | "search_contact" | "new_chat"
    whatsapp_target: str | None = None    # chat number or contact name
    chat_number: int = 1                  # which chat (1-based)
    # v1.6 context
    is_repeat: bool = False               # repeat last command
    is_diagnostics: bool = False          # system self-test
    # v2.0
    is_voice_reply: bool = False          # command whose PS output should be spoken aloud
    # v2.0 safety
    match_confidence: float = 1.0         # how confident the match is (0.0-1.0)
    match_method: str = "exact"           # "exact" | "fuzzy" | "phonetic" | "intent"
    safety_blocked: bool = False          # blocked by safety engine
    safety_reason: str | None = None      # why blocked / confirmation needed
    voice_response: str | None = None     # what VARNA should say (voice interaction)

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

        # v3.2 optimization: Build key_map once instead of on every parse() call
        self._key_map = self._build_key_map()

    def _init_empty(self):
        for attr in ("static", "parameterized", "chains", "developer",
                      "system", "scheduler", "monitoring", "context_cmds",
                      "clipboard_cmds", "file_search_cfg", "macro_cmds",
                      "window_cmds", "tab_cmds"):
            setattr(self, attr, {})
        self.dangerous = []
        self._key_map = {}

    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_key_map() -> dict[str, str]:
        """Build the key press command map once at init time (v3.2 optimization)."""
        return {
            # Enter / Submit
            "press enter": "enter", "hit enter": "enter", "send it": "enter",
            "send this": "enter", "send message": "enter", "search now": "enter",
            "submit": "enter", "enter": "enter", "press return": "enter",
            # Escape
            "press escape": "escape", "cancel": "escape", "escape": "escape",
            "press esc": "escape", "esc": "escape",
            # Backspace / Delete
            "press backspace": "backspace", "undo typing": "backspace",
            "backspace": "backspace", "erase": "backspace",
            "press delete": "delete", "delete": "delete",
            "delete this": "delete", "delete that": "delete",
            "delete selected": "delete", "remove this": "delete",
            "remove that": "delete", "remove selected": "delete",
            # Tab key
            "press tab key": "tab", "press tab": "tab",
            # Select All
            "select all": "select_all", "select all text": "select_all",
            "select everything": "select_all", "highlight all": "select_all",
            "mark all": "select_all",
            "copy all": "copy_all", "copy everything": "copy_all",
            "select all and copy": "copy_all", "select and copy all": "copy_all",
            # Undo / Redo
            "undo": "undo", "undo that": "undo", "undo this": "undo",
            "undo last": "undo", "take it back": "undo", "revert": "undo",
            "revert that": "undo",
            "redo": "redo", "redo that": "redo", "redo this": "redo",
            "redo last": "redo", "do again": "redo",
            # Copy / Paste / Cut
            "copy": "copy", "copy this": "copy", "copy that": "copy",
            "copy it": "copy", "copy text": "copy", "copy selection": "copy",
            "copy selected": "copy", "copy selected text": "copy",
            "paste": "paste", "paste it": "paste", "paste here": "paste",
            "paste that": "paste", "paste text": "paste", "paste now": "paste",
            "paste content": "paste", "paste from clipboard": "paste",
            "paste clipboard": "paste", "clipboard paste": "paste",
            "paste copied": "paste", "paste copied text": "paste",
            "paste what i copied": "paste", "paste my clipboard": "paste",
            "cut": "cut", "cut this": "cut", "cut that": "cut",
            "cut it": "cut", "cut text": "cut", "cut selection": "cut",
            "cut selected": "cut", "cut selected text": "cut",
            # Space
            "press space": "space", "space": "space",
            # Arrow keys
            "press up": "up", "press down": "down",
            "press left": "left", "press right": "right",
            "arrow up": "up", "arrow down": "down",
            "arrow left": "left", "arrow right": "right",
            "move up": "up", "move down": "down",
            "move left": "left", "move right": "right",
            # Home / End
            "press home": "home", "press end": "end",
            "home": "home", "end": "end",
            "go to start": "home", "go to end": "end",
            "beginning": "home", "ending": "end",
            # Save
            "save": "save", "save this": "save", "save file": "save",
            "save it": "save", "save document": "save", "save now": "save",
            # Find / Search in page
            "find": "find", "find text": "find",
            "search in page": "find", "find in page": "find",
            "control f": "find", "ctrl f": "find",
            # Print
            "print": "print", "print this": "print",
            "print page": "print", "print document": "print",
            # New
            "new file": "new", "new document": "new",
            # Zoom
            "zoom in": "zoom_in", "zoom out": "zoom_out",
            "make bigger": "zoom_in", "make smaller": "zoom_out",
            "zoom reset": "zoom_reset", "reset zoom": "zoom_reset",
            "actual size": "zoom_reset", "normal zoom": "zoom_reset",
            # Full screen
            "full screen": "fullscreen", "fullscreen": "fullscreen",
            "go full screen": "fullscreen", "enter full screen": "fullscreen",
            "exit full screen": "escape", "exit fullscreen": "escape",
            # Bold / Italic / Underline
            "bold": "bold", "make bold": "bold", "bold text": "bold",
            "italic": "italic", "make italic": "italic", "italic text": "italic",
            "underline": "underline", "make underline": "underline",
            # Alt+Tab / Window switching
            "switch window": "alt_tab", "alt tab": "alt_tab",
            "next window": "alt_tab", "switch app": "alt_tab",
            # Task Manager
            "task manager": "task_manager", "open task manager": "task_manager",
            # Snap windows (Win+Arrow)
            "snap left": "snap_left", "snap window left": "snap_left",
            "move window left": "snap_left", "half screen left": "snap_left",
            "left half": "snap_left", "put it on the left": "snap_left",
            "snap right": "snap_right", "snap window right": "snap_right",
            "move window right": "snap_right", "half screen right": "snap_right",
            "right half": "snap_right", "put it on the right": "snap_right",
            # Show desktop (Win+D)
            "show desktop": "show_desktop", "desktop": "show_desktop",
            "hide all": "show_desktop", "minimize everything": "show_desktop",
            # Windows screenshot (Win+Shift+S)
            "screen snip": "win_screenshot", "snip screen": "win_screenshot",
            "screenshot area": "win_screenshot", "capture area": "win_screenshot",
            "snip it": "win_screenshot", "screen clip": "win_screenshot",
            # Lock PC (Win+L)
            "lock": "lock_pc", "lock pc": "lock_pc",
            "lock computer": "lock_pc", "lock screen": "lock_pc",
            # Emoji picker (Win+.)
            "emoji": "emoji_picker", "open emoji": "emoji_picker",
            "emoji picker": "emoji_picker", "insert emoji": "emoji_picker",
            "emojis": "emoji_picker",
            # File explorer (Win+E)
            "open explorer": "open_explorer", "file explorer": "open_explorer",
            # Settings (Win+I)
            "open settings": "open_settings", "settings": "open_settings",
            # Run dialog (Win+R)
            "run dialog": "run_dialog", "open run": "run_dialog",
            "run command": "run_dialog", "run box": "run_dialog",
            # Notification center (Win+N)
            "notifications": "notification_center", "show notifications": "notification_center",
            "notification center": "notification_center",
            # Close window (Alt+F4)
            "close window": "close_window", "close this window": "close_window",
            "alt f4": "close_window", "force close": "close_window",
            # Rename (F2)
            "rename": "rename", "rename this": "rename", "rename file": "rename",
            # Address bar (Alt+D or F6)
            "address bar": "address_bar", "go to address bar": "address_bar",
            "url bar": "address_bar", "type url": "address_bar",
            # Refresh (F5)
            "refresh": "refresh", "reload": "refresh",
            "refresh page": "refresh", "reload page": "refresh",
            # Page up / Page down
            "page up": "pageup", "page down": "pagedown",
            # ============ BROWSER NAVIGATION (v3.1) ============
            "focus address bar": "focus_address_bar", "go to url": "focus_address_bar",
            "type in address bar": "focus_address_bar", "url": "focus_address_bar",
            "go back": "go_back", "back page": "go_back",
            "navigate back": "go_back",
            "previous page": "go_back", "go to previous page": "go_back",
            "back": "go_back", "go previous": "go_back",
            "go forward": "go_forward", "forward page": "go_forward",
            "navigate forward": "go_forward",
            "next page": "go_forward", "go to next page": "go_forward",
            "forward": "go_forward", "go next": "go_forward",
            "hard refresh": "hard_refresh", "force refresh": "hard_refresh",
            "hard reload": "hard_refresh", "clear cache refresh": "hard_refresh",
            "open history": "open_history", "show history": "open_history",
            "browser history": "open_history", "history page": "open_history",
            "open downloads page": "open_downloads", "show downloads": "open_downloads",
            "download list": "open_downloads",
            "developer tools": "dev_tools", "dev tools": "dev_tools",
            "open dev tools": "dev_tools", "inspect element": "dev_tools",
            "inspect": "dev_tools", "open console": "dev_tools",
            "browser console": "dev_tools", "f12": "dev_tools",
            "close tab": "close_tab", "close this tab": "close_tab",
            "new tab": "new_tab", "open new tab": "new_tab",
            "reopen tab": "reopen_tab", "reopen closed tab": "reopen_tab",
            "open last closed tab": "reopen_tab", "restore tab": "reopen_tab",
            "next tab": "next_tab", "switch to next tab": "next_tab",
            "previous tab": "prev_tab", "switch to previous tab": "prev_tab",
            "last tab": "prev_tab", "prev tab": "prev_tab",
            "bookmark": "bookmark", "bookmark this": "bookmark",
            "add bookmark": "bookmark", "save bookmark": "bookmark",
            "open bookmarks": "open_bookmarks", "show bookmarks": "open_bookmarks",
            "bookmarks": "open_bookmarks",
            "incognito": "incognito", "private window": "incognito",
            "open incognito": "incognito", "private browsing": "incognito",
            "view source": "view_source", "page source": "view_source",
            "show source code": "view_source",
            "search bar": "search_bar", "focus search": "search_bar",
            "stop loading": "escape", "stop page": "escape",
            "stop": "escape", "cancel loading": "escape",
            "save page": "save", "save this page": "save",
            "print page": "print", "print this page": "print",
            # ============ TEXT NAVIGATION (v3.1) ============
            "next word": "next_word", "jump next word": "next_word",
            "move to next word": "next_word", "word right": "next_word",
            "previous word": "prev_word", "jump previous word": "prev_word",
            "move to previous word": "prev_word", "word left": "prev_word",
            "jump back word": "prev_word",
            "select next word": "select_next_word", "highlight next word": "select_next_word",
            "select previous word": "select_prev_word", "highlight previous word": "select_prev_word",
            "delete word": "delete_word", "delete last word": "delete_word",
            "erase word": "delete_word", "remove word": "delete_word",
            "delete next word": "delete_next_word", "erase next word": "delete_next_word",
            "start of line": "home", "beginning of line": "home",
            "end of line": "end", "line end": "end",
            "go to top": "go_top", "top of document": "go_top",
            "beginning of document": "go_top", "start of document": "go_top",
            "jump to top": "go_top", "document start": "go_top",
            "go to bottom": "go_bottom", "bottom of document": "go_bottom",
            "end of document": "go_bottom", "jump to bottom": "go_bottom",
            "document end": "go_bottom",
            "select this line": "select_line", "highlight line": "select_line",
            "select to start": "select_to_start", "select to beginning": "select_to_start",
            "select to end": "select_to_end", "select to line end": "select_to_end",
            "select to top": "select_to_top", "select all above": "select_to_top",
            "select to bottom": "select_to_bottom", "select all below": "select_to_bottom",
            "move line up": "move_line_up", "shift line up": "move_line_up",
            "move line down": "move_line_down", "shift line down": "move_line_down",
            "duplicate line": "duplicate_line", "copy line down": "duplicate_line",
            "delete line": "delete_line", "remove line": "delete_line",
            "erase line": "delete_line",
            "go to line": "go_to_line_dialog", "jump to line": "go_to_line_dialog",
            "comment": "toggle_comment", "toggle comment": "toggle_comment",
            "comment line": "toggle_comment", "uncomment": "toggle_comment",
            "indent": "indent", "tab in": "indent",
            "outdent": "outdent", "shift tab": "outdent", "unindent": "outdent",
            # ============ FILE EXPLORER (v3.1) ============
            "new folder": "new_folder", "create folder": "new_folder",
            "create new folder": "new_folder", "make folder": "new_folder",
            "properties": "properties", "file properties": "properties",
            "show properties": "properties", "details": "properties",
            "permanent delete": "permanent_delete", "permanently delete": "permanent_delete",
            "shift delete": "permanent_delete", "force delete": "permanent_delete",
            "select all files": "select_all",
            "preview pane": "preview_pane", "toggle preview": "preview_pane",
            "navigation pane": "nav_pane",
            "go back folder": "go_back", "previous folder": "go_back",
            "go up folder": "go_up_folder", "parent folder": "go_up_folder",
            "up one folder": "go_up_folder", "folder up": "go_up_folder",
            "go up": "go_up_folder", "up folder": "go_up_folder",
            "parent directory": "go_up_folder",
            "go forward folder": "go_forward", "next folder": "go_forward",
            # ============ SYSTEM / GLOBAL (v3.1) ============
            "screenshot": "print_screen", "print screen": "print_screen",
            "take screenshot": "print_screen", "capture screen": "print_screen",
            "screenshot window": "alt_print_screen", "capture window": "alt_print_screen",
            "windows search": "win_search", "search windows": "win_search",
            "search start menu": "win_search",
            "action center": "action_center", "quick settings": "action_center",
            "new desktop": "new_virtual_desktop", "new virtual desktop": "new_virtual_desktop",
            "next desktop": "next_virtual_desktop", "previous desktop": "prev_virtual_desktop",
            "close desktop": "close_virtual_desktop", "close virtual desktop": "close_virtual_desktop",
            "task view": "task_view", "show all windows": "task_view",
            "show open windows": "task_view",
            "dictation": "dictation", "start dictation": "dictation",
            "windows dictation": "dictation",
            # ============ RESULT NAVIGATION (v3.1) ============
            "next link": "next_link", "tab forward": "next_link",
            "next result": "next_link", "next item": "next_link",
            "click links": "next_link", "click the links": "next_link",
            "browse links": "next_link", "show links": "next_link",
            "navigate links": "next_link", "tab through links": "next_link",
            "go through links": "next_link", "cycle links": "next_link",
            "previous link": "prev_link", "tab backward": "prev_link",
            "previous result": "prev_link", "previous item": "prev_link",
            "open this": "enter", "click this": "enter",
            "open link": "enter", "click link": "enter",
            "click it": "enter", "click that": "enter",
            "open it": "enter", "open that": "enter",
            "select this": "enter", "confirm": "enter",
            "next field": "next_link", "previous field": "prev_link",
            # ============ MEDIA CONTROLS (v3.2) ============
            "play pause": "play_pause", "pause play": "play_pause",
            "toggle play": "play_pause", "play or pause": "play_pause",
            "next track": "next_track", "skip track": "next_track",
            "skip song": "next_track", "next song": "next_track",
            "previous track": "prev_track", "prev song": "prev_track",
            "previous song": "prev_track", "last song": "prev_track",
            # ============ ADDITIONAL SHORTCUTS (v3.2) ============
            "replace": "replace", "find and replace": "replace",
            "search and replace": "replace",
            "go to file": "go_to_file", "quick open": "go_to_file",
            "open file dialog": "go_to_file",
            "command palette": "command_palette", "open command palette": "command_palette",
            "toggle sidebar": "toggle_sidebar", "hide sidebar": "toggle_sidebar",
            "show sidebar": "toggle_sidebar",
            "toggle terminal": "toggle_terminal", "show terminal": "toggle_terminal",
            "hide terminal": "toggle_terminal",
            "close all tabs": "close_all_tabs",
            "pin tab": "pin_tab", "pin this tab": "pin_tab",
        }

    # ------------------------------------------------------------------ #
    def parse(self, text: str, context=None, macro_manager=None) -> ParseResult:
        """
        Match text against the whitelist with NLP preprocessing.
        """
        if not text:
            return ParseResult()

        # v1.4 — NLP preprocessing: clean filler words
        original = text.lower().strip()

        # IMPORTANT: Check typing BEFORE NLP cleaning to preserve user's text
        # "type the quick brown fox" must keep "the" — NLP would strip it
        # "type and send hello" → type + Enter,  "just type hello" → type only
        just_type_match = re.match(r"^just\s+(?:type|write)\s+(.+)$", original)
        if just_type_match:
            content = just_type_match.group(1).strip()
            if content:
                log.info("Voice typing (no enter): '%s'", content)
                return ParseResult(matched_key=f"type: {content}",
                                   is_typing=True, typing_text=content,
                                   typing_press_enter=False)

        typing_match = re.match(r"^(?:type|write|send|ask)\s+(?:and\s+(?:send|enter)\s+)?(.+)$", original)
        if typing_match:
            content = typing_match.group(1).strip()
            if content:
                log.info("Voice typing (pre-NLP): '%s'", content)
                return ParseResult(matched_key=f"type: {content}",
                                   is_typing=True, typing_text=content,
                                   typing_press_enter=True)

        text = _nlp.clean(original)

        if text != original:
            log.info("NLP cleaned: '%s' → '%s'", original, text)

        # 0. Context info queries
        if text in ("what was my last app", "session status", "what's my context"):
            if context:
                return ParseResult(matched_key=text, is_info=True, info_text=context.get_status())
            return ParseResult(matched_key=text, is_info=True, info_text="No context tracking available.")

        # 0.1 Repeat / do it again
        if text in ("repeat", "do it again", "do that again", "say that again",
                    "again", "one more time", "repeat that", "repeat command"):
            return ParseResult(matched_key=text, is_repeat=True)

        # 0.2 Close/minimize/maximize THIS (active foreground window)
        if text in ("close this", "close this window", "close current window",
                     "close window", "shut this", "close it"):
            return ParseResult(matched_key=text, is_window=True,
                               window_action="close_this")
        if text in ("minimize this", "minimize this window", "minimize", "minimise",
                     "minimise this", "minimize it", "hide this", "hide window"):
            return ParseResult(matched_key=text, is_window=True,
                               window_action="minimize_this")
        if text in ("maximize this", "maximize this window", "maximize", "maximise",
                     "maximise this", "maximize it", "full screen", "fullscreen",
                     "go full screen", "make it full screen"):
            return ParseResult(matched_key=text, is_window=True,
                               window_action="maximize_this")

        # 0.3 System Diagnostics
        if text in ("run diagnostics", "system test", "check status", "diagnostics", "check system"):
            return ParseResult(matched_key=text, is_diagnostics=True)

        # 1. Context — pronoun resolution
        if context and text in self.context_cmds:
            resolved = context.resolve_pronoun(text)
            if resolved:
                mk, ps = resolved
                return ParseResult(matched_key=mk, commands=[ps], is_context=True,
                                   needs_confirmation=mk in self.dangerous)
            return ParseResult(matched_key=text, is_info=True,
                               info_text="I don't have enough context. Try being more specific.")

        # ── Commands whose PowerShell output should be spoken aloud ──
        _VOICE_REPLY_PATTERNS = (
            "Get-Date", "battery", "wifi", "netsh wlan",
            "Get-PSDrive", "Get-Process", "ipconfig",
            "Get-ComputerInfo", "systeminfo", "hostname",
            "Get-CimInstance", "uptime",
        )

        def _is_voice_reply(ps_cmd: str) -> bool:
            return any(p.lower() in ps_cmd.lower() for p in _VOICE_REPLY_PATTERNS)

        # 2. Exact match — static
        if text in self.static:
            # v1.4: route "open X" through window intelligence
            result = self._try_smart_open(text)
            if result:
                return result
            ps_cmd = self.static[text]
            return ParseResult(matched_key=text, commands=[ps_cmd],
                               needs_confirmation=text in self.dangerous,
                               is_voice_reply=_is_voice_reply(ps_cmd))

        # 3. Exact — developer
        if text in self.developer:
            ps_cmd = self.developer[text]
            return ParseResult(matched_key=text, commands=[ps_cmd],
                               needs_confirmation=text in self.dangerous,
                               is_voice_reply=_is_voice_reply(ps_cmd))

        # 4. Exact — system
        if text in self.system:
            ps_cmd = self.system[text]
            return ParseResult(matched_key=text, commands=[ps_cmd],
                               needs_confirmation=text in self.dangerous,
                               is_voice_reply=_is_voice_reply(ps_cmd))

        # 5. Clipboard READ-ONLY (v3.0 fix: copy/paste/cut removed, handled by key_map)
        # Only intercept commands that READ or OPEN clipboard, NOT action commands
        _clipboard_read_cmds = {
            "read clipboard", "what did i copy", "what is in clipboard",
            "read what i copied", "read my clipboard", "what is copied",
            "what was copied", "tell me clipboard",
        }
        _clipboard_history_cmds = {
            "open clipboard", "clipboard history", "show clipboard history",
            "clipboard", "show clipboard",
        }
        if text in _clipboard_read_cmds:
            return ParseResult(matched_key=text, is_clipboard=True)
        if text in _clipboard_history_cmds:
            return ParseResult(matched_key=text, is_clipboard_history=True,
                               clipboard_action="open")

        # 5.5 App scan / list (v1.5)
        if text in ("scan apps", "refresh app list", "refresh apps", "rescan apps"):
            return ParseResult(matched_key=text, is_app_scan=True, app_scan_action="scan")
        if text in ("list installed apps", "list apps", "show installed apps", "what apps do i have"):
            return ParseResult(matched_key=text, is_app_scan=True, app_scan_action="list")

        # 5.6 Key press commands (v3.0 expanded — handles copy/paste/cut/undo/redo etc.)
        if text in self._key_map:
            key = self._key_map[text]
            return ParseResult(matched_key=text, is_key_press=True, key_name=key)

        # 6. Tab control (v1.4) — including numbered tabs
        result = self._match_tab(text)
        if result.matched:
            return result

        # 6.5 Text selection (v1.5 polish)
        result = self._match_selection(text)
        if result.matched:
            return result

        # 6.6 Scrolling (v1.5 polish)
        result = self._match_scroll(text)
        if result.matched:
            return result

        # 6.7 Browser/Explorer navigation (v1.5 polish)
        result = self._match_navigation(text)
        if result.matched:
            return result

        # 6.8 Open search result (v1.5 polish)
        result = self._match_result_click(text)
        if result.matched:
            return result

        # 6.9 Clipboard history (v1.5 polish)
        result = self._match_clipboard_history(text)
        if result.matched:
            return result

        # 6.10 WhatsApp navigation (v1.5)
        result = self._match_whatsapp(text)
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

        # 17. Keyword/substring fallback — WITH SAFETY GATE
        all_flat = {**self.static, **self.developer, **self.system}
        input_category = _safety.detect_category(text)
        for key in sorted(all_flat, key=len, reverse=True):
            if key in text:
                # Safety Gate: if the matched key is dangerous, verify input actually intended it
                verdict = _safety.evaluate(text, key, 0.85, "substring")
                if not verdict.allowed:
                    log.warning("Safety blocked substring match: '%s' → '%s': %s", 
                               text, key, verdict.blocked_reason)
                    continue  # Try next candidate, don't block entirely
                result = self._try_smart_open(key)
                if result:
                    result.match_method = "substring"
                    result.match_confidence = 0.85
                    result.needs_confirmation = result.needs_confirmation or verdict.needs_confirmation
                    if verdict.needs_confirmation:
                        result.voice_response = f"Did you mean '{key}'? Say confirm to proceed."
                    return result
                return ParseResult(matched_key=key, commands=[all_flat[key]],
                                   needs_confirmation=(key in self.dangerous) or verdict.needs_confirmation,
                                   match_method="substring", match_confidence=0.85,
                                   voice_response=f"Did you mean '{key}'? Say confirm to proceed." if verdict.needs_confirmation else None)

        # 18. v2.0 — Safety-Aware Fuzzy Match (replaces old aggressive fuzzy)
        all_keys = list(all_flat.keys()) + list(self.chains.keys())
        # Safety Gate 2: Remove dangerous commands from fuzzy candidates
        safe_keys = _safety.remove_dangerous_from_fuzzy(all_keys)
        # Safety Gate 4: Filter by intent category for better matching
        if input_category != IntentCategory.UNKNOWN:
            filtered_keys = _safety.filter_keys_by_category(input_category, safe_keys)
        else:
            filtered_keys = safe_keys
        
        # Get risk-based threshold instead of fixed 0.60
        threshold = _safety.get_threshold_for_category(input_category)
        threshold = max(threshold, 0.65)  # Never go below 65% for fuzzy
        
        fuzzy = _nlp.fuzzy_match(text, filtered_keys, threshold=threshold)
        if fuzzy:
            # Calculate actual confidence
            from difflib import SequenceMatcher
            confidence = SequenceMatcher(None, text, fuzzy).ratio()

            # Safety evaluation on the fuzzy result
            verdict = _safety.evaluate(text, fuzzy, confidence, "fuzzy")
            if not verdict.allowed:
                log.warning("Safety blocked fuzzy match: '%s' → '%s': %s", 
                           text, fuzzy, verdict.blocked_reason)
                # Don't execute, but tell user what happened
                return ParseResult(
                    matched_key=None,
                    safety_blocked=True,
                    safety_reason=verdict.blocked_reason,
                    voice_response=f"I heard '{text}' but couldn't match it confidently. Please try again.",
                )
            
            if fuzzy in all_flat:
                result = self._try_smart_open(fuzzy)
                if result:
                    result.match_method = "fuzzy"
                    result.match_confidence = confidence
                    result.needs_confirmation = result.needs_confirmation or verdict.needs_confirmation
                    if verdict.needs_confirmation:
                        result.voice_response = f"I think you said '{fuzzy}'. Confirm?"
                    return result
                return ParseResult(matched_key=fuzzy, commands=[all_flat[fuzzy]],
                                   needs_confirmation=(fuzzy in self.dangerous) or verdict.needs_confirmation,
                                   match_method="fuzzy", match_confidence=confidence,
                                   voice_response=f"I think you said '{fuzzy}'. Confirm?" if verdict.needs_confirmation else None)
            if fuzzy in self.chains:
                steps = self.chains[fuzzy].get("steps", [])
                return ParseResult(matched_key=fuzzy, commands=steps, is_chain=True,
                                   match_method="fuzzy", match_confidence=confidence)

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
            folder_keywords = ("downloads", "documents", "desktop", "folder",
                             "pictures", "photos", "music", "videos",
                             "my files", "my documents", "my pictures",
                             "my music", "my videos", "download folder")
            if app in folder_keywords:
                return None
            # Skip system/settings apps — these use ms-settings: URIs
            settings_keywords = (
                "settings", "wifi settings", "wi-fi settings",
                "bluetooth settings", "bluetooth", "display settings",
                "sound settings", "audio settings", "network settings",
                "storage settings", "apps settings", "windows update",
                "privacy settings", "personalization", "power settings",
                "notification settings", "keyboard settings",
                "mouse settings", "touchpad settings", "date time settings",
                "language settings", "about", "night light",
                "focus assist", "action center", "defender",
                "antivirus", "security", "feedback hub",
                "camera", "webcam", "voice recorder", "recorder",
                "weather", "calendar", "my calendar", "windows maps",
                "magnifier", "narrator", "on screen keyboard", "keyboard",
                "windows terminal", "w t", "clock", "alarms", "timer",
                "stopwatch", "sticky notes", "notes",
                "recycle bin", "trash", "recent files", "startup folder",
                "fonts", "remote desktop",
                "device manager", "disk management", "event viewer",
                "services", "system properties", "environment variables",
                "disk cleanup", "xbox game bar", "screen sketch",
            )
            if app in settings_keywords:
                return None
            # Skip website-related
            if app.startswith("website") or app.startswith("site"):
                return None
            # Skip URLs
            if "http" in app or "www" in app or ".com" in app:
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
        if text in ("show desktop", "minimize all", "minimize all windows",
                     "hide all windows", "clear desktop"):
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
        m = re.match(r"^(?:minimize|minimise)\s+(.+)$", text)
        if m:
            app = m.group(1).strip()
            if app not in ("all", "this", "it"):
                return ParseResult(matched_key=f"minimize {app}", is_window=True,
                                   window_action="minimize", window_target=app)

        # "maximize X"
        m = re.match(r"^(?:maximize|maximise)\s+(.+)$", text)
        if m:
            app = m.group(1).strip()
            if app not in ("this", "it"):
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

        # Numbered tab: "go to tab 3", "tab 5", "switch to tab 1", "first tab", "second tab"
        m = re.match(r"^(?:go to |switch to )?tab\s+(\d)$", text)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 9:
                return ParseResult(matched_key=f"tab {n}", is_tab=True,
                                   tab_action="numbered", tab_number=n)

        # Ordinal: "first tab", "second tab", etc.
        ordinal_map = {
            "first tab": 1, "1st tab": 1,
            "second tab": 2, "2nd tab": 2,
            "third tab": 3, "3rd tab": 3,
            "fourth tab": 4, "4th tab": 4,
            "fifth tab": 5, "5th tab": 5,
            "sixth tab": 6, "6th tab": 6,
            "seventh tab": 7, "7th tab": 7,
            "eighth tab": 8, "8th tab": 8,
            "ninth tab": 9, "9th tab": 9,
        }
        if text in ordinal_map:
            n = ordinal_map[text]
            return ParseResult(matched_key=text, is_tab=True,
                               tab_action="numbered", tab_number=n)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_selection(self, text: str) -> ParseResult:
        """
        Match text selection commands:
          "select good"           → find and select the word
          "select line"           → select current line
          "select word"           → select current word
          "select next 3 words"   → select next N words
          "go to line 10"         → jump to line
        """
        # "go to line N"
        m = re.match(r"^go to line\s+(\d+)$", text)
        if m:
            line_num = m.group(1)
            return ParseResult(matched_key=f"go to line {line_num}",
                               is_selection=True, selection_action="go_to_line",
                               selection_target=line_num)

        # "select line" / "select this line" / "select current line"
        if text in ("select line", "select this line", "select current line"):
            return ParseResult(matched_key=text, is_selection=True,
                               selection_action="select_line")

        # "select word" / "select this word" / "select current word"
        if text in ("select word", "select this word", "select current word"):
            return ParseResult(matched_key=text, is_selection=True,
                               selection_action="select_word")

        # "select next N words" / "select previous N words"
        m = re.match(r"^select\s+(next|previous|prev|last)\s+(\d+)\s+words?$", text)
        if m:
            direction = "next" if m.group(1) == "next" else "prev"
            count = int(m.group(2))
            return ParseResult(matched_key=f"select {direction} {count} words",
                               is_selection=True, selection_action=f"select_{direction}",
                               selection_count=count)

        # "select <word>" — find and select a specific word
        m = re.match(r"^select\s+(.+)$", text)
        if m:
            target = m.group(1).strip()
            # Avoid matching other select commands
            if target not in ("all", "line", "word", "this line", "this word",
                              "current line", "current word"):
                return ParseResult(matched_key=f"select {target}",
                                   is_selection=True, selection_action="select_word_name",
                                   selection_target=target)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_scroll(self, text: str) -> ParseResult:
        """
        Match scroll commands with sensitivity (v3.0 expanded):
          "scroll down"           → normal (5)
          "scroll little down"    → small (2)
          "scroll a lot down"     → big (15)
          "scroll to top"         → Ctrl+Home
          "page down"             → PageDown
          "go down"               → normal scroll
        """
        # Special scrolls
        special_map = {
            "scroll to top": "top",
            "scroll to the top": "top",
            "go to top": "top",
            "go to the top": "top",
            "top of page": "top",
            "top of the page": "top",
            "scroll top": "top",
            "scroll to bottom": "bottom",
            "scroll to the bottom": "bottom",
            "go to bottom": "bottom",
            "go to the bottom": "bottom",
            "bottom of page": "bottom",
            "bottom of the page": "bottom",
            "scroll bottom": "bottom",
            "page down": "page_down",
            "page up": "page_up",
            "next page": "page_down",
            "previous page": "page_up",
            "go to next page": "page_down",
            "go to previous page": "page_up",
        }
        if text in special_map:
            return ParseResult(matched_key=text, is_scroll=True,
                               scroll_special=special_map[text])

        # Direct simple phrases: "go down", "go up", "down", "up" (in browsing context)
        simple_scroll = {
            "go down": ("down", 5),
            "go up": ("up", 5),
            "move down": ("down", 5),
            "move up": ("up", 5),
            "scroll down": ("down", 5),
            "scroll up": ("up", 5),
            "down": ("down", 5),
            "up": ("up", 5),
        }
        if text in simple_scroll:
            direction, amount = simple_scroll[text]
            return ParseResult(matched_key=f"scroll {direction}",
                               is_scroll=True, scroll_direction=direction,
                               scroll_amount=amount)

        # Sensitivity-based scrolling
        m = re.match(
            r"^scroll\s+(?:(little|slightly|a little|a bit|bit|small)\s+)?(up|down)$",
            text
        )
        if m:
            modifier = m.group(1)
            direction = m.group(2)
            amount = 2 if modifier else 5
            return ParseResult(matched_key=f"scroll {direction}",
                               is_scroll=True, scroll_direction=direction,
                               scroll_amount=amount)

        m = re.match(
            r"^scroll\s+(?:(a lot|way|much|fast|big|more|lots)\s+)?(up|down)$",
            text
        )
        if m and m.group(1):
            direction = m.group(2)
            return ParseResult(matched_key=f"scroll {direction} a lot",
                               is_scroll=True, scroll_direction=direction,
                               scroll_amount=15)

        # "scroll down a lot" / "scroll up a little" (modifier AFTER direction)
        m = re.match(
            r"^scroll\s+(up|down)\s+(a lot|a little|a bit|more|fast|slowly?)$",
            text
        )
        if m:
            direction = m.group(1)
            modifier = m.group(2)
            if modifier in ("a lot", "more", "fast"):
                amount = 15
            elif modifier in ("a little", "a bit", "slow", "slowly"):
                amount = 2
            else:
                amount = 5
            return ParseResult(matched_key=f"scroll {direction}",
                               is_scroll=True, scroll_direction=direction,
                               scroll_amount=amount)

        # Numeric scrolling: "scroll down 10", "scroll up 3"
        m = re.match(r"^scroll\s+(up|down)\s+(\d+)$", text)
        if m:
            direction = m.group(1)
            amount = min(int(m.group(2)), 50)  # cap at 50
            return ParseResult(matched_key=f"scroll {direction} {amount}",
                               is_scroll=True, scroll_direction=direction,
                               scroll_amount=amount)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_navigation(self, text: str) -> ParseResult:
        """
        Match browser / file explorer navigation:
          "go back"             → Alt+Left
          "go forward"          → Alt+Right
          "refresh page"        → F5
          "go to address bar"   → Ctrl+L
          "go to D drive"       → navigate in same window
          "go to this pc"       → This PC
          "go to downloads"     → known folder
          "open folder pgcet"   → navigate into subfolder
          "search for X"        → File Explorer search box
        """
        nav_map = {
            "go back": "back",
            "go to previous page": "back",
            "previous page": "back",
            "back": "back",
            "navigate back": "back",
            "go forward": "forward",
            "go to next page": "forward",
            "next page": "forward",
            "forward": "forward",
            "navigate forward": "forward",
            "refresh page": "refresh",
            "refresh": "refresh",
            "reload": "refresh",
            "reload page": "refresh",
            "go to address bar": "address_bar",
            "address bar": "address_bar",
            "focus address bar": "address_bar",
        }
        if text in nav_map:
            return ParseResult(matched_key=text, is_navigation=True,
                               nav_action=nav_map[text])

        # Drive navigation: "go to D drive" / "open D drive" / "open drive D"
        m = re.match(r"^(?:go to|open|navigate to)\s+([a-z])\s+drive$", text)
        if m:
            drive = m.group(1).upper()
            return ParseResult(matched_key=f"go to {drive} drive",
                               is_navigation=True, nav_action="drive",
                               nav_target=f"{drive}:\\")

        m = re.match(r"^(?:go to|open|navigate to)\s+drive\s+([a-z])$", text)
        if m:
            drive = m.group(1).upper()
            return ParseResult(matched_key=f"go to drive {drive}",
                               is_navigation=True, nav_action="drive",
                               nav_target=f"{drive}:\\")

        # This PC / My Computer
        if text in ("go to this pc", "open this pc", "this pc",
                    "go to my computer", "open my computer", "my computer"):
            return ParseResult(matched_key=text, is_navigation=True,
                               nav_action="this_pc")

        # Known folders
        known_folders = {
            "desktop": "Desktop",
            "downloads": "Downloads",
            "documents": "Documents",
            "pictures": "Pictures",
            "music": "Music",
            "videos": "Videos",
        }
        m = re.match(r"^(?:go to|open|navigate to)\s+(desktop|downloads|documents|pictures|music|videos)$", text)
        if m:
            folder_key = m.group(1)
            return ParseResult(matched_key=f"go to {folder_key}",
                               is_navigation=True, nav_action="known_folder",
                               nav_target=known_folders[folder_key])

        # Open/select a folder by name in current File Explorer window
        # "open folder pgcet" / "go to folder projects" / "select pgcet folder"
        m = re.match(r"^(?:open|go to|navigate to)\s+(?:folder\s+)(.+)$", text)
        if m:
            folder = m.group(1).strip()
            # Guard: don't match known nav commands already handled above
            if folder not in ("this pc", "my computer") and "drive" not in folder:
                return ParseResult(matched_key=f"open folder {folder}",
                                   is_navigation=True, nav_action="open_folder",
                                   nav_target=folder)

        m = re.match(r"^select\s+(.+?)\s+folder$", text)
        if m:
            folder = m.group(1).strip()
            return ParseResult(matched_key=f"open folder {folder}",
                               is_navigation=True, nav_action="open_folder",
                               nav_target=folder)

        # File Explorer search: "search for X" / "search X in explorer"
        # "find X here" / "search here for X"
        m = re.match(r"^search\s+(?:for\s+)?(.+?)(?:\s+in\s+explorer|\s+here)?$", text)
        if m:
            query = m.group(1).strip()
            # Guard: don't match generic "search X" that should go to browser
            if text.endswith("in explorer") or text.endswith("here") or text.startswith("search for "):
                return ParseResult(matched_key=f"search explorer {query}",
                                   is_navigation=True, nav_action="explorer_search",
                                   nav_target=query)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_result_click(self, text: str) -> ParseResult:
        """
        Match search result opening:
          "open result 1"       → Tab to first link → Enter
          "open first result"   → same
        """
        # "open result N"
        m = re.match(r"^open\s+result\s+(\d+)$", text)
        if m:
            n = int(m.group(1))
            return ParseResult(matched_key=f"open result {n}",
                               is_result_click=True, result_number=n)

        # Ordinal: "open first result", "open second result", "open first link"
        ordinal_results = {
            "open first result": 1, "open 1st result": 1,
            "open second result": 2, "open 2nd result": 2,
            "open third result": 3, "open 3rd result": 3,
            "open fourth result": 4, "open 4th result": 4,
            "open fifth result": 5, "open 5th result": 5,
            # Link variants
            "open first link": 1, "open 1st link": 1,
            "click first link": 1, "click 1st link": 1,
            "open second link": 2, "open 2nd link": 2,
            "click second link": 2, "click 2nd link": 2,
            "open third link": 3, "open 3rd link": 3,
            "click third link": 3, "click 3rd link": 3,
            "open fourth link": 4, "open 4th link": 4,
            "click fourth link": 4, "click 4th link": 4,
            "open fifth link": 5, "open 5th link": 5,
            "click fifth link": 5, "click 5th link": 5,
            # Generic click result
            "click first result": 1, "click 1st result": 1,
            "click second result": 2, "click 2nd result": 2,
            "click third result": 3, "click 3rd result": 3,
        }
        if text in ordinal_results:
            n = ordinal_results[text]
            return ParseResult(matched_key=text, is_result_click=True,
                               result_number=n)

        # "open link N" / "click link N" / "open result N"  
        m = re.match(r"^(?:open|click)\s+(?:link|result)\s+(\d+)$", text)
        if m:
            n = int(m.group(1))
            return ParseResult(matched_key=f"open result {n}",
                               is_result_click=True, result_number=n)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_clipboard_history(self, text: str) -> ParseResult:
        """
        Match clipboard history commands:
          "open clipboard"          → Win+V
          "show clipboard"          → Win+V
          "paste 3rd item"          → Win+V → down × 2 → Enter
          "paste third copied"      → same
        """
        if text in ("open clipboard", "show clipboard", "show clipboard history",
                    "clipboard history", "open clipboard history"):
            return ParseResult(matched_key=text, is_clipboard_history=True,
                               clipboard_action="open")

        # "paste Nth item" / "paste Nth copied"
        m = re.match(r"^paste\s+(\d+)(?:st|nd|rd|th)?\s+(?:item|copied|content|entry)$", text)
        if m:
            n = int(m.group(1))
            return ParseResult(matched_key=f"paste item {n}",
                               is_clipboard_history=True,
                               clipboard_action="paste_nth", clipboard_index=n)

        # Ordinal: "paste first item", "paste second copied"
        ordinal_paste = {
            "paste first item": 1, "paste first copied": 1,
            "paste second item": 2, "paste second copied": 2,
            "paste third item": 3, "paste third copied": 3,
            "paste fourth item": 4, "paste fourth copied": 4,
            "paste fifth item": 5, "paste fifth copied": 5,
            "paste last item": 1,  # most recent = first in history
            "paste last copied": 1,
        }
        if text in ordinal_paste:
            n = ordinal_paste[text]
            return ParseResult(matched_key=text, is_clipboard_history=True,
                               clipboard_action="paste_nth", clipboard_index=n)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_whatsapp(self, text: str) -> ParseResult:
        """
        Match WhatsApp Desktop navigation:
          "open first chat"        → navigate to 1st chat
          "open 2nd chat"          → navigate to 2nd chat
          "open chat 5"            → navigate to 5th chat
          "search contact john"    → Ctrl+K → type name
          "new chat"               → Ctrl+N (WhatsApp Desktop)
        """
        # "new chat" (WhatsApp context)
        if text in ("new chat", "start new chat", "new conversation"):
            return ParseResult(matched_key=text, is_whatsapp=True,
                               whatsapp_action="new_chat")

        # "open chat N" / "open Nth chat"
        m = re.match(r"^open\s+chat\s+(\d+)$", text)
        if m:
            n = int(m.group(1))
            return ParseResult(matched_key=f"open chat {n}", is_whatsapp=True,
                               whatsapp_action="open_chat", chat_number=n)

        m = re.match(r"^open\s+(\d+)(?:st|nd|rd|th)?\s+chat$", text)
        if m:
            n = int(m.group(1))
            return ParseResult(matched_key=f"open chat {n}", is_whatsapp=True,
                               whatsapp_action="open_chat", chat_number=n)

        # Ordinal: "open first chat", "open second chat"
        ordinal_chats = {
            "open first chat": 1, "open 1st chat": 1,
            "open second chat": 2, "open 2nd chat": 2,
            "open third chat": 3, "open 3rd chat": 3,
            "open fourth chat": 4, "open 4th chat": 4,
            "open fifth chat": 5, "open 5th chat": 5,
            "open sixth chat": 6, "open 6th chat": 6,
            "open seventh chat": 7, "open 7th chat": 7,
            "open eighth chat": 8, "open 8th chat": 8,
            "open ninth chat": 9, "open 9th chat": 9,
            "open tenth chat": 10, "open 10th chat": 10,
            "open top chat": 1,
            "open last chat": 1,  # most recent = top chat
        }
        if text in ordinal_chats:
            n = ordinal_chats[text]
            return ParseResult(matched_key=text, is_whatsapp=True,
                               whatsapp_action="open_chat", chat_number=n)

        # "search contact X" / "find contact X" / "message X"
        m = re.match(r"^(?:search|find|message)\s+(?:contact\s+)?(.+)$", text)
        if m:
            contact = m.group(1).strip()
            # Avoid matching generic "search X" / "find X" (handled elsewhere)
            # Only match if it contains "contact" OR starts with "message"
            if "contact" in text or text.startswith("message"):
                return ParseResult(matched_key=f"search contact {contact}",
                                   is_whatsapp=True, whatsapp_action="search_contact",
                                   whatsapp_target=contact)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_typing(self, text: str) -> ParseResult:
        """
        Match voice typing commands:
          "type hello world"       → type + Enter
          "write good morning"     → type + Enter
          "send hello"             → type + Enter
          "just type hello"        → type only (no Enter)
        """
        # "just type X" → no Enter
        m_just = re.match(r"^just\s+(?:type|write)\s+(.+)$", text)
        if m_just:
            content = m_just.group(1).strip()
            if content:
                log.info("Voice typing (no enter): '%s'", content)
                return ParseResult(matched_key=f"type: {content}",
                                   is_typing=True, typing_text=content,
                                   typing_press_enter=False)

        m = re.match(r"^(?:type|write|send|ask)\s+(?:and\s+(?:send|enter)\s+)?(.+)$", text)
        if m:
            content = m.group(1).strip()
            if content:
                log.info("Voice typing: '%s'", content)
                return ParseResult(matched_key=f"type: {content}",
                                   is_typing=True, typing_text=content,
                                   typing_press_enter=True)
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
                               is_typing=True, typing_text=param,
                               typing_press_enter=True)

        # find
        if intent == "find" and param:
            return ParseResult(matched_key=f"find {param}",
                               is_file_search=True, file_search_query=param)

        return ParseResult()

    # ------------------------------------------------------------------ #
    def _match_parameterized(self, text: str, context=None) -> ParseResult:
        """Parameterized command matching with browser-aware context and alias support."""
        for key in sorted(self.parameterized, key=len, reverse=True):
            entry = self.parameterized[key]
            extract_after = entry.get("extract_after", key).lower()
            aliases = [a.lower() for a in entry.get("aliases", [])]
            
            # Check main trigger and all aliases
            triggers = [extract_after] + aliases
            
            matched_trigger = None
            for trigger in sorted(triggers, key=len, reverse=True):
                if text.startswith(trigger):
                    matched_trigger = trigger
                    break
            
            if not matched_trigger:
                continue

            raw_query = text[len(matched_trigger):].strip()
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
