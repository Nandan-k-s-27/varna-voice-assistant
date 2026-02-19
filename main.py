"""
VARNA v1 — Voice-Activated Resource & Navigation Assistant
Main entry point.

Pipeline:
  🎤 Microphone  →  📝 Speech-to-Text  →  🧠 Parser  →  🛡 Whitelist
  →  ⚡ PowerShell Executor  →  🔊 TTS Response
"""

import sys
from listener import Listener
from parser import Parser
from executor import Executor
from speaker import Speaker
from utils.logger import get_logger

log = get_logger("VARNA")

# Exit phrases (user says any of these to quit)
EXIT_PHRASES = {"exit", "quit", "stop", "goodbye", "bye", "shut up", "stop listening"}


def main() -> None:
    """Run the VARNA assistant loop."""

    log.info("=" * 60)
    log.info("VARNA v1 starting up …")
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
    print("\n🎤  VARNA is listening. Say a command (or 'exit' to quit).\n")

    while True:
        text = listener.listen(timeout=7, phrase_time_limit=10)

        if text is None:
            # No speech detected — silently loop
            continue

        print(f"   You said: \"{text}\"")

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

        # Parse the spoken text
        matched_key, ps_command = parser.parse(text)

        if matched_key is None:
            speaker.say(f"Sorry, I don't recognise the command: {text}")
            continue

        # Execute the matched command
        speaker.say(f"Running: {matched_key}")
        success, output = executor.run(ps_command)

        if success:
            # For info-type commands, read out the result
            if output and output != "Command executed successfully.":
                # Truncate long outputs
                short = output[:300] if len(output) > 300 else output
                print(f"   📋 Output:\n{short}\n")
                speaker.say("Done. Here is the output.")
            else:
                speaker.say("Done.")
        else:
            speaker.say(f"Something went wrong: {output}")

    log.info("VARNA v1 shut down cleanly.")
    print("\n👋  VARNA has shut down.\n")


# ====================================================================== #
if __name__ == "__main__":
    main()
