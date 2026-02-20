"""
VARNA v1.5 — Voice-Activated Resource & Navigation Assistant
Main entry point.

Pipeline:
  🎤 Always Listening  →  🧹 NLP Clean  →  🧠 Parser  →  🛡 Whitelist
  →  ⚡ Executor / Window Manager / AppManager / PyAutoGUI  →  🔊 TTS Response

v1.5 additions:
  • Universal App Manager (open/close ANY installed app)
  • App scanning & indexing (Start Menu, Program Files, UWP)
  • Dynamic close via psutil
  • All v1.4 features (window, typing, tabs, NLP, search, chains)
"""

import sys
import os
import re
import time
from listener import Listener
from parser import Parser, ParseResult
from executor import Executor
from speaker import Speaker
from context import SessionContext
from monitor import ProcessMonitor
from macros import MacroManager
from tray import TrayUI
from window_manager import WindowManager, set_app_manager
from app_manager import AppManager
from utils.logger import get_logger

log = get_logger("VARNA")

VERSION = "1.5"

EXIT_PHRASES = {"exit", "quit", "stop", "goodbye", "bye", "shut up", "stop listening"}

# Try to import pyautogui
try:
    import pyautogui
    pyautogui.FAILSAFE = False
    _HAS_AUTO = True
except ImportError:
    _HAS_AUTO = False
    log.warning("pyautogui not installed — typing/tab/search features disabled.")


def main() -> None:
    """Run the VARNA assistant loop."""

    log.info("=" * 60)
    log.info("VARNA v%s starting up …", VERSION)
    log.info("=" * 60)

    # --- Initialise components -------------------------------------------
    try:
        speaker = Speaker(rate=170, volume=1.0)
        listener = Listener()
        parser = Parser()
        executor = Executor()
        context = SessionContext()
        monitor = ProcessMonitor(speaker=speaker)
        macros = MacroManager()
        tray = TrayUI()
        win_mgr = WindowManager()
        app_mgr = AppManager(auto_scan=True)  # v1.5: scan installed apps
        set_app_manager(app_mgr)  # Wire into WindowManager
    except Exception as exc:
        log.critical("Initialisation failed: %s", exc)
        print(f"\n[FATAL] {exc}")
        sys.exit(1)

    # --- Start tray UI ---------------------------------------------------
    tray.start()

    # --- Calibrate mic ---------------------------------------------------
    speaker.say("Calibrating microphone. Please wait.")
    listener.calibrate(duration=2.0)

    # --- Greet -----------------------------------------------------------
    speaker.greet()
    tray.update_result("✅ Ready")

    # --- Main loop -------------------------------------------------------
    log.info("Entering main loop.")
    print(f"\n🎤  VARNA v{VERSION} is listening. Say a command (or 'exit' to quit).\n")

    while True:
        tray.update_status("🎤 Listening …")
        text = listener.listen(timeout=7, phrase_time_limit=10)

        if text is None:
            continue

        tray.update_status("🧠 Processing …")
        tray.update_speech(text)
        print(f'   You said: "{text}"')

        # Exit
        if text in EXIT_PHRASES:
            log.info("Exit phrase detected: '%s'", text)
            if monitor.is_running:
                monitor.stop()
            tray.update_result("👋 Shutting down …")
            speaker.goodbye()
            tray.stop()
            break

        # Help
        if text in {"help", "list commands", "what can you do"}:
            cmds = parser.list_commands()
            summary = ", ".join(cmds[:10])
            speaker.say(f"I can do things like: {summary}, and more.")
            tray.update_command("help")
            continue

        if text in {"developer commands", "dev commands", "dev help"}:
            dev_cmds = parser.list_developer_commands()
            summary = ", ".join(dev_cmds[:8])
            speaker.say(f"Developer commands include: {summary}.")
            tray.update_command("dev help")
            continue

        # v1.4 — Multi-command natural chain: split by " and " / " then "
        # Only if the text contains " and " and isn't a known chain/macro-record
        if _should_split(text):
            parts = re.split(r"\s+and\s+|\s+then\s+", text)
            if len(parts) > 1:
                log.info("Natural chain detected: %d parts", len(parts))
                speaker.say(f"Running {len(parts)} commands.")
                tray.update_command(f"chain: {len(parts)} commands")

                for i, part in enumerate(parts, 1):
                    part = part.strip()
                    if not part:
                        continue
                    print(f"   ⛓ Step {i}: {part}")
                    _process_single(part, parser, executor, context, monitor,
                                    macros, win_mgr, app_mgr, speaker, tray, listener)
                    time.sleep(0.8)  # Small delay between steps
                continue

        # Single command
        _process_single(text, parser, executor, context, monitor,
                        macros, win_mgr, app_mgr, speaker, tray, listener)

    log.info("VARNA v%s shut down cleanly.", VERSION)
    print(f"\n👋  VARNA v{VERSION} has shut down.\n")


