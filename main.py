"""
VARNA v1.3 — Voice-Activated Resource & Navigation Assistant
Main entry point.

Pipeline:
  🎤 Always Listening  →  📝 Speech-to-Text  →  🧠 Parser  →  🛡 Whitelist
  →  ⚡ PowerShell Executor  →  🔊 TTS Response

v1.3 additions:
  • Custom macros     ("whenever I say focus mode do open vscode and open chrome")
  • Clipboard         ("read clipboard" / "what did I copy")
  • Smart screenshot  ("screenshot as ReactBug")
  • File search       ("find PDF downloaded yesterday")
  • System tray UI    (floating overlay with mic status, last command, result)
"""

import sys
import os
from listener import Listener
from parser import Parser, ParseResult
from executor import Executor
from speaker import Speaker
from context import SessionContext
from monitor import ProcessMonitor
from macros import MacroManager
from tray import TrayUI
from utils.logger import get_logger

log = get_logger("VARNA")

VERSION = "1.3"

# Exit phrases
EXIT_PHRASES = {"exit", "quit", "stop", "goodbye", "bye", "shut up", "stop listening"}


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
    except Exception as exc:
        log.critical("Initialisation failed: %s", exc)
        print(f"\n[FATAL] {exc}")
        sys.exit(1)

    # --- Start tray UI in background -------------------------------------
    tray.start()

    # --- Calibrate microphone --------------------------------------------
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

        # Parse (with context + macro manager)
        result: ParseResult = parser.parse(text, context=context, macro_manager=macros)

        if not result.matched:
            speaker.say(f"Sorry, I don't recognise the command: {text}")
            tray.update_result(f"❌ Unknown: {text}")
            continue

        tray.update_command(result.matched_key or text)

        # --- Info response -----------------------------------------------
        if result.is_info:
            speaker.say(result.info_text or "No information available.")
            tray.update_result("ℹ️ Info")
            continue

        # --- Clipboard (v1.3) -------------------------------------------
        if result.is_clipboard:
            _handle_clipboard(speaker, tray)
            continue

        # --- Monitor commands -------------------------------------------
        if result.is_monitor:
            _handle_monitor(result, monitor, speaker, tray)
            continue

        # --- Smart Screenshot (v1.3) ------------------------------------
        if result.is_screenshot:
            _handle_screenshot(result, executor, speaker, tray)
            continue

        # --- File Search (v1.3) -----------------------------------------
        if result.is_file_search:
            _handle_file_search(result, executor, speaker, tray)
            continue

        # --- Macro commands (v1.3) --------------------------------------
        if result.is_macro:
            _handle_macro(result, macros, parser, executor, context, speaker, tray)
            continue

        # --- Confirmation layer -----------------------------------------
        if result.needs_confirmation:
            speaker.say(f"Are you sure you want to {result.matched_key}?")
            print(f"   ⚠️  Dangerous command: {result.matched_key}")
            tray.update_result("⚠️ Awaiting confirmation …")

            confirmed = listener.ask_yes_no(timeout=6)

            if confirmed is True:
                speaker.say("Confirmed. Proceeding.")
                log.info("Confirmed: '%s'", result.matched_key)
            elif confirmed is False:
                speaker.say("Command cancelled.")
                tray.update_result("🚫 Cancelled")
                continue
            else:
                speaker.say("No response. Command cancelled for safety.")
                tray.update_result("⏰ Timed out — cancelled")
                continue

        # --- Execute ----------------------------------------------------
        if result.is_chain:
            speaker.say(f"Running chain: {result.matched_key}")
            print(f"   ⛓  Chain: {result.matched_key}  ({len(result.commands)} steps)")

            success, output = executor.run_chain(result.commands)

            if success:
                context.update_after_command(result.matched_key, result.commands[-1])
                tray.update_result("✅ Chain completed")
                if output and output != "All steps completed successfully.":
                    short = output[:300] if len(output) > 300 else output
                    print(f"   📋 Output:\n{short}\n")
                    speaker.say("Chain completed. Here is the output.")
                else:
                    speaker.say("Chain completed successfully.")
            else:
                speaker.say(f"Chain failed: {output}")
                tray.update_result(f"❌ Failed: {output[:60]}")

        else:
            ps_command = result.commands[0]
            speaker.say(f"Running: {result.matched_key}")

            success, output = executor.run(ps_command)

            if success:
                context.update_after_command(result.matched_key, ps_command)
                tray.update_result("✅ Done")
                if output and output != "Command executed successfully.":
                    short = output[:300] if len(output) > 300 else output
                    print(f"   📋 Output:\n{short}\n")
                    speaker.say("Done. Here is the output.")
                else:
                    speaker.say("Done.")
            else:
                speaker.say(f"Something went wrong: {output}")
                tray.update_result(f"❌ Error: {output[:60]}")

    log.info("VARNA v%s shut down cleanly.", VERSION)
    print(f"\n👋  VARNA v{VERSION} has shut down.\n")


