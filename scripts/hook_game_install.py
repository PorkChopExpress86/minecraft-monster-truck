"""Lifecycle hook script to remind/prompt for game installation when changes are made."""
import json
import sys
from pathlib import Path

def main():
    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        payload = {}

    # PreInvocation hook: inject an ephemeral system instruction
    if "invocationNum" in payload:
        msg = (
            "[HOOK: Minecraft Installation Reminder]\n"
            "Whenever changes or improvements to the add-on files (behavior packs, resource packs, or scripts) "
            "are completed, prompt the user asking whether they would like to install the updated add-on to "
            "their local Minecraft installation (via `python scripts/install_addon.py`)."
        )
        print(json.dumps({
            "injectSteps": [
                {"ephemeralMessage": msg}
            ]
        }))
        return

    # Default empty response for other events
    print(json.dumps({}))

if __name__ == "__main__":
    main()