# ====================================================================== #
def _should_split(text: str) -> bool:
    """Check if text should be split into multiple commands."""
    # Don't split macro recordings
    if text.startswith(("whenever i say", "when i say", "create macro", "save macro")):
        return False
    # Don't split known chain commands
    if "and my react project" in text:
        return False
    # Split if contains " and " or " then "
    return bool(re.search(r"\s+and\s+|\s+then\s+", text))


# ====================================================================== #
def _process_single(text: str, parser: Parser, executor: Executor,
                    context: SessionContext, monitor: ProcessMonitor,
                    macros: MacroManager, win_mgr: WindowManager,
                    app_mgr: AppManager,
                    speaker: Speaker, tray: TrayUI, listener: Listener) -> None:
    """Process a single command."""

    result: ParseResult = parser.parse(text, context=context, macro_manager=macros)

    if not result.matched:
        speaker.say(f"Sorry, I don't recognise the command: {text}")
        tray.update_result(f"❌ Unknown: {text}")
        return

    tray.update_command(result.matched_key or text)

    # --- Info response ---
    if result.is_info:
        speaker.say(result.info_text or "No information available.")
        tray.update_result("ℹ️ Info")
        return

    # --- Clipboard ---
    if result.is_clipboard:
        _handle_clipboard(speaker, tray)
        return

    # --- Tab control (v1.4) ---
    if result.is_tab:
        _handle_tab(result, speaker, tray)
        return

    # --- App scan / list (v1.5) ---
    if result.is_app_scan:
        _handle_app_scan(result, app_mgr, speaker, tray)
        return

    # --- Dynamic close (v1.5) ---
    if result.is_dynamic_close:
        _handle_dynamic_close(result, app_mgr, speaker, tray)
        return

    # --- Window intelligence (v1.4 + v1.5 AppManager fallback) ---
    if result.is_window:
        _handle_window(result, win_mgr, context, speaker, tray)
        return

    # --- Voice typing (v1.4) ---
    if result.is_typing:
        _handle_typing(result, speaker, tray)
        return

    # --- Key press (v1.5 polish) ---
    if result.is_key_press:
        _handle_key_press(result, speaker, tray)
        return

    # --- Text selection (v1.5 polish) ---
    if result.is_selection:
        _handle_selection(result, speaker, tray)
        return

    # --- Scrolling (v1.5 polish) ---
    if result.is_scroll:
        _handle_scroll(result, speaker, tray)
        return

    # --- Browser/Explorer navigation (v1.5 polish) ---
    if result.is_navigation:
        _handle_navigation(result, speaker, tray)
        return

    # --- Search result click (v1.5 polish) ---
    if result.is_result_click:
        _handle_result_click(result, speaker, tray)
        return

    # --- Clipboard history (v1.5 polish) ---
    if result.is_clipboard_history:
        _handle_clipboard_history(result, speaker, tray)
        return

    # --- WhatsApp navigation (v1.5) ---
    if result.is_whatsapp:
        _handle_whatsapp(result, speaker, tray)
        return

    # --- Monitor ---
    if result.is_monitor:
        _handle_monitor(result, monitor, speaker, tray)
        return

    # --- Smart Screenshot ---
    if result.is_screenshot:
        _handle_screenshot(result, executor, speaker, tray)
        return

    # --- File Search ---
    if result.is_file_search:
        _handle_file_search(result, executor, speaker, tray)
        return

    # --- Macros ---
    if result.is_macro:
        _handle_macro(result, macros, parser, executor, context, speaker, tray)
        return

    # --- Confirmation layer ---
    if result.needs_confirmation:
        speaker.say(f"Are you sure you want to {result.matched_key}?")
        print(f"   ⚠️  Dangerous: {result.matched_key}")
        tray.update_result("⚠️ Confirm?")

        confirmed = listener.ask_yes_no(timeout=6)
        if confirmed is True:
            speaker.say("Confirmed.")
        elif confirmed is False:
            speaker.say("Cancelled.")
            tray.update_result("🚫 Cancelled")
            return
        else:
            speaker.say("No response. Cancelled for safety.")
            tray.update_result("⏰ Timed out")
            return

    # --- Smart search routing (v1.4) ---
    if result.is_in_tab_search and result.search_query:
        if _try_in_tab_search(result.search_query, win_mgr, speaker, tray):
            context.update_after_command(result.matched_key, result.commands[0] if result.commands else "")
            return
        # Fall through to normal execution if browser isn't active

    # --- Execute (chain or single) ---
    if result.is_chain:
        speaker.say(f"Running chain: {result.matched_key}")
        success, output = executor.run_chain(result.commands)
        if success:
            context.update_after_command(result.matched_key, result.commands[-1])
            tray.update_result("✅ Chain done")
            if output and output != "All steps completed successfully.":
                print(f"   📋 Output:\n{output[:300]}\n")
                speaker.say("Chain completed. Here is the output.")
            else:
                speaker.say("Chain completed.")
        else:
            speaker.say(f"Chain failed: {output}")
            tray.update_result(f"❌ Failed")
    else:
        ps_command = result.commands[0]
        speaker.say(f"Running: {result.matched_key}")

        success, output = executor.run(ps_command)
        if success:
            context.update_after_command(result.matched_key, ps_command)
            tray.update_result("✅ Done")
            if output and output != "Command executed successfully.":
                print(f"   📋 Output:\n{output[:300]}\n")
                speaker.say("Done. Here is the output.")
            else:
                speaker.say("Done.")
        else:
            speaker.say(f"Something went wrong: {output}")
            tray.update_result(f"❌ Error")


