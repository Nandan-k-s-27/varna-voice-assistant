"""
VARNA v2.3 — Voice-Activated Resource & Navigation Assistant
Main entry point.

Pipeline:
  🎤 Always Listening  →  🧹 NLP Clean  →  🧠 Parser  →  🛡 Whitelist
  →  ⚡ Executor / Window Manager / AppManager / PyAutoGUI  →  🔊 TTS Response
"""

import sys
import os
import re
import time
import threading
import datetime
import platform
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

VERSION = "2.3"

EXIT_PHRASES = {
    "exit", "quit", "stop", "goodbye", "bye", "shut up", "stop listening",
    "that's all", "i'm done", "go to sleep", "shut down", "close varna",
}

# ====================================================================== #
# Conversational Query Handler — VARNA speaks answers directly
# ====================================================================== #

# Pre-built trigger sets (don't rebuild on every call)
_TIME_TRIGGERS = frozenset({
    "what time is it", "what time", "what is the time", "current time",
    "show time", "tell me time", "tell me the time", "time",
    "show me the time", "tell the time", "what's the time",
    "time please", "whats the time",
})
_DATE_TRIGGERS = frozenset({
    "what date is it", "what is the date", "current date", "today's date",
    "tell me date", "tell me the date", "show date", "date",
    "what is today", "what day is it", "today", "show me the date",
    "what's the date", "whats the date", "what day is today",
})
_DAY_TRIGGERS = frozenset({"what day", "which day", "what day of the week"})
_DATETIME_TRIGGERS = frozenset({
    "date and time", "time and date", "what is the date and time",
    "tell me date and time", "show date and time",
})
_BATTERY_TRIGGERS = frozenset({
    "battery", "battery level", "battery status", "check battery",
    "how much battery", "battery percentage", "battery life",
    "how much charge", "charge level", "power level",
})
_HOSTNAME_TRIGGERS = frozenset({
    "my hostname", "what is my hostname", "computer name",
    "what is my computer name", "my computer name", "pc name",
})
_USERNAME_TRIGGERS = frozenset({
    "my username", "who am i", "what is my username",
    "logged in user", "which user", "my user",
})
_GREETING_TRIGGERS = frozenset({
    "hello", "hi", "hey", "good morning", "good afternoon",
    "good evening", "hey varna", "hello varna", "hi varna",
})
_HOW_ARE_YOU_TRIGGERS = frozenset({
    "how are you", "how are you doing", "what's up", "whats up",
    "how do you do", "how is it going",
})
_THANKS_TRIGGERS = frozenset({
    "thank you", "thanks", "thanks varna", "thank you varna",
    "thank you so much", "thanks a lot",
})
_CAPABILITY_TRIGGERS = frozenset({
    "what can you do", "what do you do", "your capabilities",
    "what are your features",
})
_IDENTITY_TRIGGERS = frozenset({
    "who are you", "what is your name", "what's your name",
    "your name", "introduce yourself",
})
# Pre-compile the punctuation-stripping regex
_CONV_PUNCT_RE = re.compile(r'[.,!?;:…]+$|^[.,!?;:…]+')


