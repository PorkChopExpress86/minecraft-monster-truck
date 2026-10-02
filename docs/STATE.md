## Goal
Set up the add-on for Linux development, debug, install, and fully automate in-game testing of the monster truck.
## Now
#37 answered. User testing truck speed in 'Monster Truck Playground' world (random terrain, creative, 16 trucks + speedometer helper pack); then #38.
## Next
1. #36 Scenario Run container bootstrap. 3. #37 Simulated Driver prototype. 4. #38 mechanic scenarios incl. pitch. 5. #39 CI.
6. After #38: trim issues #27-#30 to visual-only residue.
## Constraints
- "if there is something strange then prompt me for input" (re: test thresholds/outcomes)
- "do not look into the separt containers" (re: NetherNet errors on minecraft-creative/minecraft-survival)
## Decisions
- DECISION: Scenario driver runs inside a Scenario-World-only copy of the add-on BP (entry imports main.js + scenario_driver) on @minecraft/server 2.11.0-beta — simulated players only materialize in the spawning runtime (user approved).
- DECISION: Production exports requestDriverJump(player), called by the Jump-button handler and by jump scenarios (user chose 2a).
- DECISION: Linux Client Smoke Run verdict = world loaded with our packs (client stdout) + screenshots; gameplay stage not_verified on Linux; all gameplay pass/fail from BDS Scenario Runs — Android-based client never surfaces script console output (user chose option 1).
- DECISION: Automate driving mechanics via BDS + GameTest SimulatedPlayer, keep real client for smoke + screenshots — no Wayland input injection (ADR-0007 stays).
- DECISION: Target Minecraft 1.26.52.3 for both client and BDS — client already downloaded; official BDS 1.26.52.3 Linux zip exists.
- DECISION: Run BDS via Docker image itzg/minecraft-bedrock-server (user already uses it) — not a native zip.
- DECISION: Extend scripts/bedrock_test.py with a Linux platform mode + test-addon.sh, same report format — shared stage/report logic.
- DECISION: Client Smoke Run screenshots via spectacle on the live KDE Wayland desktop.
- DECISION: Dedicated Test World created in flatpak com.mojang; "Hiker's Friend" untouched; content_log_file enabled with options.txt backup.
- DECISION: Scenario mechanics 1-9 (auto-step, jump+stomp, shock absorption, flotation+shoreline, trample+molten, demolition+shearing, dye repaint, retrieval/scrap, seats) plus Dynamic Incline Pitch on hills (user: "realistic look where the truck pitches up going up a hill").
- DECISION: If SimulatedPlayer cannot drive the truck, STOP and ask user (no silent fallback to scripted impulses).
- DECISION: Beta APIs experiment allowed in the Scenario World only; production pack stays on stable @minecraft/server 2.10.0.
- DECISION: Spec-defining outcomes hard-coded in tests; tuning values read from vehicle.config.json; anything strange -> prompt user.
- DECISION: Local test-addon.sh modes (Static/Scenarios/Game/All) + GitHub Actions for static + BDS scenarios as last slice.
- DECISION: Glossary terms Scenario Run, Simulated Driver, Scenario World, Client Smoke Run.
- DECISION: Scenario Run uses an ephemeral container monster-truck-scenario-<run-id> (itzg image digest-pinned, VERSION=1.26.52.3, private network, no host ports, mounts dist/bedrock-tests/<run-id>/, removed after) — never touch minecraft-creative/minecraft-survival.
- DECISION: install_addon.py gains opt-in `--servers creative,survival` (copy packs to /data, activate in world, require texture pack, confirm before each container restart); default installs to local client only.
- DECISION: Incline pitch scenario: stepped ramps at 1:2 (~27deg), 1:3 (~18deg), 1:1 (clamp 35deg); assert pitch >0 uphill and <0 downhill within +-5deg of atan(rise/run), returns to 0 on flat, per-tick delta within smoothing bound; strange results -> ask user.
- DECISION: Client Smoke Run showcase adds a camera angle on a truck parked on a slope.
- DECISION: If 1.26.52.3 client fails to launch -> stop and ask user (no fallback to 1.26.45.1); Scenario Runs proceed independently.
## Facts
- Launcher: flatpak io.mrarm.mcpelauncher v1.8.4; client binary via `flatpak run --command=mcpelauncher-client io.mrarm.mcpelauncher` supports `-u minecraft://?load=<world>`.
- com.mojang (Linux): ~/.var/app/io.mrarm.mcpelauncher/data/mcpelauncher/games/com.mojang ; versions in .../data/mcpelauncher/versions/ (1.26.40.5, 1.26.52.3).
- Bug: scripts/version_manager.py:126 find_com_mojang_roots() only checks Windows APPDATA/LOCALAPPDATA -> install_addon.py fails on Linux.
- Existing user BDS containers (do not touch): minecraft-creative, minecraft-survival (itzg image, VERSION=LATEST, already on bedrock_server-1.26.52.3, network media_proxy, compose dir /mnt/samsung/Docker/MediaServer, volumes media-stack_minecraft_{creative,survival}_data).
- Dynamic Incline Pitch is server-observable via entity property blake:pitch_angle (int, clamp +-35), computed in behavior_packs/MonsterTruck_BP/scripts/kinematics.js.
- Tests: .venv-testing/bin/python -m pytest -q (venv created from requirements-testing.txt).
- Docker servers keep add-ons in /data/behavior_packs/<Name>_BP and /data/resource_packs/<Name>_RP, world lists at /data/worlds/<level-name>/world_*_packs.json, texturepack-required=true already.
- Linux client: `flatpak run --command=mcpelauncher-client io.mrarm.mcpelauncher -dg <data>/versions/1.26.52.3 -m <data>/mods/mcpelauncher-updates/1.26.45.1/x86_64/ -u minecraft://?load=<world folder>` loads the world directly; flatpak run execs into bwrap so Popen.pid is the process-group leader; KWin script closeWindow() exits rc 0; spectacle -b -n -a -e -S captures after KWin activation.
- Linux content logs: com.mojang/logs/ContentLog<date>.txt (created but stays empty).
- Dedicated Test World: com.mojang/minecraftWorlds/addon-test-b06f3b8a-1a26-4f26-a3aa-76c2c480ad35 ; options.txt backup in dist/bedrock-tests/setup/.
- Scenario server: official BDS zip sha256 f6348d84...71c6 cached in dist/bedrock-tests/cache; image itzg/minecraft-bedrock-server@sha256:42004bb6...; needs ONLINE_MODE=false, ALLOW_LIST=false, docker -t (else stdout block-buffered); modules @minecraft/server 2.11.0-beta + @minecraft/server-gametest 1.0.0-beta; spawnSimulatedPlayer(DimensionLocation, name, GameMode) top-level.
- Desktop: KDE Wayland; spectacle installed; no xdotool/ydotool.
## Done
- #37 — RESULT (run 1ec3980aa43a4a71b9a6aa43c4941866, 0 errors): driver seats at seat 0 via interactWithEntity; moveRelative drives truck 63.84 blocks/60 ticks; setBodyRotation steers (yaw 0->90, steer_angle=1); requestDriverJump(driver) -> Suspension Jump +4.92 blocks. Fixes: driver runs inside test copy of add-on runtime (server 2.11.0-beta + gametest); production exports requestDriverJump.
- Playground world created: com.mojang/minecraftWorlds/monster-truck-playground (seed 8832057175689493418), helper pack spawns 16 trucks once + actionbar speedometer; BDS load check clean.
- #36 Scenario Run container — RESULT: ./test-addon.sh Scenarios exit 0, run 5a61248ad05a41ae8bc5e6e27fc389d8 smoke PASS (simulated driver joined, truck spawned, 2 seats), no container left; pytest 135 passed.
- #35 Linux Client Smoke Run — RESULT: ./test-addon.sh Game exit 0, PASSED run 137bd73e04984abd9e6063415e020472 (world_load, screenshots 3 + final hill view, shutdown passed; gameplay not_verified by design); pytest 127 passed.
- #34 committed 408a9de; v1.0.3 installed to flatpak client + both Docker servers (server logs show Monster Truck Behavior 1.0.3 in Pack Stack).
- Grilling + ADR-0016 + CONTEXT.md terms + GitHub spec #33 and slices #34-#39 — RESULT: created.
- #34 Linux install — RESULT: find_com_mojang_roots finds flatpak root on this machine; install_addon.py --servers creative,survival added (docker cp to /data/{behavior,resource}_packs, world_*_packs.json entry, texturepack-required, confirm restart); .venv-testing/bin/python -m pytest -q -> 120 passed (baseline 116). Live server deploy not yet run.
## Open items
- Speed: Simulated Driver drives ~1.06 blocks/tick (~21 b/s) vs design 0.55 b/tick (ADR-0011, PROVING_GROUND item 7). User is measuring real driving in the playground speedometer; calibrate #38 speed checks to their answer.
- NOTED (not done): main.js:166 `currentRiders.map((r) => r.id)` throws if getRiders() ever yields undefined (only seen with cross-runtime simulated players).
- Pitch rounding in kinematics.js (Math.round after 0.2 smoothing) stalls up to ~2 deg short of target — check against the +-5 deg pitch tolerance in #38.
## Failed attempts
- #37 probe run d45e0504130947af80cbd899c710b7dc: interactWithEntity seats SimulatedDriver at seat 0 (riders visible from scenario pack); moveRelative moves truck 63.84 blocks/60 ticks (inputInfo.getMovementVector()=(0,0)); setBodyRotation turns truck yaw 0->90; jump() true but truck +0.00; production main.js:166 `currentRiders.map((r) => r.id)` throws 'cannot read property id of undefined' every tick while seated (340 log lines).
- #37 ATTEMPT 1 [L1]: hypothesis 'production pack lacks @minecraft/server-gametest so simulated rider unwrappable' — test copy given server 2.11.0-beta + gametest 1.0.0-beta (run fd60486ab5f349a1b5a012f280213298) -> same TypeError at main.js:166 (170 lines). Refuted.
- #37 L3 instrumentation run b8a348a016cf4e1bb7840aebdaaee7da: in the add-on runtime world.getAllPlayers() contains undefined for SimulatedDriver ('cannot read property name of undefined'); in the scenario pack runtime getRiders() -> SimulatedPlayer. CAUSE: simulated player objects only materialize in the script runtime that spawned them. Next: run scenario driver inside the add-on's runtime (test copy only).
- #37 run 323bd534feb243158c991baf069c0d08 (driver merged into test copy of add-on runtime, server 2.11.0-beta + gametest 1.0.0-beta): 0 errors, steer_angle=1; forward still 63.84 blocks/60 ticks (~1.06 b/tick vs design 0.55 b/tick per ADR-0011); jump() still +0.00 (add-on jump listens to playerButtonInput, which SimulatedPlayer never fires). Awaiting user decisions.
- #36 ATTEMPT 1 [L1]: first container run -> 'Could not connect to Minecraft services. This is required to accept connections in online mode.' then server stopped; fix ONLINE_MODE=false (--network none has no services).
- #36 ATTEMPT 2 [L1]: -> 'Using an allowlist without online authentication can be dangerous and is not allowed.'; also no live output (BDS stdout block-buffered without TTY). Fix: ALLOW_LIST=false + docker run -t.
- ATTEMPT 1 [L1]: Linux Client Smoke Run: harness PASS marker missing (content log ContentLog*.txt in com.mojang/logs stays 0 bytes; marker absent from client stdout). Hypothesis H1 'SIGTERM loses buffered content log' tested by graceful KWin closeWindow (rc 0) -> still 0 bytes. H1 refuted.