# ====================================================================== #
# Handler functions
# ====================================================================== #

def _handle_clipboard(speaker: Speaker, tray: TrayUI):
    """Read clipboard contents and speak them."""
    try:
        import pyperclip
        content = pyperclip.paste()
        if content and content.strip():
            short = content[:500] if len(content) > 500 else content
            print(f"   📋 Clipboard:\n{short}\n")
            # Speak a summarized version (first 200 chars for TTS)
            speak_content = content[:200] if len(content) > 200 else content
            speaker.say(f"Your clipboard contains: {speak_content}")
            tray.update_result("📋 Clipboard read")
        else:
            speaker.say("Your clipboard is empty.")
            tray.update_result("📋 Clipboard empty")
    except ImportError:
        speaker.say("Clipboard feature requires pyperclip. Install it with pip install pyperclip.")
        tray.update_result("❌ pyperclip not installed")
    except Exception as exc:
        speaker.say(f"Could not read clipboard: {exc}")
        tray.update_result(f"❌ Clipboard error")


def _handle_screenshot(result: ParseResult, executor: Executor, speaker: Speaker, tray: TrayUI):
    """Take a screenshot with a custom filename."""
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
        print(f"   📸 Screenshot saved: {filepath}")
        speaker.say(f"Screenshot saved as {name} on your desktop.")
        tray.update_result(f"📸 Saved: {name}.png")
    else:
        speaker.say(f"Screenshot failed: {output}")
        tray.update_result("❌ Screenshot failed")


def _handle_file_search(result: ParseResult, executor: Executor, speaker: Speaker, tray: TrayUI):
    """Search for files matching a natural language query."""
    query = result.file_search_query or ""

    # Parse file type from query
    ext_filter = "*"
    for ext in ["pdf", "doc", "docx", "txt", "xlsx", "pptx", "png", "jpg", "mp4", "zip", "py", "js", "html", "css"]:
        if ext in query.lower():
            ext_filter = f"*.{ext}"
            query = query.lower().replace(ext, "").strip()
            break

    # Parse time filter
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
    elif "last week" in query:
        time_filter = "| Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-14) -and $_.LastWriteTime -lt (Get-Date).AddDays(-7) }"
        query = query.replace("last week", "").strip()

    # Build search — search common locations
    name_filter = f"*{query}*" if query else ext_filter
    search_paths = [
        "$env:USERPROFILE\\Desktop",
        "$env:USERPROFILE\\Downloads",
        "$env:USERPROFILE\\Documents",
    ]

    ps_cmd = "; ".join([
        f"Get-ChildItem -Path {p} -Filter '{name_filter}' -Recurse -ErrorAction SilentlyContinue {time_filter} "
        f"| Select-Object Name, Length, LastWriteTime, FullName | Format-Table -AutoSize"
        for p in search_paths
    ])

    speaker.say(f"Searching for {result.file_search_query}")
    tray.update_result("🔍 Searching …")

    success, output = executor.run(ps_cmd)

    if success and output and output.strip() and output.strip() != "Command executed successfully.":
        short = output[:500] if len(output) > 500 else output
        print(f"   🔍 Search results:\n{short}\n")
        # Count results
        lines = [l for l in output.strip().split("\n") if l.strip() and not l.startswith("-") and not l.startswith("Name")]
        count = len(lines)
        speaker.say(f"Found {count} files matching your search. Check the console for details.")
        tray.update_result(f"🔍 Found {count} files")
    else:
        speaker.say("No files found matching your search.")
        tray.update_result("🔍 No results")