def _handle_conversational(text: str, speaker, tray) -> bool:
    """
    Handle conversational/informational queries that VARNA should SPEAK
    directly instead of running in a terminal. Returns True if handled.
    """
    # Strip punctuation that Whisper/STT may add (periods, commas, question marks)
    t = _CONV_PUNCT_RE.sub('', text.lower().strip()).strip()

    # --- Time queries ---
    if t in _TIME_TRIGGERS:
        now = datetime.datetime.now()
        spoken_time = now.strftime("%I:%M %p").lstrip("0")
        speaker.say(f"The current time is {spoken_time}.")
        tray.update_result(f"🕐 {spoken_time}")
        log.info("Conversational: time → %s", spoken_time)
        return True

    # --- Date queries ---
    if t in _DATE_TRIGGERS:
        now = datetime.datetime.now()
        spoken_date = now.strftime("%A, %B %d, %Y")
        speaker.say(f"Today is {spoken_date}.")
        tray.update_result(f"📅 {spoken_date}")
        log.info("Conversational: date → %s", spoken_date)
        return True

    # --- Day of week ---
    if t in _DAY_TRIGGERS:
        day = datetime.datetime.now().strftime("%A")
        speaker.say(f"Today is {day}.")
        tray.update_result(f"📅 {day}")
        return True

    # --- Date and Time combined ---
    if t in _DATETIME_TRIGGERS:
        now = datetime.datetime.now()
        spoken = f"It's {now.strftime('%I:%M %p').lstrip('0')} on {now.strftime('%A, %B %d, %Y')}."
        speaker.say(spoken)
        tray.update_result(f"🕐📅 {now.strftime('%I:%M %p - %b %d')}")
        return True

    # --- Battery ---
    if t in _BATTERY_TRIGGERS:
        try:
            import psutil
            bat = psutil.sensors_battery()
            if bat:
                pct = bat.percent
                plugged = "and charging" if bat.power_plugged else "on battery"
                speaker.say(f"Battery is at {pct} percent, {plugged}.")
                tray.update_result(f"🔋 {pct}% {plugged}")
            else:
                speaker.say("I couldn't read the battery status. You might be on a desktop.")
                tray.update_result("🔋 N/A")
        except Exception:
            speaker.say("Battery information is not available.")
        return True

    # --- Hostname / Computer name ---
    if t in _HOSTNAME_TRIGGERS:
        name = platform.node()
        speaker.say(f"Your computer name is {name}.")
        tray.update_result(f"💻 {name}")
        return True

    # --- Username ---
    if t in _USERNAME_TRIGGERS:
        user = os.getlogin()
        speaker.say(f"You are logged in as {user}.")
        tray.update_result(f"👤 {user}")
        return True

    # --- Greetings ---
    if t in _GREETING_TRIGGERS:
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        speaker.say(f"{greeting}! How can I help you?")
        tray.update_result(f"👋 {greeting}")
        return True

    # --- How are you ---
    if t in _HOW_ARE_YOU_TRIGGERS:
        speaker.say("I'm doing great, thank you! Ready for your commands.")
        tray.update_result("😊 Doing great")
        return True

    # --- Thank you ---
    if t in _THANKS_TRIGGERS:
        speaker.say("You're welcome! Let me know if you need anything else.")
        tray.update_result("🙏 Welcome")
        return True

    # --- What can you do ---
    if t in _CAPABILITY_TRIGGERS:
        speaker.say("I can open apps, search the web, manage windows, type text, "
                     "tell you the time and date, check battery, control media, "
                     "and much more. Just say a command!")
        tray.update_result("ℹ️ Capabilities")
        return True

    # --- Who are you ---
    if t in _IDENTITY_TRIGGERS:
        speaker.say("I am VARNA, your Voice Activated Resource and Navigation Assistant.")
        tray.update_result("ℹ️ VARNA")
        return True

    return False


# Try to import pyautogui
try:
    import pyautogui
    pyautogui.FAILSAFE = False
    _HAS_AUTO = True
except ImportError:
    _HAS_AUTO = False
    log.warning("pyautogui not installed — typing/tab/search features disabled.")


# Thread-safe console printing
PRINT_LOCK = threading.Lock()

def main() -> None:
    """Run the VARNA assistant loop."""

    log.info("=" * 60)
    log.info("VARNA v%s starting up …", VERSION)
    log.info("=" * 60)

    # --- Initialise components -------------------------------------------
    try:
        speaker = Speaker(rate=190, volume=1.0)
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
    listener.calibrate(duration=1.5)

    # --- Greet -----------------------------------------------------------
    speaker.greet()
    tray.update_result("✅ Ready")

    # --- Main loop -------------------------------------------------------
    log.info("Entering main loop.")
    print(f"\n🎤  VARNA v{VERSION} is listening. Say a command (or 'exit' to quit).\n")

    while True:
        tray.update_status("🎤 Listening …")
        text = listener.listen(timeout=7, phrase_time_limit=12)

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
        if text in {"help", "list commands", "what can you do",
                     "what commands do you have", "show commands",
                     "commands", "what do you do"}:
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
                    try:
                        _process_single(part, parser, executor, context, monitor,
                                        macros, win_mgr, app_mgr, speaker, tray, listener)
                    except Exception as exc:
                        log.error("Error processing chain step '%s': %s", part, exc, exc_info=True)
                        speaker.say("Something went wrong with that step. Skipping.")
                    time.sleep(0.8)  # Small delay between steps
                continue

        # Single command
        try:
            _process_single(text, parser, executor, context, monitor,
                            macros, win_mgr, app_mgr, speaker, tray, listener)
        except Exception as exc:
            log.error("Error processing command '%s': %s", text, exc, exc_info=True)
            speaker.say("Sorry, something went wrong. Please try again.")
            tray.update_result(f"❌ Error: {type(exc).__name__}")

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
    # Don't split conversational queries
    if text in ("date and time", "time and date"):
        return False
    # Don't split typing commands (preserve "type X and Y")
    if text.startswith(("type ", "write ", "send ", "just type ")):
        return False
    # Split if contains " and " or " then "
    return bool(re.search(r"\s+and\s+|\s+then\s+", text))


