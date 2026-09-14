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

    # PreInvocation hook: inject an ephemeral system instruction with live version status
    if "invocationNum" in payload:
        repo_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(repo_root))
        sys.path.insert(0, str(repo_root / "scripts"))
        try:
            from version_manager import check_version_sync
            status = check_version_sync(repo_root)
            sync_info = f"Version: Finished repo is v{status['repo_version_str']} | Sync Status: {status['summary']}"
        except Exception:
            sync_info = "Version status: Run `python scripts/install_addon.py --check`"

        msg = (
            "[HOOK: Minecraft Installation & Version Rev Reminder]\n"
            f"{sync_info}\n"
            "Whenever you complete changes, bug fixes, or improvements to the add-on files "
            "(`behavior_packs/`, `resource_packs/`, or `scripts/`), you MUST proactively prompt the user "
            "asking whether they would like to rev the version and install the updated add-on directly to "
            "their local Minecraft game (running `python scripts/install_addon.py` upon confirmation), "
            "so the installed game version and the latest finished version are verified to match."
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
