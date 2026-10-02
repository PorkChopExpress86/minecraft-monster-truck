## Goal
Set up the add-on for Linux development, debug, install, and fully automate in-game testing of the monster truck.
## Now
Slice #34 implemented (uncommitted); awaiting user: rev+install to local client? live --servers deploy? commit?
## Next
1. #35 Linux Client Smoke Run (bedrock_test.py Linux mode + test-addon.sh; bedrock_world.py:27/62 and bedrock_test.py:56 are Windows-only discovery).
2. #36 Scenario Run container bootstrap. 3. #37 Simulated Driver prototype. 4. #38 mechanic scenarios incl. pitch. 5. #39 CI.
6. After #38: trim issues #27-#30 to visual-only residue.
## Constraints
- "if there is something strange then prompt me for input" (re: test thresholds/outcomes)
## Decisions
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
- Desktop: KDE Wayland; spectacle installed; no xdotool/ydotool.
## Done
- Grilling + ADR-0016 + CONTEXT.md terms + GitHub spec #33 and slices #34-#39 — RESULT: created.
- #34 Linux install — RESULT: find_com_mojang_roots finds flatpak root on this machine; install_addon.py --servers creative,survival added (docker cp to /data/{behavior,resource}_packs, world_*_packs.json entry, texturepack-required, confirm restart); .venv-testing/bin/python -m pytest -q -> 120 passed (baseline 116). Live server deploy not yet run.
## Open items
## Failed attempts