# ====================================================================== #
def _process_single(text: str, parser: Parser, executor: Executor,
                    context: SessionContext, monitor: ProcessMonitor,
                    macros: MacroManager, win_mgr: WindowManager,
                    app_mgr: AppManager,
                    speaker: Speaker, tray: TrayUI, listener: Listener) -> None:
    """Process a single command with safety gates and voice interaction."""

    # --- v3.2: Conversational queries (time, date, greetings, etc.) ---
    # Handle these FIRST so VARNA speaks directly instead of running PS commands
    if _handle_conversational(text, speaker, tray):
        context.last_command_text = text
        return

    result: ParseResult = parser.parse(text, context=context, macro_manager=macros)

    # --- v2.0: Safety blocked --- 
    if result.safety_blocked:
        msg = result.voice_response or result.safety_reason or f"I couldn't match '{text}' confidently."
        speaker.say(msg)
        log.warning("Safety blocked: %s → %s", text, result.safety_reason)
        tray.update_result(f"🛡️ Blocked: {text}")
        return

    if not result.matched:
        # Voice interaction: tell the user clearly
        speaker.say(f"I didn't catch that. Could you repeat the command?")
        tray.update_result(f"❌ Unknown: {text}")
        return

    # --- v2.0: Voice confirmation for fuzzy/low-confidence matches ---
    if result.voice_response and result.needs_confirmation and not result.is_repeat:
        speaker.say(result.voice_response)
        tray.update_result(f"❓ Confirm: {result.matched_key}")
        print(f"   ❓ Confirm: {result.matched_key} (confidence: {result.match_confidence:.0%})")
        
        confirmed = listener.ask_yes_no(timeout=6)
        if confirmed is True:
            speaker.say("Confirmed.")
            result.needs_confirmation = False  # Already confirmed
        elif confirmed is False:
            speaker.say("Cancelled.")
            tray.update_result("🚫 Cancelled")
            return
        else:
            speaker.say("No response. Cancelled for safety.")
            tray.update_result("⏰ Timed out")
            return

    # v3.1: Log active app mode for debugging
    active_mode = _get_active_app()
    log.info("Active app mode: %s | Command: %s (confidence=%.2f method=%s)", 
             active_mode, result.matched_key or text, result.match_confidence, result.match_method)

    tray.update_command(result.matched_key or text)

    # --- Repeat / Do it again ---
    if result.is_repeat:
        if context.last_command_text:
            speaker.say("Repeating.")
            tray.update_command(f"repeat: {context.last_command_text}")
            _process_single(context.last_command_text, parser, executor, context,
                            monitor, macros, win_mgr, app_mgr, speaker, tray, listener)
        else:
            speaker.say("Nothing to repeat yet.")
            tray.update_result("❌ Nothing to repeat")
        return

    # Track last command for repeat (skip repeat itself)
    context.last_command_text = text

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

    # --- Diagnostics (v1.6 robustness) ---
    if result.is_diagnostics:
        _handle_diagnostics(speaker, context, win_mgr, app_mgr, tray)
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

        # Voice-reply commands: speak the PS output aloud (time, date, battery, wifi, etc.)
        if result.is_voice_reply:
            success, output = executor.run(ps_command)
            if success and output and output != "Command executed successfully.":
                # Clean up for speech (strip PS formatting noise)
                spoken = output.strip().replace('\r\n', ', ').replace('\n', ', ')
                # Truncate if too long for speech
                if len(spoken) > 400:
                    spoken = spoken[:400] + "... and more."
                log.info("Voice reply: %s → %s", result.matched_key, spoken[:100])
                speaker.say(spoken)
                tray.update_result(f"🗣️ {spoken[:50]}")
            elif success:
                speaker.say("Done, but no output was returned.")
                tray.update_result("✅ Done (no output)")
            else:
                speaker.say(f"Something went wrong: {output}")
                tray.update_result(f"❌ Error")
            context.update_after_command(result.matched_key, ps_command)
            return

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

# Pre-compile symbol replacement patterns at module load (v3.2 optimization)
_COMPILED_SYMBOL_PATTERNS = []
for _name in sorted(_SYMBOL_MAP.keys(), key=len, reverse=True):
    _pat = re.compile(r'\b' + re.escape(_name) + r'\b', flags=re.IGNORECASE)
    _COMPILED_SYMBOL_PATTERNS.append((_pat, _SYMBOL_MAP[_name]))

# Pre-compile the number+symbol expansion pattern
_NUMBER_SYMBOL_PATTERN = re.compile(
    r"(\d+)\s+(period|dot|exclamation mark|exclamation|question mark|question|hash|star|asterisk|dash|hyphen|underscore)s?",
    flags=re.IGNORECASE
)