# ====================================================================== #
# Utility functions
# ====================================================================== #

# Spoken punctuation/symbol → actual character
_SYMBOL_MAP = {
    "question mark": "?",
    "exclamation mark": "!",
    "exclamation point": "!",
    "period": ".",
    "full stop": ".",
    "comma": ",",
    "colon": ":",
    "semicolon": ";",
    "at the rate": "@",
    "at sign": "@",
    "at": "@",
    "hash": "#",
    "hashtag": "#",
    "dollar sign": "$",
    "dollar": "$",
    "percent": "%",
    "percent sign": "%",
    "ampersand": "&",
    "and sign": "&",
    "asterisk": "*",
    "star": "*",
    "plus sign": "+",
    "plus": "+",
    "minus sign": "-",
    "minus": "-",
    "equals sign": "=",
    "equals": "=",
    "underscore": "_",
    "hyphen": "-",
    "dash": "-",
    "slash": "/",
    "forward slash": "/",
    "backslash": "\\",
    "open parenthesis": "(",
    "close parenthesis": ")",
    "open bracket": "[",
    "close bracket": "]",
    "open brace": "{",
    "close brace": "}",
    "double quote": '"',
    "single quote": "'",
    "apostrophe": "'",
    "tilde": "~",
    "pipe": "|",
    "greater than": ">",
    "less than": "<",
    "new line": "\n",
    "enter key": "\n",
    "tab key": "\t",
    "space": " ",
    # Multi-character symbols
    "three periods": "...",
    "triple dot": "...",
    "triple dots": "...",
    "dot dot dot": "...",
    "ellipsis": "...",
    "three dots": "...",
}

# Punctuation characters that should NOT have a leading space
_NO_SPACE_BEFORE = set(".,!?;:)]}\"'>…")


def _replace_symbols(text: str) -> str:
    """Replace spoken punctuation/symbol names with actual characters."""
    # Sort by length (longest first) to match "exclamation mark" before "mark"
    for name in sorted(_SYMBOL_MAP.keys(), key=len, reverse=True):
        if name in text.lower():
            text = re.sub(re.escape(name), _SYMBOL_MAP[name], text, flags=re.IGNORECASE)

    # Handle number + symbol patterns like "3 periods" → "...", "2 exclamation marks" → "!!"
    def _expand_number(m):
        count = int(m.group(1))
        sym = m.group(2).rstrip("s")  # remove trailing 's'
        char = _SYMBOL_MAP.get(sym, _SYMBOL_MAP.get(sym + " mark", sym))
        return char * min(count, 10)  # cap at 10 to be safe

    text = re.sub(
        r"(\d+)\s+(period|dot|exclamation mark|exclamation|question mark|question|hash|star|asterisk|dash|hyphen|underscore)s?",
        _expand_number, text, flags=re.IGNORECASE
    )

    return text.strip()


def _is_only_punctuation(text: str) -> bool:
    """Check if text is purely punctuation/symbols (no letters or digits)."""
    return bool(text) and all(not c.isalnum() and not c.isspace() for c in text)


# ====================================================================== #
# Handler functions
# ====================================================================== #

def _handle_app_scan(result: ParseResult, app_mgr: AppManager,
                     speaker: Speaker, tray: TrayUI):
    """Handle scan / list installed apps commands."""
    if result.app_scan_action == "scan":
        speaker.say("Scanning installed applications. This may take a moment.")
        tray.update_result("🔍 Scanning …")
        count = app_mgr.scan()
        speaker.say(f"Scan complete. Found {count} applications.")
        tray.update_result(f"📦 {count} apps indexed")
    elif result.app_scan_action == "list":
        apps = app_mgr.list_apps()
        if apps:
            # Show first 10
            shown = apps[:10]
            more = len(apps) - 10 if len(apps) > 10 else 0
            names = ", ".join(shown)
            print(f"   📦 Installed apps ({len(apps)} total): {names}{'...' if more else ''}")
            speaker.say(f"You have {len(apps)} apps indexed. Some include: {names}.")
            tray.update_result(f"📦 {len(apps)} apps")
        else:
            speaker.say("No apps indexed yet. Say 'scan apps' to build the list.")
            tray.update_result("📦 No apps")


