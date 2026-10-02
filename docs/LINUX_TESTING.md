# Automated Linux testing

Linux runs use the flatpak [Minecraft Bedrock Launcher](https://mcpelauncher.readthedocs.io/) (`io.mrarm.mcpelauncher`) on KDE Plasma (Wayland). The runner shares `scripts/bedrock_test.py`, the report format, and `dist/bedrock-tests/latest.json` with the Windows runner described in `WINDOWS_TESTING.md`.

## Prerequisites

- The launcher is installed, signed in, and has downloaded the client version named by `linux_client_version` in `testing/bedrock.json` (currently 1.26.52.3).
- Minecraft is closed at the start of each run; the runner launches it.
- `spectacle` and `qdbus6` (KDE) are available for screenshots and window control.
- Python 3.11 or later.

## Commands

```bash
./test-addon.sh            # All: static checks, then the Client Smoke Run
./test-addon.sh Setup      # Create .venv-testing, then Bootstrap
./test-addon.sh Bootstrap  # Create/refresh the Dedicated Test World only
./test-addon.sh Static     # pytest, validation, packaging; no game launch
./test-addon.sh Game       # Client Smoke Run only
./test-addon.sh Doctor     # Read-only discovery of worlds and log directories
```

Bootstrap creates the Dedicated Test World `addon-test-<harness uuid>` in `~/.var/app/io.mrarm.mcpelauncher/data/mcpelauncher/games/com.mojang/minecraftWorlds/` from the same pinned Mojang starter as Windows, and enables `content_log_file` after backing up `options.txt` under `dist/bedrock-tests/setup/`. Other worlds are never modified.

## What a Client Smoke Run verifies

The runner deploys the add-on and the test-only harness into the Dedicated Test World, then starts the client directly with `flatpak run --command=mcpelauncher-client … -u minecraft://?load=<world>`, using the newest `mcpelauncher-updates` compatibility mod. Client output is saved as `client-stdout.log` in the run directory.

The Linux client never surfaces script console output: `ContentLog*.txt` stays empty and the harness `[ADDON_TEST]` marker is absent from client output. A Linux run therefore passes on:

- **world_load**: the client opened the Dedicated Test World, loaded the test behavior pack and the harness pack (from its `Pack Stack` lines), and spawned the player;
- **screenshots**: at least two showcase captures, including the side-on view of a truck parked on a 1:2 ramp for Dynamic Incline Pitch;
- **shutdown**: the game window is closed normally through a KWin script (the world is saved), with a SIGTERM to only the launched sandbox as fallback.

`stages.gameplay` is `not_verified` on Linux. Gameplay pass/fail comes from headless Scenario Runs (ADR-0016). Screenshots still require human review.

Before each capture the runner raises the window titled "Minecraft" through a temporary KWin script, then captures the active window with `spectacle`. Avoid using the desktop during a run.