def _replace_symbols(text: str) -> str:
    """Replace spoken punctuation/symbol names with actual characters."""
    for pattern, replacement in _COMPILED_SYMBOL_PATTERNS:
        if pattern.search(text):
            text = pattern.sub(replacement, text)

    # Handle number + symbol patterns like "3 periods" → "...", "2 exclamation marks" → "!!"
    def _expand_number(m):
        count = int(m.group(1))
        sym = m.group(2).rstrip("s")  # remove trailing 's'
        char = _SYMBOL_MAP.get(sym, _SYMBOL_MAP.get(sym + " mark", sym))
        return char * min(count, 10)  # cap at 10 to be safe

    text = _NUMBER_SYMBOL_PATTERN.sub(_expand_number, text)

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


def _handle_diagnostics(speaker: Speaker, context: SessionContext, 
                        win_mgr: WindowManager, app_mgr: AppManager, tray: TrayUI):
    """Run internal self-tests to verify system health."""
    speaker.say("Starting system diagnostics.")
    tray.update_status("🧠 Diagnostics ...")
    
    results = []
    
    # 1. Check Window Tracking
    active = context.get_active_window_title()
    if active:
        results.append("Window tracking OK")
    else:
        results.append("Window tracking WARNING (No active window found)")
        
    # 2. Check App Index
    count = app_mgr.count()
    if count > 0:
        results.append(f"App index OK ({count} apps)")
    else:
        results.append("App index EMPTY (Try saying 'scan apps')")
        
    # 3. Check Mic/Speaker (Implicitly working if we got here, but log it)
    results.append("Speaker/Parser OK")
    
    summary = ". ".join(results)
    log.info("DIAGNOSTICS: %s", summary)
    speaker.say(f"Diagnostics complete. {summary}")
    tray.update_result("✅ Diagnostics OK")
    tray.update_status("🎤 Listening ...")


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

    # v1.6: close/minimize/maximize THIS (foreground) window
    if action == "close_this":
        if _HAS_AUTO:
            title = context.get_active_window_title() or "window"
            pyautogui.hotkey("alt", "F4")
            speaker.say(f"Closed {title.split(' - ')[-1] if ' - ' in title else 'window'}")
            tray.update_result("🚫 Closed active window")
        else:
            speaker.say("Cannot close — pyautogui not available.")
        return

    if action == "minimize_this":
        if _HAS_AUTO:
            pyautogui.hotkey("win", "down")
            speaker.say("Minimized this window")
            tray.update_result("🪟 Minimized active")
        else:
            speaker.say("Cannot minimize — pyautogui not available.")
        return

    if action == "maximize_this":
        if _HAS_AUTO:
            pyautogui.hotkey("win", "up")
            speaker.say("Maximized this window")
            tray.update_result("🪟 Maximized active")
        else:
            speaker.say("Cannot maximize — pyautogui not available.")
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
    """Handle tab control commands via keyboard shortcuts with focus reset."""
    if not _HAS_AUTO:
        speaker.say("Tab control requires pyautogui. Install it with pip install pyautogui.")
        return

    # Focus reset: dismiss any popup before tab operation
    _focus_reset()

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
    """Type text into the active window with smart spacing and optional Enter press."""
    if not _HAS_AUTO:
        speaker.say("Voice typing requires pyautogui. Install it with pip install pyautogui.")
        return

    text = result.typing_text
    press_enter = getattr(result, 'typing_press_enter', True)
    if text:
        # Map spoken punctuation/symbol names to actual characters
        text = _replace_symbols(text)

        # Focus reset: ESC to dismiss any popup/find bar before typing
        _focus_reset()

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

        # Press Enter after typing (useful for ChatGPT, search boxes, etc.)
        if press_enter:
            time.sleep(0.2)
            pyautogui.press("enter")
            log.info("Typed + Enter: '%s'", text)
            tray.update_result(f"⌨️ Sent: {text[:30]}")
        else:
            log.info("Typed: '%s'", text)
            tray.update_result(f"⌨️ Typed: {text[:30]}")


