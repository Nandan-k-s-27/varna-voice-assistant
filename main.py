"""
VARNA v1.4 — Voice-Activated Resource & Navigation Assistant
Main entry point.

Pipeline:
  🎤 Always Listening  →  🧹 NLP Clean  →  🧠 Parser  →  🛡 Whitelist
  →  ⚡ Executor / Window Manager / PyAutoGUI  →  🔊 TTS Response

v1.4 additions:
  • Window intelligence (smart open/minimize/maximize/switch/restore)
  • Voice typing      ("type hello world" in active app)
  • Tab control       ("close tab", "new tab", "next tab", "previous tab")
  • Flexible NLP      (filler removal + fuzzy match + intent fallback)
  • Smart search      (search in current tab if browser active)
  • Natural chains    ("open edge and search React hooks" split + sequential)
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
from window_manager import WindowManager
from utils.logger import get_logger

log = get_logger("VARNA")

VERSION = "1.4"

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
                                    macros, win_mgr, speaker, tray, listener)
                    time.sleep(0.8)  # Small delay between steps
                continue

        # Single command
        _process_single(text, parser, executor, context, monitor,
                        macros, win_mgr, speaker, tray, listener)

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

    # --- Window intelligence (v1.4) ---
    if result.is_window:
        _handle_window(result, win_mgr, context, speaker, tray)
        return

    # --- Voice typing (v1.4) ---
    if result.is_typing:
        _handle_typing(result, speaker, tray)
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
# Handler functions
# ====================================================================== #

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
    """Type text into the active window."""
    if not _HAS_AUTO:
        speaker.say("Voice typing requires pyautogui. Install it with pip install pyautogui.")
        return

    text = result.typing_text
    if text:
        speaker.say(f"Typing: {text}")
        time.sleep(0.5)  # Small delay to let TTS finish before typing
        pyautogui.write(text, interval=0.03)
        log.info("Typed: '%s'", text)
        tray.update_result(f"⌨️ Typed: {text[:30]}")


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
