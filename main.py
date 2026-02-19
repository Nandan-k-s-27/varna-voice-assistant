"""
VARNA v1.2 — Voice-Activated Resource & Navigation Assistant
Main entry point.

Pipeline:
  🎤 Always Listening  →  🔑 "VARNA" keyword detection  →  📝 Extract command
  →  🧠 Parser  →  🛡 Whitelist  →  ⚡ PowerShell Executor  →  🔊 TTS Response

Behaviour:
  • VARNA listens continuously to everything.
  • Only when the user says "varna" somewhere in the phrase does it
    treat the rest as a command.  E.g. "varna search html elements".
  • All other speech is silently ignored.
"""

import sys
import re
from listener import Listener
from parser import Parser, ParseResult
from executor import Executor
from speaker import Speaker
from context import SessionContext
from monitor import ProcessMonitor
from utils.logger import get_logger

log = get_logger("VARNA")

VERSION = "1.2"

# Exit phrases (user says any of these to quit)
EXIT_PHRASES = {"exit", "quit", "stop", "goodbye", "bye", "shut up", "stop listening"}

# Pattern to detect and strip the wake keyword from spoken text
_WAKE_PATTERN = re.compile(
    r"\b(?:hey\s+varna|hi\s+varna|hello\s+varna|ok\s+varna|varna)\b",
    re.IGNORECASE,
)


def _extract_command(text: str) -> str | None:
    """
    If the text contains the keyword 'varna', strip it out and return
    the remaining text as the intended command.
    Returns None if 'varna' is not present in the text.
    """
    if not _WAKE_PATTERN.search(text):
        return None

    # Remove the wake-word and clean up
    command = _WAKE_PATTERN.sub("", text).strip()
    # Collapse multiple spaces
    command = re.sub(r"\s{2,}", " ", command)
    return command if command else None


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
    except Exception as exc:
        log.critical("Initialisation failed: %s", exc)
        print(f"\n[FATAL] {exc}")
        sys.exit(1)

    # --- Calibrate microphone --------------------------------------------
    speaker.say("Calibrating microphone. Please wait.")
    listener.calibrate(duration=2.0)

    # --- Greet the user --------------------------------------------------
    speaker.greet()

    # --- Main loop -------------------------------------------------------
    log.info("Entering main loop. Say 'varna <command>' to interact.")
    print(f"\n🎤  VARNA v{VERSION} is listening. Say 'VARNA <command>' to interact.\n")

    while True:
        # Always listen for speech
        text = listener.listen(timeout=7, phrase_time_limit=10)

        if text is None:
            # No speech detected — silently loop
            continue

        # --- Check if the user said "varna" somewhere --------------------
        command = _extract_command(text)

        if command is None:
            # "varna" was NOT in the speech — ignore completely
            log.debug("Ignored (no wake keyword): '%s'", text)
            continue

        # If user ONLY said "varna" with no command
        if not command:
            speaker.say("Yes? What can I do for you?")
            continue

        print(f'   You said: "{command}"')

        # Check for exit intent
        if command in EXIT_PHRASES:
            log.info("Exit phrase detected: '%s'", command)
            if monitor.is_running:
                monitor.stop()
            speaker.goodbye()
            break

        # Check for "help" / "list commands"
        if command in {"help", "list commands", "what can you do"}:
            cmds = parser.list_commands()
            summary = ", ".join(cmds[:10])
            speaker.say(f"I can do things like: {summary}, and more.")
            continue

        # Check for "developer commands" / "dev help"
        if command in {"developer commands", "dev commands", "dev help"}:
            dev_cmds = parser.list_developer_commands()
            summary = ", ".join(dev_cmds[:8])
            speaker.say(f"Developer commands include: {summary}.")
            continue

        # Parse the spoken command (with context for browser-awareness etc.)
        result: ParseResult = parser.parse(command, context=context)

        if not result.matched:
            speaker.say(f"Sorry, I don't recognise the command: {command}")
            continue

        # --- Info response (no execution needed) -----------------------
        if result.is_info:
            speaker.say(result.info_text or "No information available.")
            continue

        # --- Monitor commands ------------------------------------------
        if result.is_monitor:
            _handle_monitor(result, monitor, speaker)
            continue

        # --- Confirmation layer ----------------------------------------
        if result.needs_confirmation:
            speaker.say(f"Are you sure you want to {result.matched_key}?")
            print(f"   ⚠️  Dangerous command: {result.matched_key} — waiting for confirmation …")

            confirmed = listener.ask_yes_no(timeout=6)

            if confirmed is True:
                speaker.say("Confirmed. Proceeding.")
                log.info("User confirmed dangerous command: '%s'", result.matched_key)
            elif confirmed is False:
                speaker.say("Command cancelled.")
                log.info("User cancelled dangerous command: '%s'", result.matched_key)
                continue
            else:
                speaker.say("No response. Command cancelled for safety.")
                log.info("Confirmation timed out for: '%s'", result.matched_key)
                continue

        # --- Execute ---------------------------------------------------
        if result.is_chain:
            speaker.say(f"Running chain: {result.matched_key}")
            print(f"   ⛓  Chain: {result.matched_key}  ({len(result.commands)} steps)")

            success, output = executor.run_chain(result.commands)

            if success:
                context.update_after_command(result.matched_key, result.commands[-1])
                if output and output != "All steps completed successfully.":
                    short = output[:300] if len(output) > 300 else output
                    print(f"   📋 Output:\n{short}\n")
                    speaker.say("Chain completed. Here is the output.")
                else:
                    speaker.say("Chain completed successfully.")
            else:
                speaker.say(f"Chain failed: {output}")

        else:
            ps_command = result.commands[0]
            speaker.say(f"Running: {result.matched_key}")

            success, output = executor.run(ps_command)

            if success:
                context.update_after_command(result.matched_key, ps_command)
                if output and output != "Command executed successfully.":
                    short = output[:300] if len(output) > 300 else output
                    print(f"   📋 Output:\n{short}\n")
                    speaker.say("Done. Here is the output.")
                else:
                    speaker.say("Done.")
            else:
                speaker.say(f"Something went wrong: {output}")

    log.info("VARNA v%s shut down cleanly.", VERSION)
    print(f"\n👋  VARNA v{VERSION} has shut down.\n")


# ====================================================================== #
def _handle_monitor(result: ParseResult, monitor: ProcessMonitor, speaker: Speaker):
    """Handle monitor start / stop / check commands."""
    if result.monitor_action == "start" and result.monitor_process:
        msg = monitor.start(result.monitor_process)
        speaker.say(msg)
        print(f"   📊 {msg}")

    elif result.monitor_action == "stop":
        msg = monitor.stop()
        speaker.say(msg)
        print(f"   📊 {msg}")

    elif result.monitor_action == "check" and result.monitor_process:
        status = monitor.get_status(result.monitor_process)
        print(f"   📊 {status}")
        if "not running" in status.lower():
            speaker.say(f"{result.monitor_process} is not running.")
        else:
            speaker.say(f"Here is the status of {result.monitor_process}.")


# ====================================================================== #
if __name__ == "__main__":
    main()