def _handle_dynamic_close(result: ParseResult, app_mgr: AppManager,
                          speaker: Speaker, tray: TrayUI):
    """Close any running application dynamically via psutil."""
    target = result.close_target
    if not target:
        speaker.say("Which application should I close?")
        return

    msg = app_mgr.close(target)
    speaker.say(msg)
    if "not running" in msg.lower():
        tray.update_result(f"❌ {target} not running")
    else:
        tray.update_result(f"🚫 Closed {target}")


def _handle_window(result: ParseResult, win_mgr: WindowManager,
                   context: SessionContext, speaker: Speaker, tray: TrayUI):
    """Handle window intelligence commands."""
    action = result.window_action
    target = result.window_target

    if action == "show_desktop":
        msg = win_mgr.show_desktop()
        speaker.say(msg)
        tray.update_result("🖥 Desktop")
        return

    if action == "restore_last":
        if context.last_app:
            msg = win_mgr.restore(context.last_app)
            speaker.say(msg)
            tray.update_result(f"🪟 Restored {context.last_app}")
        else:
            speaker.say("No last window to restore.")
            tray.update_result("❌ No last window")
        return

    if not target:
        speaker.say("Which application?")
        return

    if action == "smart_open":
        act, msg = win_mgr.smart_open(target)
        if act == "suggest":
            # Multiple similar apps found — ask user to be specific
            speaker.say(f"I found similar apps: {msg}. Which one did you mean?")
            tray.update_result(f"❓ Similar: {msg}")
            return
        if act == "not_found":
            speaker.say(msg)
            tray.update_result(f"❌ {target} not found")
            return
        speaker.say(msg)
        context.update_after_command(f"open {target}", f"Start-Process {target}")
        tray.update_result(f"🪟 {act}: {target}")

    elif action == "open_new":
        act, msg = win_mgr.smart_open_new(target)
        speaker.say(msg)
        context.update_after_command(f"open {target}", f"Start-Process {target}")
        tray.update_result(f"🪟 New: {target}")

    elif action == "minimize":
        msg = win_mgr.minimize(target)
        speaker.say(msg)
        tray.update_result(f"🪟 Minimized {target}")

    elif action == "maximize":
        msg = win_mgr.maximize(target)
        speaker.say(msg)
        tray.update_result(f"🪟 Maximized {target}")

    elif action == "restore":
        msg = win_mgr.restore(target)
        speaker.say(msg)
        tray.update_result(f"🪟 Restored {target}")

    elif action == "switch":
        msg = win_mgr.switch_to(target)
        speaker.say(msg)
        context.update_after_command(f"switch to {target}", "")
        tray.update_result(f"🪟 Switched to {target}")