def _handle_macro(result: ParseResult, macros: MacroManager, parser: Parser,
                   executor: Executor, context: SessionContext,
                   speaker: Speaker, tray: TrayUI):
    """Handle macro record / play / list / delete."""

    if result.macro_action == "list":
        names = macros.list_all()
        if names:
            listing = ", ".join(names)
            speaker.say(f"Your macros are: {listing}")
            print(f"   🔁 Macros: {listing}")
            tray.update_result(f"🔁 {len(names)} macros")
        else:
            speaker.say("You haven't saved any macros yet.")
            tray.update_result("🔁 No macros")

    elif result.macro_action == "record" and result.macro_name:
        msg = macros.record(result.macro_name, result.macro_steps)
        speaker.say(msg)
        print(f"   🔁 {msg}")
        tray.update_result(f"🔁 Recorded: {result.macro_name}")

    elif result.macro_action == "delete" and result.macro_name:
        msg = macros.delete(result.macro_name)
        speaker.say(msg)
        print(f"   🔁 {msg}")
        tray.update_result(f"🗑 Deleted: {result.macro_name}")

    elif result.macro_action == "play" and result.macro_name:
        steps = result.macro_steps
        if not steps:
            speaker.say(f"Macro {result.macro_name} has no steps.")
            return

        speaker.say(f"Running macro: {result.macro_name}")
        print(f"   🔁 Macro: {result.macro_name}  ({len(steps)} steps)")
        tray.update_result(f"🔁 Playing: {result.macro_name}")

        for i, step_name in enumerate(steps, 1):
            print(f"      Step {i}: {step_name}")
            # Re-parse each step to get the actual PS command
            step_result = parser.parse(step_name, context=context)
            if step_result.matched and step_result.commands:
                for cmd in step_result.commands:
                    success, output = executor.run(cmd)
                    if success:
                        context.update_after_command(step_name, cmd)
                    else:
                        speaker.say(f"Step {i} failed: {output}")
                        tray.update_result(f"❌ Macro step {i} failed")
                        return
            else:
                speaker.say(f"Step {i} not recognised: {step_name}")
                tray.update_result(f"❌ Unknown step: {step_name}")
                return

        speaker.say(f"Macro {result.macro_name} completed.")
        tray.update_result(f"✅ Macro done: {result.macro_name}")


def _handle_monitor(result: ParseResult, monitor: ProcessMonitor, speaker: Speaker, tray: TrayUI):
    """Handle monitor start / stop / check commands."""
    if result.monitor_action == "start" and result.monitor_process:
        msg = monitor.start(result.monitor_process)
        speaker.say(msg)
        print(f"   📊 {msg}")
        tray.update_result(f"📊 Monitoring: {result.monitor_process}")

    elif result.monitor_action == "stop":
        msg = monitor.stop()
        speaker.say(msg)
        print(f"   📊 {msg}")
        tray.update_result("📊 Monitor stopped")

    elif result.monitor_action == "check" and result.monitor_process:
        status = monitor.get_status(result.monitor_process)
        print(f"   📊 {status}")
        if "not running" in status.lower():
            speaker.say(f"{result.monitor_process} is not running.")
        else:
            speaker.say(f"Here is the status of {result.monitor_process}.")
        tray.update_result(f"📊 {result.monitor_process}")


# ====================================================================== #
if __name__ == "__main__":
    main()
