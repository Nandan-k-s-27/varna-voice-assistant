"""
VARNA v1.1 — Voice-Activated Resource & Navigation Assistant
Main entry point.

Pipeline:
  🎤 Microphone  →  📝 Speech-to-Text  →  🧠 Parser  →  🛡 Whitelist
  →  ⚡ PowerShell Executor  →  🔊 TTS Response

v1.1 additions:
  • Parameterized commands  (e.g. "search React hooks")
  • Multi-step command chains (e.g. "start my backend")
  • Developer-mode commands  (e.g. "kill port 3000")
"""

import sys
from listener import Listener
from parser import Parser, ParseResult
from executor import Executor
from speaker import Speaker
from utils.logger import get_logger

log = get_logger("VARNA")

VERSION = "1.1"

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

        # Parse the spoken text
        result: ParseResult = parser.parse(text)

        if not result.matched:
            speaker.say(f"Sorry, I don't recognise the command: {text}")
            continue

        # --- Execute -------------------------------------------------------
        if result.is_chain:
            # Multi-step command chain
            speaker.say(f"Running chain: {result.matched_key}")
            print(f"   ⛓  Chain: {result.matched_key}  ({len(result.commands)} steps)")

            success, output = executor.run_chain(result.commands)

            if success:
                if output and output != "All steps completed successfully.":
                    short = output[:300] if len(output) > 300 else output
                    print(f"   📋 Output:\n{short}\n")
                    speaker.say("Chain completed. Here is the output.")
                else:
                    speaker.say("Chain completed successfully.")
            else:
                speaker.say(f"Chain failed: {output}")

        else:
            # Single command execution
            ps_command = result.commands[0]
            speaker.say(f"Running: {result.matched_key}")

            success, output = executor.run(ps_command)

            if success:
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
if __name__ == "__main__":
    main()
