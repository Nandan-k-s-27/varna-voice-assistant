"""
VARNA v1.2 — Voice-Activated Resource & Navigation Assistant
Main entry point.

Pipeline:
  🎤 Always Listening  →  📝 Speech-to-Text  →  🧠 Parser  →  🛡 Whitelist
  →  ⚡ PowerShell Executor  →  🔊 TTS Response

Behaviour:
  • VARNA listens continuously and processes ALL recognised speech.
  • Context tracking remembers last app, last browser, last project.
  • Dangerous commands require voice confirmation ("Are you sure?").
"""

import sys
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
    log.info("Entering main loop. Say 'exit' to quit.")
    print(f"\n🎤  VARNA v{VERSION} is listening. Say a command (or 'exit' to quit).\n")

    while True:
        text = listener.listen(timeout=7, phrase_time_limit=10)

        if text is None:
            # No speech detected — silently loop
            continue

        print(f'   You said: "{text}"')

        # Check for exit intent
        if text in EXIT_PHRASES:
            log.info("Exit phrase detected: '%s'", text)
            if monitor.is_running:
                monitor.stop()
            speaker.goodbye()
            break

        # Check for "help" / "list commands"
        if text in {"help", "list commands", "what can you do"}:
            cmds = parser.list_commands()
            summary = ", ".join(cmds[:10])
            speaker.say(f"I can do things like: {summary}, and more.")
            continue

        # Check for "developer commands" / "dev help"
        if text in {"developer commands", "dev commands", "dev help"}:
            dev_cmds = parser.list_developer_commands()
            summary = ", ".join(dev_cmds[:8])
            speaker.say(f"Developer commands include: {summary}.")
            continue

        # Parse the spoken text (with context for browser-awareness etc.)
        result: ParseResult = parser.parse(text, context=context)

        if not result.matched:
            speaker.say(f"Sorry, I don't recognise the command: {text}")
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