def _handle_tab(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Handle tab control commands via keyboard shortcuts."""
    if not _HAS_AUTO:
        speaker.say("Tab control requires pyautogui. Install it with pip install pyautogui.")
        return

    action = result.tab_action
    tab_shortcuts = {
        "close": ("ctrl", "w"),
        "new": ("ctrl", "t"),
        "next": ("ctrl", "Tab"),
        "prev": ("ctrl", "shift", "Tab"),
        "reopen": ("ctrl", "shift", "t"),
    }

    # Numbered tab: Ctrl+N
    if action == "numbered" and result.tab_number:
        n = result.tab_number
        pyautogui.hotkey("ctrl", str(n))
        msg = f"Switched to tab {n}"
        speaker.say(msg)
        tray.update_result(f"📑 {msg}")
        log.info("Tab action: go to tab %d", n)
        return

    shortcut = tab_shortcuts.get(action)
    if shortcut:
        pyautogui.hotkey(*shortcut)
        action_labels = {
            "close": "Closed tab", "new": "Opened new tab",
            "next": "Switched to next tab", "prev": "Switched to previous tab",
            "reopen": "Reopened last tab",
        }
        msg = action_labels.get(action, "Tab action done")
        speaker.say(msg)
        tray.update_result(f"📑 {msg}")
        log.info("Tab action: %s → %s", action, shortcut)


def _handle_typing(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Type text into the active window with smart spacing."""
    if not _HAS_AUTO:
        speaker.say("Voice typing requires pyautogui. Install it with pip install pyautogui.")
        return

    text = result.typing_text
    if text:
        # Map spoken punctuation/symbol names to actual characters
        text = _replace_symbols(text)

        speaker.say(f"Typing: {text}")
        time.sleep(0.5)  # Small delay to let TTS finish before typing

        # Smart spacing: only add a leading space if text starts with words, not punctuation
        if _is_only_punctuation(text) or (text and text[0] in _NO_SPACE_BEFORE):
            # Pure punctuation like "?" or "..." — stick to previous word
            pyautogui.write(text, interval=0.03)
        else:
            # Normal words — add a leading space to separate from previous text
            pyautogui.press("space")
            pyautogui.write(text, interval=0.03)

        log.info("Typed: '%s'", text)
        tray.update_result(f"⌨️ Typed: {text[:30]}")


def _handle_key_press(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Press a keyboard key or hotkey combo."""
    if not _HAS_AUTO:
        speaker.say("Key press requires pyautogui.")
        return

    key = result.key_name
    if not key:
        return

    # Hotkey combos
    hotkey_map = {
        "select_all": ("ctrl", "a"),
        "undo": ("ctrl", "z"),
        "redo": ("ctrl", "y"),
        "copy": ("ctrl", "c"),
        "paste": ("ctrl", "v"),
        "cut": ("ctrl", "x"),
    }

    if key in hotkey_map:
        pyautogui.hotkey(*hotkey_map[key])
    else:
        pyautogui.press(key)

    key_labels = {
        "enter": "Pressed Enter",
        "escape": "Pressed Escape",
        "tab": "Pressed Tab",
        "backspace": "Pressed Backspace",
        "delete": "Pressed Delete",
        "select_all": "Selected all",
        "undo": "Undo",
        "redo": "Redo",
        "copy": "Copied",
        "paste": "Pasted",
        "cut": "Cut",
    }
    msg = key_labels.get(key, f"Pressed {key}")
    speaker.say(msg)
    tray.update_result(f"⌨️ {msg}")
    log.info("Key press: %s", key)


def _handle_selection(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Handle text selection commands using keyboard shortcuts."""
    if not _HAS_AUTO:
        speaker.say("Text selection requires pyautogui.")
        return

    action = result.selection_action

    if action == "select_line":
        pyautogui.press("home")
        time.sleep(0.05)
        pyautogui.hotkey("shift", "end")
        speaker.say("Selected line")
        tray.update_result("📝 Selected line")

    elif action == "select_word":
        # Double-click selects word in most editors; keyboard alternative:
        pyautogui.hotkey("ctrl", "shift", "left")
        speaker.say("Selected word")
        tray.update_result("📝 Selected word")

    elif action == "select_next":
        count = result.selection_count
        for _ in range(count):
            pyautogui.hotkey("ctrl", "shift", "right")
            time.sleep(0.05)
        speaker.say(f"Selected next {count} words")
        tray.update_result(f"📝 Selected next {count} words")

    elif action == "select_prev":
        count = result.selection_count
        for _ in range(count):
            pyautogui.hotkey("ctrl", "shift", "left")
            time.sleep(0.05)
        speaker.say(f"Selected previous {count} words")
        tray.update_result(f"📝 Selected prev {count} words")

    elif action == "go_to_line":
        line_num = result.selection_target
        # Ctrl+G works in Notepad, VS Code, most editors
        pyautogui.hotkey("ctrl", "g")
        time.sleep(0.3)
        pyautogui.typewrite(str(line_num), interval=0.03)
        time.sleep(0.1)
        pyautogui.press("enter")
        speaker.say(f"Jumped to line {line_num}")
        tray.update_result(f"📝 Go to line {line_num}")

    elif action == "select_word_name":
        target = result.selection_target
        # Use Ctrl+F (Find) to locate the word, which highlights it
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.3)
        # Clear any existing search text
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.05)
        pyautogui.typewrite(target, interval=0.03)
        time.sleep(0.1)
        pyautogui.press("enter")  # Find next — highlights the match
        time.sleep(0.1)
        pyautogui.press("escape")  # Close find dialog — selection stays
        speaker.say(f"Selected {target}")
        tray.update_result(f"📝 Selected: {target}")

    log.info("Selection: %s", action)