def _get_active_app() -> str:
    """Detect the active foreground application category.
    Returns: 'browser', 'editor', 'explorer', 'terminal', 'unknown'.
    """
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.lower()

        # Also get process name for more reliable matching
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            import psutil
            proc = psutil.Process(pid.value)
            pname = proc.name().lower()
        except Exception:
            pname = ""

        # Browser detection
        browser_titles = ("chrome", "firefox", "edge", "brave", "opera", "vivaldi", "safari")
        browser_procs = ("chrome.exe", "firefox.exe", "msedge.exe", "brave.exe", "opera.exe", "vivaldi.exe")
        if any(b in title for b in browser_titles) or pname in browser_procs:
            return "browser"

        # File Explorer
        if pname in ("explorer.exe",) and ("file explorer" in title or "this pc" in title
                                            or ":\\" in title or "desktop" in title
                                            or "downloads" in title or "documents" in title):
            return "explorer"

        # Code editors
        editor_titles = ("visual studio code", "vs code", "vscode", "pycharm", "sublime",
                         "atom", "intellij", "webstorm", "eclipse", "android studio")
        editor_procs = ("code.exe", "pycharm64.exe", "sublime_text.exe", "atom.exe")
        if any(e in title for e in editor_titles) or pname in editor_procs:
            return "editor"

        # Terminal
        terminal_titles = ("command prompt", "powershell", "terminal", "cmd.exe", "windows terminal")
        terminal_procs = ("cmd.exe", "powershell.exe", "windowsterminal.exe", "wt.exe")
        if any(t in title for t in terminal_titles) or pname in terminal_procs:
            return "terminal"

        # Text editors
        text_titles = ("notepad", "wordpad", "word", "google docs", "libreoffice")
        text_procs = ("notepad.exe", "wordpad.exe", "winword.exe")
        if any(t in title for t in text_titles) or pname in text_procs:
            return "editor"

        return "unknown"
    except Exception:
        return "unknown"


def _focus_reset():
    """Send ESC to dismiss any popup/find bar/overlay before executing a command."""
    if _HAS_AUTO:
        pyautogui.press("escape")
        time.sleep(0.08)


def _post_cleanup():
    """Optional ESC after command to dismiss any popup that appeared."""
    if _HAS_AUTO:
        time.sleep(0.08)
        pyautogui.press("escape")


# Commands that should NOT get ESC focus reset (ESC itself, or commands that open dialogs)
_NO_FOCUS_RESET = frozenset({
    "escape", "find", "emoji_picker", "notification_center",
    "run_dialog", "task_manager", "close_window",
})

# Commands that need post-cleanup ESC (they may leave dialogs/overlays)
_NEEDS_POST_CLEANUP = frozenset({
    "find", "print", "go_to_line",
})


