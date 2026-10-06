# Automated Linux testing

Linux runs use the flatpak [Minecraft Bedrock Launcher](https://mcpelauncher.readthedocs.io/) (`io.mrarm.mcpelauncher`) on KDE Plasma (Wayland). The runner shares `scripts/bedrock_test.py`, the report format, and `dist/bedrock-tests/latest.json` with the Windows runner described in `WINDOWS_TESTING.md`.

## Prerequisites

- The launcher is installed, signed in, and has downloaded the client version named by `linux_client_version` in `testing/bedrock.json` (currently 1.26.52.3).
- Minecraft is closed at the start of each run; the runner launches it.
- `spectacle` and `qdbus6` (KDE) are available for screenshots and window control.
- Python 3.11 or later, and Node.js with npm (script syntax checks, Script API type check).
- Docker, with the pinned `itzg/minecraft-bedrock-server` image available locally, for Scenario Runs.

## Commands

```bash
./test-addon.sh            # All: static checks, Scenario Runs, then the Client Smoke Run
./test-addon.sh Setup      # Create .venv-testing, then Bootstrap
./test-addon.sh Bootstrap  # Create/refresh the Dedicated Test World only
./test-addon.sh Static     # Script API type check, pytest, validation, packaging; no game launch
./test-addon.sh Scenarios  # Headless Scenario Runs only (Docker)
./test-addon.sh Scenarios --only flotation_water,handbrake  # Just these scenarios, in configured order
./test-addon.sh Game       # Client Smoke Run only
./test-addon.sh Client     # Client Input Run: real key presses in the real client (local only, not in All)
./test-addon.sh Client --only sneak_dismounts  # Just these input checks
./test-addon.sh Client --trace --only sneak_dismounts  # Also record the probe during every key hold
./test-addon.sh Client --diag probe.py  # Run probe.py's CHECKS instead (one-off measurements)
./test-addon.sh Doctor     # Read-only discovery of worlds and log directories
```

Bootstrap, Static, and All also install the dev tooling in `package.json` (`@minecraft/server` types pinned to the pack's runtime, and TypeScript) and enable the pre-commit hook in `.githooks/`. The hook runs `node --check` on every script, `npm run typecheck` (`tsc --checkJs` over the behavior pack scripts, catching misspelled Script API members and wrong argument types that the scripts' `try`/`catch` blocks would otherwise swallow in game), and pytest with `REQUIRE_NODE=1` so node-backed contract tests cannot silently skip. `.github/workflows/static.yml` runs the same checks plus validation and packaging in CI. `.github/workflows/scenarios.yml` runs the full Scenario Run on every push in a GitHub-hosted Docker runner; a failing scenario fails the job, and `report.json` plus `scenario-server.log` are uploaded as the `scenario-run` artifact either way. For a real Script API signature, read `node_modules/@minecraft/server/index.d.ts`.

Bootstrap creates the Dedicated Test World `addon-test-<harness uuid>` in `~/.var/app/io.mrarm.mcpelauncher/data/mcpelauncher/games/com.mojang/minecraftWorlds/` from the same pinned Mojang starter as Windows, and enables `content_log_file` after backing up `options.txt` under `dist/bedrock-tests/setup/`. Other worlds are never modified.

## What a Client Smoke Run verifies

The runner deploys the add-on and the test-only harness into the Dedicated Test World, then starts the client directly with `flatpak run --command=mcpelauncher-client … -u minecraft://?load=<world>`, using the newest `mcpelauncher-updates` compatibility mod. Client output is saved as `client-stdout.log` in the run directory.

The Linux client never surfaces script console output: `ContentLog*.txt` stays empty and the harness `[ADDON_TEST]` marker is absent from client output. A Linux run therefore passes on:

- **world_load**: the client opened the Dedicated Test World, loaded the test behavior pack and the harness pack (from its `Pack Stack` lines), and spawned the player;
- **screenshots**: at least two showcase captures, including the side-on view of a truck parked on a 1:2 ramp for Dynamic Incline Pitch;
- **shutdown**: the game window is closed normally through a KWin script (the world is saved), with a SIGTERM to only the launched sandbox as fallback.

`stages.gameplay` is `not_verified` on Linux. Gameplay pass/fail comes from headless Scenario Runs (ADR-0016). Screenshots still require human review.

Before each capture the runner raises the window titled "Minecraft" through a temporary KWin script, then captures the active window with `spectacle`. Avoid using the desktop during a run.

## Scenario Runs

Scenario Runs assert gameplay headlessly (ADR-0016). Settings live under `scenario_server` in `testing/bedrock.json`.

1. The official Bedrock Dedicated Server zip for the pinned version is downloaded once to `dist/bedrock-tests/cache/` and verified against the pinned SHA-256 on every run.
2. The runner unpacks it into `dist/bedrock-tests/<run-id>/server/` and builds the **Scenario World** from the pinned flat starter, with the Beta APIs experiment enabled. It installs the add-on packs plus the test-only pack from `testing/scenarios/` (`@minecraft/server-gametest`).
3. A throwaway container `monster-truck-scenario-<run-id>` starts from the digest-pinned image with `VERSION=EXISTING`, `--network none`, no published ports, offline mode, and a TTY so output streams live.
4. The scenario pack loads a ticking area at world spawn, spawns the **Simulated Driver**, runs each scenario listed in `scenario_server.scenarios`, and prints `[SCENARIO]` PASS/FAIL markers and a final DONE marker.
5. The container is stopped and removed, the unpacked server directory is deleted, and `scenario-server.log` is kept. Any scenario failure, missing result, or other server WARN/ERROR line fails the run.

Add scenarios in `testing/scenarios/scenarios.js` and list them in `scenario_server.scenarios`. While iterating on one failure, rerun only it with `--only`; run the full list before committing. Engine behavior that scenario checks depend on (drag, collisions, the damage immunity window) is in `docs/agents/bedrock-physics.md`. The user's long-lived server containers are never used.

## Client Input Run

A Client Input Run presses real keys in the real client and asserts the outcome in the client's own world (ADR-0019). It is local only: it takes the keyboard, so it is not part of All and never runs in CI. Step away from the desktop while it runs.

1. The runner deploys the add-on plus the harness in probe mode. The harness publishes, every tick, the player's seat (`riding`), ticks spent out of a seat (`lost`), and the Sneak, Jump and look state on the `mt_probe` scoreboard instead of running the showcase.
2. For the run only, `options.txt` gets `websockets_enabled:1`, `websocket_encryption:0`, and Sneak bound to K (a virtual Shift never reaches this launcher as Sneak; a real Shift does). Only those keys are restored afterwards; the game's other changes are kept.
3. The client loads the Dedicated Test World. A user-level uinput virtual keyboard (`scripts/linux_input.py`, no root: `/dev/uinput` has a uaccess ACL for the seat user) types `/connect 127.0.0.1:<port>` into chat, and `scripts/client_ws.py` answers as the WebSocket server.
4. Each check summons a fresh truck, seats the player in the Driver Seat, holds keys, and reads positions (`querytarget`) and the probe scoreboard: `w_drives`, `a_turns_left`, `d_turns_right`, `space_keeps_rider` (the player is in the seat on every tick the probe sees while Space is held), `s_brakes_and_reverses` (S brakes, then reverses straight back), `sneak_dismounts` (Sneak leaves the truck, the player stays out, and their Jump input is back on), `space_sneak_exits` (Sneak with the handbrake still held also gets the player out), `sneak_exits_afloat` (Sneak while floating in a pool sets the player down on dry land at its edge), and `sneak_during_drop` (Sneak held while the truck drops 32 blocks keeps the player seated until it lands; after that, Sneak gets them out). Each check saves a screenshot under `client-input/`.

Before every key press a focus guard (a KWin script reporting the active window through the user journal) checks that the launched Minecraft window has focus. Any other window ends the run with every key released. Mouse look is not checked: virtual pointer motion reaches the game only while the pointer is over the window, and the `steering` scenario already proves that look does not steer.

What the real client does differently from the dedicated server (riding and Sneak, Space dismounts, virtual keys, chat, client-side commands) is in `docs/agents/bedrock-physics.md`, "The real client". To diagnose a failed check, rerun it with `--trace`.

## Scenario Run blind spots

A green Scenario Run proves server-side state. A player-reported bug in any area below needs the real client to confirm the fix; treat the scenario as necessary, not sufficient.

- **Key mapping and engine input handling.** The Simulated Driver sends no key presses: its movement and held Jump button reach the add-on only through the `driverInput` seam in `main.js`. Which key gives which movement-vector sign (`LEFT_INPUT_SIGN` in `driving.js`), and how the engine treats a key, never show up server-side. Run a Client Input Run for these. It found that Minecraft dismounts a rider who presses Space, and that a riding player never reads as sneaking: setting `isSneaking` on a Simulated Driver does not reproduce a real Sneak exit.
- **Client rendering.** Rider position, seat flicker, animations, and the camera. During #32 the server kept the driver seated and linked on every tick while the player saw them leave the truck.
- **Feel.** Acceleration, drift, and turning radius are asserted as numbers; whether they feel right is the player's call.

For bugs in these areas, look for engine or component explanations first: ADRs, and `git log -S '<component>'` for earlier fixes of the same symptom.