def _handle_scroll(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Handle scroll commands with sensitivity."""
    if not _HAS_AUTO:
        speaker.say("Scrolling requires pyautogui.")
        return

    special = result.scroll_special
    if special:
        if special == "top":
            pyautogui.hotkey("ctrl", "Home")
            msg = "Scrolled to top"
        elif special == "bottom":
            pyautogui.hotkey("ctrl", "End")
            msg = "Scrolled to bottom"
        elif special == "page_down":
            pyautogui.press("pagedown")
            msg = "Page down"
        elif special == "page_up":
            pyautogui.press("pageup")
            msg = "Page up"
        else:
            msg = "Scrolled"
        speaker.say(msg)
        tray.update_result(f"📜 {msg}")
        log.info("Scroll special: %s", special)
        return

    direction = result.scroll_direction
    amount = result.scroll_amount

    # pyautogui.scroll: positive = up, negative = down
    clicks = amount if direction == "up" else -amount
    pyautogui.scroll(clicks)

    sensitivity = "a little" if amount <= 2 else ("a lot" if amount >= 15 else "")
    msg = f"Scrolled {sensitivity} {direction}".strip()
    msg = " ".join(msg.split())  # clean double spaces
    speaker.say(msg)
    tray.update_result(f"📜 {msg}")
    log.info("Scroll: %s %d clicks", direction, amount)


def _handle_navigation(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Handle browser / file explorer navigation including drives and folders."""
    if not _HAS_AUTO:
        speaker.say("Navigation requires pyautogui.")
        return

    action = result.nav_action

    # Keyboard shortcut-based navigation
    nav_shortcuts = {
        "back": (("alt", "left"), "Went back"),
        "forward": (("alt", "right"), "Went forward"),
        "refresh": (("F5",), "Refreshed page"),
        "address_bar": (("ctrl", "l"), "Focused address bar"),
    }

    shortcut_info = nav_shortcuts.get(action)
    if shortcut_info:
        keys, msg = shortcut_info
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        speaker.say(msg)
        tray.update_result(f"🧭 {msg}")
        log.info("Navigation: %s", action)
        return

    # Drive navigation: open D:\, E:\, etc.
    if action == "drive":
        target = result.nav_target  # e.g. "D:\\"
        drive_letter = target[0]
        import os
        if os.path.exists(target):
            import subprocess as _sp
            _sp.Popen(["explorer.exe", target])
            speaker.say(f"Opened {drive_letter} drive")
            tray.update_result(f"📂 {drive_letter}: drive")
            log.info("Navigation: opened drive %s", target)
        else:
            speaker.say(f"Drive {drive_letter} not found")
            tray.update_result(f"❌ Drive {drive_letter} not found")
        return

    # This PC
    if action == "this_pc":
        import subprocess as _sp
        _sp.Popen(["explorer.exe", "shell:MyComputerFolder"])
        speaker.say("Opened This PC")
        tray.update_result("📂 This PC")
        log.info("Navigation: This PC")
        return

    # Known folders: Desktop, Downloads, Documents, etc.
    if action == "known_folder":
        import os, subprocess as _sp
        folder_name = result.nav_target  # e.g. "Downloads"
        folder_path = os.path.join(os.path.expanduser("~"), folder_name)
        if os.path.exists(folder_path):
            _sp.Popen(["explorer.exe", folder_path])
            speaker.say(f"Opened {folder_name}")
            tray.update_result(f"📂 {folder_name}")
            log.info("Navigation: opened %s", folder_path)
        else:
            speaker.say(f"{folder_name} folder not found")
            tray.update_result(f"❌ {folder_name} not found")
        return


def _handle_result_click(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Open a search result by number using Tab navigation."""
    if not _HAS_AUTO:
        speaker.say("Result clicking requires pyautogui.")
        return

    n = result.result_number
    # In Google search results, Tab navigates through links.
    # We press Tab multiple times to reach the Nth result, then Enter.
    # First, focus on the page body (click somewhere neutral)
    speaker.say(f"Opening result {n}")
    time.sleep(0.3)

    # Press Tab to navigate through results
    tab_count = n * 2 + 3  # approximate: skip nav elements, reach Nth result
    for i in range(tab_count):
        pyautogui.press("tab")
        time.sleep(0.08)

    pyautogui.press("enter")
    tray.update_result(f"🔍 Opened result {n}")
    log.info("Result click: #%d (tabbed %d times)", n, tab_count)


def _handle_clipboard_history(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Handle clipboard history commands (Win+V)."""
    if not _HAS_AUTO:
        speaker.say("Clipboard history requires pyautogui.")
        return

    action = result.clipboard_action

    if action == "open":
        pyautogui.hotkey("win", "v")
        speaker.say("Opened clipboard history")
        tray.update_result("📋 Clipboard history")
        log.info("Clipboard: opened history")

    elif action == "paste_nth":
        n = result.clipboard_index
        # Open clipboard history
        pyautogui.hotkey("win", "v")
        time.sleep(0.5)  # Wait for clipboard panel to appear

        # Navigate down to the Nth item (first item is already selected)
        for _ in range(n - 1):
            pyautogui.press("down")
            time.sleep(0.1)

        # Press Enter to paste the selected item
        pyautogui.press("enter")
        speaker.say(f"Pasted item {n}")
        tray.update_result(f"📋 Pasted item {n}")
        log.info("Clipboard: pasted item #%d", n)


def _handle_whatsapp(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Handle WhatsApp Desktop navigation using keyboard shortcuts."""
    if not _HAS_AUTO:
        speaker.say("WhatsApp navigation requires pyautogui.")
        return

    action = result.whatsapp_action

    if action == "open_chat":
        n = result.chat_number
        # Navigate to the chat list area and select Nth chat
        # In WhatsApp Desktop: Alt+F4 to ensure focus, then use arrow keys
        # First, press Escape to clear any open dialog/search
        pyautogui.press("escape")
        time.sleep(0.2)

        # Press Ctrl+F to focus search, then Escape to focus chat list
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.2)
        pyautogui.press("escape")
        time.sleep(0.2)

        # Now press Down arrow N times to reach Nth chat, then Enter
        for i in range(n):
            pyautogui.press("down")
            time.sleep(0.1)
        pyautogui.press("enter")

        speaker.say(f"Opened chat {n}")
        tray.update_result(f"💬 Opened chat {n}")
        log.info("WhatsApp: opened chat #%d", n)

    elif action == "search_contact":
        contact = result.whatsapp_target
        # Ctrl+K opens WhatsApp search / new chat search
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.5)
        pyautogui.typewrite(contact, interval=0.04)
        time.sleep(0.8)  # Wait for search results to appear
        pyautogui.press("enter")  # Open the first matching contact

        speaker.say(f"Opening chat with {contact}")
        tray.update_result(f"💬 Chat: {contact}")
        log.info("WhatsApp: searched contact '%s'", contact)

    elif action == "new_chat":
        pyautogui.hotkey("ctrl", "n")
        speaker.say("Starting new chat")
        tray.update_result("💬 New chat")
        log.info("WhatsApp: new chat")


def _try_in_tab_search(query: str, win_mgr: WindowManager,
                       speaker: Speaker, tray: TrayUI) -> bool:
    """
    If a browser is currently active, search in the current tab
    using Ctrl+L → type → Enter. Returns True if handled.
    """
    if not _HAS_AUTO:
        return False

    browser = win_mgr.is_browser_active()
    if not browser:
        return False

    log.info("Smart search: browser '%s' is active — searching in current tab.", browser)
    speaker.say(f"Searching in current tab: {query}")
    tray.update_result(f"🔍 In-tab search")

    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "l")  # Focus address bar
    time.sleep(0.3)
    pyautogui.write(query, interval=0.02)
    time.sleep(0.1)
    pyautogui.press("enter")

    return True


def _handle_clipboard(speaker: Speaker, tray: TrayUI):
    """Read clipboard and speak contents."""
    try:
        import pyperclip
        content = pyperclip.paste()
        if content and content.strip():
            print(f"   📋 Clipboard:\n{content[:500]}\n")
            speaker.say(f"Your clipboard contains: {content[:200]}")
            tray.update_result("📋 Clipboard read")
        else:
            speaker.say("Your clipboard is empty.")
            tray.update_result("📋 Empty")
    except ImportError:
        speaker.say("Clipboard requires pyperclip. Install with pip install pyperclip.")
    except Exception as exc:
        speaker.say(f"Could not read clipboard: {exc}")


def _handle_screenshot(result: ParseResult, executor: Executor,
                       speaker: Speaker, tray: TrayUI):
    """Smart screenshot with custom filename."""
    name = result.screenshot_name or "screenshot"
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    filepath = os.path.join(desktop, f"{name}.png")

    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.Screen]::PrimaryScreen | ForEach-Object { "
        "$bitmap = New-Object System.Drawing.Bitmap($_.Bounds.Width, $_.Bounds.Height); "
        "$graphics = [System.Drawing.Graphics]::FromImage($bitmap); "
        "$graphics.CopyFromScreen($_.Bounds.Location, [System.Drawing.Point]::Empty, $_.Bounds.Size); "
        f"$bitmap.Save('{filepath}'); "
        f"Write-Output 'Screenshot saved to {filepath}' "
        "}"
    )

    speaker.say(f"Taking screenshot as {name}")
    success, output = executor.run(ps_cmd)
    if success:
        speaker.say(f"Screenshot saved as {name} on your desktop.")
        tray.update_result(f"📸 {name}.png")
    else:
        speaker.say(f"Screenshot failed: {output}")


def _handle_file_search(result: ParseResult, executor: Executor,
                        speaker: Speaker, tray: TrayUI):
    """Search for files by natural description."""
    query = result.file_search_query or ""

    ext_filter = "*"
    for ext in ["pdf", "doc", "docx", "txt", "xlsx", "pptx", "png", "jpg", "mp4", "zip", "py", "js", "html", "css"]:
        if ext in query.lower():
            ext_filter = f"*.{ext}"
            query = query.lower().replace(ext, "").strip()
            break

    time_filter = ""
    if "yesterday" in query:
        time_filter = "| Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-1) }"
        query = query.replace("yesterday", "").strip()
    elif "today" in query:
        time_filter = "| Where-Object { $_.LastWriteTime -gt (Get-Date).Date }"
        query = query.replace("today", "").strip()
    elif "this week" in query:
        time_filter = "| Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-7) }"
        query = query.replace("this week", "").strip()

    name_filter = f"*{query}*" if query else ext_filter
    search_paths = ["$env:USERPROFILE\\Desktop", "$env:USERPROFILE\\Downloads", "$env:USERPROFILE\\Documents"]
    ps_cmd = "; ".join([
        f"Get-ChildItem -Path {p} -Filter '{name_filter}' -Recurse -ErrorAction SilentlyContinue {time_filter} "
        f"| Select-Object Name, Length, LastWriteTime, FullName | Format-Table -AutoSize"
        for p in search_paths
    ])

    speaker.say(f"Searching for {result.file_search_query}")
    tray.update_result("🔍 Searching …")
    success, output = executor.run(ps_cmd)

    if success and output and output.strip() and output.strip() != "Command executed successfully.":
        print(f"   🔍 Results:\n{output[:500]}\n")
        lines = [l for l in output.strip().split("\n") if l.strip() and not l.startswith("-") and not l.startswith("Name")]
        speaker.say(f"Found {len(lines)} files. Check the console.")
        tray.update_result(f"🔍 {len(lines)} files")
    else:
        speaker.say("No files found.")
        tray.update_result("🔍 No results")


def _handle_macro(result: ParseResult, macros: MacroManager, parser: Parser,
                  executor: Executor, context: SessionContext,
                  speaker: Speaker, tray: TrayUI):
    """Handle macro record / play / list / delete."""
    if result.macro_action == "list":
        names = macros.list_all()
        if names:
            speaker.say(f"Your macros are: {', '.join(names)}")
            tray.update_result(f"🔁 {len(names)} macros")
        else:
            speaker.say("No macros saved yet.")
            tray.update_result("🔁 None")

    elif result.macro_action == "record" and result.macro_name:
        msg = macros.record(result.macro_name, result.macro_steps)
        speaker.say(msg)
        tray.update_result(f"🔁 Recorded: {result.macro_name}")

    elif result.macro_action == "delete" and result.macro_name:
        msg = macros.delete(result.macro_name)
        speaker.say(msg)
        tray.update_result(f"🗑 {result.macro_name}")

    elif result.macro_action == "play" and result.macro_name:
        steps = result.macro_steps
        if not steps:
            speaker.say(f"Macro {result.macro_name} has no steps.")
            return
        speaker.say(f"Running macro: {result.macro_name}")
        tray.update_result(f"🔁 Playing: {result.macro_name}")
        for i, step_name in enumerate(steps, 1):
            step_result = parser.parse(step_name, context=context)
            if step_result.matched and step_result.commands:
                for cmd in step_result.commands:
                    success, output = executor.run(cmd)
                    if success:
                        context.update_after_command(step_name, cmd)
                    else:
                        speaker.say(f"Step {i} failed: {output}")
                        return
            elif step_result.is_window:
                from window_manager import WindowManager
                wm = WindowManager()
                if step_result.window_action == "smart_open" and step_result.window_target:
                    wm.smart_open(step_result.window_target)
                    context.update_after_command(step_name, f"Start-Process {step_result.window_target}")
            else:
                speaker.say(f"Step {i} not recognised: {step_name}")
                return
            time.sleep(0.5)
        speaker.say(f"Macro {result.macro_name} completed.")
        tray.update_result(f"✅ Macro done")


def _handle_monitor(result: ParseResult, monitor: ProcessMonitor,
                    speaker: Speaker, tray: TrayUI):
    """Handle monitor commands."""
    if result.monitor_action == "start" and result.monitor_process:
        msg = monitor.start(result.monitor_process)
        speaker.say(msg)
        tray.update_result(f"📊 Monitoring: {result.monitor_process}")
    elif result.monitor_action == "stop":
        msg = monitor.stop()
        speaker.say(msg)
        tray.update_result("📊 Stopped")
    elif result.monitor_action == "check" and result.monitor_process:
        status = monitor.get_status(result.monitor_process)
        speaker.say(f"Here is the status of {result.monitor_process}." if "not running" not in status.lower()
                    else f"{result.monitor_process} is not running.")
        tray.update_result(f"📊 {result.monitor_process}")


# ====================================================================== #
if __name__ == "__main__":
    main()