def _handle_key_press(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Press a keyboard key or hotkey combo with focus reset."""
    if not _HAS_AUTO:
        speaker.say("Key press requires pyautogui.")
        return

    key = result.key_name
    if not key:
        return

    # Focus reset: ESC before command to clear popups/find bars
    if key not in _NO_FOCUS_RESET:
        _focus_reset()

    # Hotkey combos
    hotkey_map = {
        "select_all": ("ctrl", "a"),
        "undo": ("ctrl", "z"),
        "redo": ("ctrl", "y"),
        "copy": ("ctrl", "c"),
        "paste": ("ctrl", "v"),
        "cut": ("ctrl", "x"),
        "save": ("ctrl", "s"),
        "find": ("ctrl", "f"),
        "new": ("ctrl", "n"),
        "print": ("ctrl", "p"),
        "zoom_in": ("ctrl", "+"),
        "zoom_out": ("ctrl", "-"),
        "zoom_reset": ("ctrl", "0"),
        "bold": ("ctrl", "b"),
        "italic": ("ctrl", "i"),
        "underline": ("ctrl", "u"),
        "fullscreen": ("f11",),
        "alt_tab": ("alt", "tab"),
        "task_manager": ("ctrl", "shift", "escape"),
        "snap_left": ("win", "left"),
        "snap_right": ("win", "right"),
        "show_desktop": ("win", "d"),
        "win_screenshot": ("win", "shift", "s"),
        "lock_pc": ("win", "l"),
        "emoji_picker": ("win", "."),
        "open_explorer": ("win", "e"),
        "open_settings": ("win", "i"),
        "run_dialog": ("win", "r"),
        "notification_center": ("win", "n"),
        "close_window": ("alt", "f4"),
        "rename": ("f2",),
        "address_bar": ("alt", "d"),
        "refresh": ("f5",),
        "pageup": ("pageup",),
        "pagedown": ("pagedown",),

        # --------- Browser navigation (v3.1) ---------
        "focus_address_bar": ("ctrl", "l"),
        "go_back": ("alt", "left"),
        "go_forward": ("alt", "right"),
        "hard_refresh": ("ctrl", "shift", "r"),
        "open_history": ("ctrl", "h"),
        "open_downloads": ("ctrl", "j"),
        "dev_tools": ("f12",),
        "close_tab": ("ctrl", "w"),
        "new_tab": ("ctrl", "t"),
        "reopen_tab": ("ctrl", "shift", "t"),
        "next_tab": ("ctrl", "tab"),
        "prev_tab": ("ctrl", "shift", "tab"),
        "bookmark": ("ctrl", "d"),
        "open_bookmarks": ("ctrl", "shift", "o"),
        "incognito": ("ctrl", "shift", "n"),
        "view_source": ("ctrl", "u"),
        "search_bar": ("ctrl", "k"),

        # --------- Text navigation (v3.1) ---------
        "next_word": ("ctrl", "right"),
        "prev_word": ("ctrl", "left"),
        "select_next_word": ("ctrl", "shift", "right"),
        "select_prev_word": ("ctrl", "shift", "left"),
        "delete_word": ("ctrl", "backspace"),
        "delete_next_word": ("ctrl", "delete"),
        "go_top": ("ctrl", "Home"),
        "go_bottom": ("ctrl", "End"),
        "select_to_start": ("shift", "Home"),
        "select_to_end": ("shift", "End"),
        "select_to_top": ("ctrl", "shift", "Home"),
        "select_to_bottom": ("ctrl", "shift", "End"),
        "move_line_up": ("alt", "up"),
        "move_line_down": ("alt", "down"),
        "duplicate_line": ("ctrl", "shift", "d"),
        "delete_line": ("ctrl", "shift", "k"),
        "go_to_line_dialog": ("ctrl", "g"),
        "toggle_comment": ("ctrl", "/"),
        "indent": ("tab",),
        "outdent": ("shift", "tab"),

        # --------- File Explorer (v3.1) ---------
        "new_folder": ("ctrl", "shift", "n"),
        "properties": ("alt", "enter"),
        "permanent_delete": ("shift", "delete"),
        "preview_pane": ("alt", "p"),
        "nav_pane": ("alt", "d"),
        "go_up_folder": ("alt", "up"),

        # --------- System / Global (v3.1) ---------
        "print_screen": ("printscreen",),
        "alt_print_screen": ("alt", "printscreen"),
        "win_search": ("win", "s"),
        "action_center": ("win", "a"),
        "new_virtual_desktop": ("win", "ctrl", "d"),
        "next_virtual_desktop": ("win", "ctrl", "right"),
        "prev_virtual_desktop": ("win", "ctrl", "left"),
        "close_virtual_desktop": ("win", "ctrl", "f4"),
        "task_view": ("win", "tab"),
        "dictation": ("win", "h"),

        # --------- Result navigation (v3.1) ---------
        "next_link": ("tab",),
        "prev_link": ("shift", "tab"),

        # --------- Media controls (v3.2) ---------
        "play_pause": ("playpause",),
        "next_track": ("nexttrack",),
        "prev_track": ("prevtrack",),

        # --------- Additional shortcuts (v3.2) ---------
        "replace": ("ctrl", "h"),
        "go_to_file": ("ctrl", "p"),
        "command_palette": ("ctrl", "shift", "p"),
        "toggle_sidebar": ("ctrl", "b"),
        "toggle_terminal": ("ctrl", "`"),
        "close_all_tabs": ("ctrl", "shift", "w"),
        "pin_tab": ("ctrl", "shift", "p"),  # Chrome-specific
    }

    # Special multi-step key commands (not simple hotkeys)
    if key == "select_line":
        pyautogui.press("home")
        time.sleep(0.05)
        pyautogui.hotkey("shift", "end")
    elif key == "copy_all":
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "c")
    elif key == "go_back":
        # Context-aware: Backspace in Settings/Explorer, Alt+Left in browsers
        active = _get_active_app()
        if active in ("explorer",):
            pyautogui.press("backspace")
        else:
            pyautogui.hotkey("alt", "left")
    elif key in hotkey_map:
        pyautogui.hotkey(*hotkey_map[key])
    else:
        pyautogui.press(key)

    # Post-cleanup: dismiss any popup that the command may have opened
    if key in _NEEDS_POST_CLEANUP:
        _post_cleanup()

    key_labels = {
        "enter": "Pressed Enter",
        "escape": "Pressed Escape",
        "tab": "Pressed Tab",
        "backspace": "Pressed Backspace",
        "delete": "Deleted",
        "space": "Pressed Space",
        "select_all": "Selected all",
        "undo": "Undo",
        "redo": "Redo",
        "copy": "Copied",
        "paste": "Pasted",
        "cut": "Cut",
        "save": "Saved",
        "find": "Opened Find",
        "new": "New file",
        "print": "Print",
        "zoom_in": "Zoomed in",
        "zoom_out": "Zoomed out",
        "zoom_reset": "Reset zoom",
        "bold": "Bold",
        "italic": "Italic",
        "underline": "Underline",
        "fullscreen": "Full screen",
        "alt_tab": "Switched window",
        "task_manager": "Task Manager",
        "snap_left": "Snapped left",
        "snap_right": "Snapped right",
        "show_desktop": "Show desktop",
        "win_screenshot": "Screen snip",
        "lock_pc": "Locking PC",
        "emoji_picker": "Emoji picker",
        "open_explorer": "File Explorer",
        "open_settings": "Settings",
        "run_dialog": "Run dialog",
        "notification_center": "Notifications",
        "close_window": "Closed window",
        "rename": "Rename",
        "address_bar": "Address bar",
        "refresh": "Refreshed",
        "pageup": "Page Up",
        "pagedown": "Page Down",
        "up": "Arrow Up",
        "down": "Arrow Down",
        "left": "Arrow Left",
        "right": "Arrow Right",
        "home": "Home",
        "end": "End",
        # Browser (v3.1)
        "focus_address_bar": "Address bar",
        "go_back": "Went back",
        "go_forward": "Went forward",
        "hard_refresh": "Hard refresh",
        "open_history": "History",
        "open_downloads": "Downloads",
        "dev_tools": "Developer tools",
        "close_tab": "Closed tab",
        "new_tab": "New tab",
        "reopen_tab": "Reopened tab",
        "next_tab": "Next tab",
        "prev_tab": "Previous tab",
        "bookmark": "Bookmarked",
        "open_bookmarks": "Bookmarks",
        "incognito": "Incognito window",
        "view_source": "View source",
        "search_bar": "Search bar",
        # Text navigation (v3.1)
        "next_word": "Next word",
        "prev_word": "Previous word",
        "select_next_word": "Selected next word",
        "select_prev_word": "Selected previous word",
        "delete_word": "Deleted word",
        "delete_next_word": "Deleted next word",
        "go_top": "Top of document",
        "go_bottom": "Bottom of document",
        "select_line": "Selected line",
        "select_to_start": "Selected to start",
        "select_to_end": "Selected to end",
        "select_to_top": "Selected to top",
        "select_to_bottom": "Selected to bottom",
        "move_line_up": "Moved line up",
        "move_line_down": "Moved line down",
        "duplicate_line": "Duplicated line",
        "delete_line": "Deleted line",
        "go_to_line_dialog": "Go to line",
        "toggle_comment": "Toggled comment",
        "indent": "Indented",
        "outdent": "Outdented",
        # File Explorer (v3.1)
        "new_folder": "New folder",
        "properties": "Properties",
        "permanent_delete": "Permanently deleted",
        "preview_pane": "Preview pane",
        "nav_pane": "Navigation pane",
        "go_up_folder": "Up one folder",
        # System (v3.1)
        "print_screen": "Screenshot taken",
        "alt_print_screen": "Window screenshot",
        "win_search": "Windows search",
        "action_center": "Action center",
        "new_virtual_desktop": "New virtual desktop",
        "next_virtual_desktop": "Next desktop",
        "prev_virtual_desktop": "Previous desktop",
        "close_virtual_desktop": "Closed virtual desktop",
        "task_view": "Task view",
        "dictation": "Dictation",
        # Result navigation (v3.1)
        "next_link": "Next link",
        "prev_link": "Previous link",
        # Media controls (v3.2)
        "play_pause": "Play/Pause",
        "next_track": "Next track",
        "prev_track": "Previous track",
        # Additional shortcuts (v3.2)
        "replace": "Find & Replace",
        "go_to_file": "Quick Open",
        "command_palette": "Command Palette",
        "toggle_sidebar": "Toggle Sidebar",
        "toggle_terminal": "Toggle Terminal",
        "close_all_tabs": "Closed all tabs",
        "pin_tab": "Pin tab",
    }
    msg = key_labels.get(key, f"Pressed {key}")
    speaker.say(msg)
    tray.update_result(f"⌨️ {msg}")
    log.info("Key press: %s", key)


def _handle_selection(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Handle text selection commands using keyboard shortcuts with focus reset."""
    if not _HAS_AUTO:
        speaker.say("Text selection requires pyautogui.")
        return

    action = result.selection_action

    # Focus reset before selection commands (dismiss any popup/find bar)
    if action != "select_word_name":  # select_word_name does its own ESC handling
        _focus_reset()

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
        # ESC first to dismiss any popup, then Ctrl+G
        pyautogui.press("escape")
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "g")
        time.sleep(0.4)
        pyautogui.typewrite(str(line_num), interval=0.03)
        time.sleep(0.1)
        pyautogui.press("enter")
        speaker.say(f"Jumped to line {line_num}")
        tray.update_result(f"📝 Go to line {line_num}")

    elif action == "select_word_name":
        target = result.selection_target
        if not target or len(target.strip()) == 0:
            speaker.say("No word specified to select.")
            return

        # v3.1 Fix: Defensive execution with focus reset
        # Step 1: ESC to dismiss any existing popup/find bar
        pyautogui.press("escape")
        time.sleep(0.15)

        # Step 2: Click on the document body to ensure text area has focus
        # (This helps prevent find bar from retaining focus)
        pyautogui.press("escape")
        time.sleep(0.1)

        # Step 3: Open Find dialog
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.4)

        # Step 4: Clear any existing search text and type the target
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.05)
        pyautogui.typewrite(target, interval=0.03)
        time.sleep(0.15)

        # Step 5: Press Enter to find the word (highlights match if found)
        pyautogui.press("enter")
        time.sleep(0.2)

        # Step 6: Close Find dialog — selection stays on found text
        # Press ESC to close Find bar/dialog
        pyautogui.press("escape")
        time.sleep(0.15)

        # Step 7: If Notepad's "Cannot find" dialog appeared, ESC dismisses it
        # Send one more ESC to be safe (handles both dialog and find bar)
        pyautogui.press("escape")
        time.sleep(0.1)

        speaker.say(f"Found {target}")
        tray.update_result(f"📝 Found: {target}")

    log.info("Selection: %s", action)


def _handle_scroll(result: ParseResult, speaker: Speaker, tray: TrayUI):
    """Handle scroll commands with sensitivity and focus reset."""
    if not _HAS_AUTO:
        speaker.say("Scrolling requires pyautogui.")
        return

    # Focus reset: dismiss popups before scrolling
    _focus_reset()

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
    """Handle browser / file explorer navigation including drives and folders with focus reset."""
    if not _HAS_AUTO:
        speaker.say("Navigation requires pyautogui.")
        return

    # Focus reset: dismiss any popup before navigation
    _focus_reset()

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

    # Drive navigation: navigate in SAME window via address bar
    if action == "drive":
        target = result.nav_target  # e.g. "D:\\"
        drive_letter = target[0]
        import os
        if os.path.exists(target):
            pyautogui.hotkey("ctrl", "l")      # focus address bar
            time.sleep(0.3)
            pyautogui.typewrite(target, interval=0.03)
            time.sleep(0.1)
            pyautogui.press("enter")
            speaker.say(f"Navigated to {drive_letter} drive")
            tray.update_result(f"📂 {drive_letter}: drive")
            log.info("Navigation: drive %s (same window)", target)
        else:
            speaker.say(f"Drive {drive_letter} not found")
            tray.update_result(f"❌ Drive {drive_letter} not found")
        return

    # This PC — navigate in same window
    if action == "this_pc":
        pyautogui.hotkey("ctrl", "l")          # focus address bar
        time.sleep(0.3)
        pyautogui.typewrite("This PC", interval=0.03)
        time.sleep(0.1)
        pyautogui.press("enter")
        speaker.say("Navigated to This PC")
        tray.update_result("📂 This PC")
        log.info("Navigation: This PC (same window)")
        return

    # Known folders: Desktop, Downloads, Documents, etc. — same window
    if action == "known_folder":
        import os
        folder_name = result.nav_target  # e.g. "Downloads"
        folder_path = os.path.join(os.path.expanduser("~"), folder_name)
        if os.path.exists(folder_path):
            pyautogui.hotkey("ctrl", "l")      # focus address bar
            time.sleep(0.3)
            pyautogui.typewrite(folder_path, interval=0.02)
            time.sleep(0.1)
            pyautogui.press("enter")
            speaker.say(f"Navigated to {folder_name}")
            tray.update_result(f"📂 {folder_name}")
            log.info("Navigation: %s (same window)", folder_path)
        else:
            speaker.say(f"{folder_name} folder not found")
            tray.update_result(f"❌ {folder_name} not found")
        return

    # Open/select a subfolder by name in current File Explorer
    if action == "open_folder":
        folder_name = result.nav_target
        # Type the folder name — File Explorer auto-jumps to matching item
        # First click on the file list area to ensure it has focus
        pyautogui.press("escape")
        time.sleep(0.1)
        # Press F5 to refresh focus to file list, then type to jump
        pyautogui.press("f6")  # cycles focus; in Explorer, F6 → file list
        time.sleep(0.2)
        # Type folder name — Explorer jumps to closest match
        pyautogui.typewrite(folder_name, interval=0.05)
        time.sleep(0.3)
        pyautogui.press("enter")               # open the selected folder
        speaker.say(f"Opened {folder_name}")
        tray.update_result(f"📂 → {folder_name}")
        log.info("Navigation: open folder '%s'", folder_name)
        return

    # File Explorer search box
    if action == "explorer_search":
        query = result.nav_target
        pyautogui.hotkey("ctrl", "e")          # focus search box
        time.sleep(0.4)
        pyautogui.typewrite(query, interval=0.04)
        time.sleep(0.2)
        pyautogui.press("enter")
        speaker.say(f"Searching for {query}")
        tray.update_result(f"🔍 Search: {query}")
        log.info("Navigation: explorer search '%s'", query)
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
