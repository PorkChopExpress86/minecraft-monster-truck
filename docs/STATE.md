## Goal
Set up the add-on for Linux development, debug, install, and fully automate in-game testing of the monster truck.
## Now
Installed: v1.0.13 (c995a7a) on the local client and servers creative, survival, 2026-10-05.
Retro 2 (2026-10-05): .claude/skills/open-items (re-checks STATE notes before reporting), scripts/release.py (rev, install, Installed: line, commit, --push), ./test-addon.sh Client --diag <file>, CODING_STANDARDS 'Tests don't fake what the engine decides', doc test that LINUX_TESTING names every client check.
Client check sneak_during_drop (2026-10-05): #32's 'Shift during a drop' automated; Client 9/9 run 23025b5a; fails with the drop re-seat disabled (run 109563e1). Fall immunity after the exit stays with Scenario two_seat_drop (the client test world is Creative).
## Next
1. User verifies 1.0.13 in game (#32): real Left Shift exits (also after a drop, then no fall immunity), nothing flashes on Space, two players.
2. Manual Proving Ground checks #27/#28/#29/#30; then #31 acceptance evidence; then close parent #24.
## Constraints
- "Keep the version and install with #38" (no rev/install until #38 lands)
- "if there is something strange then prompt me for input" (re: test thresholds/outcomes)
- "do not look into the separt containers" (re: NetherNet errors on minecraft-creative/minecraft-survival)
## Decisions
- DECISION (user, 2026-10-05): Sneak exit over liquid -> 'Nearest dry land (Recommended)': set the player down on the nearest safe block (solid below, 2 air) within a few blocks; none in reach: over lava keep them seated, over water let them swim. Was: teleport onto the roof, which is not solid for players (Client Input Run diag: player falls through, dz -0.80 then dy -1.94).
- DECISION (user, 2026-10-04): #40 implement 'Implement, keep re-seat (Recommended)': disable a seated player's Jump input permission while in a truck, restore it on exit, truck removal and spawn/rejoin; keep the script Space re-seat as a backstop.
- DECISION (user, 2026-10-04): Space-aware re-seat now (a rider who leaves while holding Space/Jump, or whose Jump was held within a few ticks, is put back; other exits on steady ground are Sneak and let go), AND open a ticket to research an engine/entity setting that stops Minecraft's own Space-dismount at the source (the possible one-tick flash, #32).
- DECISION (user, 2026-10-04): Sneak-exit rule: re-seat a rider who leaves only while the truck is falling or within the landing retention window (the #32 engine glitch); on steady ground anyone who leaves is let go; sneaking mid-drop keeps you in until you land. Replaces 'any non-sneaking detachment is undone' (real client never reports Sneak on a riding player).
- DECISION (user, 2026-10-04): real-client tests may inject keyboard/mouse through a user-level uinput virtual device (/dev/uinput has a uaccess ACL for specter; no root, no daemon), with a focus guard: verify Minecraft is the active window before every event, abort otherwise. Local only, never CI. Reverses ADR-0016's 'no input injection' -> record in a new ADR.
- DECISION (user, 2026-10-04): drop the real-client mouse-look check (virtual REL motion never turns the view without a pointer grab; server `steering` scenario already proves look does not steer).
- FACT (user, 2026-10-04): real Left Shift sneaks/dismounts in this launcher; the uinput virtual Shift (left and right) never registers as sneaking (probe `sneaking` 0, standing and riding) although W/A/D/Space/letters and Shift-as-modifier work.
- DECISION (user, 2026-10-03): lava 2-block-bank stall (82 ticks, 0.06 margin, 6a06a68) -> design a proper fix from measured lava vertical retention (multi-tick lift), acceptance: climb within 20 ticks of contact in water and lava, peak <= bank top +0.5, 3x --only passes with margin.
- DECISION (user, 2026-10-03): Shoreline Step-Up bank height is measured above the liquid surface; 1-2 blocks above are climbed, 3+ refused (CONTEXT.md). Production code counted from the truck's submerged block (2-above bank refused) -> fix test-first.
- NOTE: liquid_start release check judges decay on 5-tick average speed; lava shows one reproducible per-tick rise (+0.137 b/tick) after release while the add-on's target speed falls — engine liquid motion noise, recorded in bedrock-physics.md.
- DECISION: ADR-0017 script-driven driving: input_ground_controlled removed; driving.js owns yaw/velocity; impulses divided by retention (ground 0.91*slipperiness*friction_modifier 1.15, water 0.86, lava 0.72, air 0.91 during Shoreline Step-Up window) — user approved Q1-Q6 2026-10-03.
- DECISION: Driving tuning lives in driving.js DRIVING (Bedrock scripts cannot read vehicle.config.json at runtime).
- DECISION: Scenario driver runs inside a Scenario-World-only copy of the add-on BP (entry imports main.js + scenario_driver) on @minecraft/server 2.11.0-beta — simulated players only materialize in the spawning runtime (user approved).
- DECISION: Linux Client Smoke Run verdict = world loaded with our packs (client stdout) + screenshots; gameplay stage not_verified on Linux; all gameplay pass/fail from BDS Scenario Runs — Android-based client never surfaces script console output (user chose option 1).
- DECISION: Gameplay is automated via BDS + GameTest SimulatedPlayer; the real client adds a Client Input Run with uinput key presses (ADR-0019 superseded the earlier 'no Wayland input injection').
- DECISION: Target Minecraft 1.26.52.3 for both client and BDS — client already downloaded; official BDS 1.26.52.3 Linux zip exists.
- DECISION: Run BDS via Docker image itzg/minecraft-bedrock-server (user already uses it) — not a native zip.
- DECISION: Extend scripts/bedrock_test.py with a Linux platform mode + test-addon.sh, same report format — shared stage/report logic.
- DECISION: Client Smoke Run screenshots via spectacle on the live KDE Wayland desktop.
- DECISION: Dedicated Test World created in flatpak com.mojang; "Hiker's Friend" untouched; content_log_file enabled with options.txt backup.
- DECISION: Scenario mechanics 1-9 (auto-step, jump+stomp, shock absorption, flotation+shoreline, trample+molten, demolition+shearing, dye repaint, retrieval/scrap, seats) plus Dynamic Incline Pitch on hills (user: "realistic look where the truck pitches up going up a hill").
- DECISION: Beta APIs experiment allowed in the Scenario World only; production pack stays on stable @minecraft/server 2.10.0.
- DECISION: Spec-defining outcomes hard-coded in tests; tuning values read from vehicle.config.json; anything strange -> prompt user.
- DECISION: Local test-addon.sh modes (Static/Scenarios/Game/All) + GitHub Actions for static + BDS scenarios as last slice.
- DECISION: Glossary terms Scenario Run, Simulated Driver, Scenario World, Client Smoke Run.
- DECISION: Scenario Run uses an ephemeral container monster-truck-scenario-<run-id> (itzg image digest-pinned, VERSION=1.26.52.3, private network, no host ports, mounts dist/bedrock-tests/<run-id>/, removed after) — never touch minecraft-creative/minecraft-survival.
- DECISION: install_addon.py gains opt-in `--servers creative,survival` (copy packs to /data, activate in world, require texture pack, confirm before each container restart); default installs to local client only.
- DECISION: Incline pitch scenario: stepped ramps at 1:2 (~27deg), 1:3 (~18deg), 1:1 (clamp 35deg); assert pitch >0 uphill and <0 downhill within +-5deg of atan(rise/run), returns to 0 on flat, per-tick delta within smoothing bound; strange results -> ask user.
- DECISION: Client Smoke Run showcase adds a camera angle on a truck parked on a slope.
- DECISION: If 1.26.52.3 client fails to launch -> stop and ask user (no fallback to 1.26.45.1); Scenario Runs proceed independently.
- DECISION: incline_pitch band = [min,max] of nominal atan(rise/run) and, when one stair can be straddled alone (run >= 2.25, the front/rear sample span), atan(rise/2.25); widened +-5, clamped 35 — user chose (a).
- DECISION: Aquatic cruising speed must equal measured overland speed (CONTEXT.md 'full overland cruising speed'); scenario asserts pool speed >= 90% of land speed.
## Facts
- Launcher: flatpak io.mrarm.mcpelauncher v1.8.4; client binary via `flatpak run --command=mcpelauncher-client io.mrarm.mcpelauncher` supports `-u minecraft://?load=<world>`.
- com.mojang (Linux): ~/.var/app/io.mrarm.mcpelauncher/data/mcpelauncher/games/com.mojang ; versions in .../data/mcpelauncher/versions/ (1.26.40.5, 1.26.52.3).
- com.mojang root discovery: scripts/addon_packs.py com_mojang_roots() (Windows APPDATA/LOCALAPPDATA, then the Linux mcpelauncher flatpak and native installs).
- Existing user BDS containers (do not touch): minecraft-creative, minecraft-survival (itzg image, VERSION=LATEST, already on bedrock_server-1.26.52.3, network media_proxy, compose dir /mnt/samsung/Docker/MediaServer, volumes media-stack_minecraft_{creative,survival}_data).
- Dynamic Incline Pitch is server-observable via entity property blake:pitch_angle (int, clamp +-35), computed in behavior_packs/MonsterTruck_BP/scripts/kinematics.js.
- Tests: .venv-testing/bin/python -m pytest -q (venv created from requirements-testing.txt); npm run typecheck; one scenario: ./test-addon.sh Scenarios --only <name>.
- Docker servers keep add-ons in /data/behavior_packs/<Name>_BP and /data/resource_packs/<Name>_RP, world lists at /data/worlds/<level-name>/world_*_packs.json, texturepack-required=true already.
- Linux client: `flatpak run --command=mcpelauncher-client io.mrarm.mcpelauncher -dg <data>/versions/1.26.52.3 -m <data>/mods/mcpelauncher-updates/1.26.45.1/x86_64/ -u minecraft://?load=<world folder>` loads the world directly; flatpak run execs into bwrap so Popen.pid is the process-group leader; KWin script closeWindow() exits rc 0; spectacle -b -n -a -e -S captures after KWin activation.
- Linux content logs: com.mojang/logs/ContentLog<date>.txt (created but stays empty).
- Dedicated Test World: com.mojang/minecraftWorlds/addon-test-b06f3b8a-1a26-4f26-a3aa-76c2c480ad35 ; options.txt backup in dist/bedrock-tests/setup/.
- Scenario server: official BDS zip sha256 f6348d84...71c6 cached in dist/bedrock-tests/cache; image itzg/minecraft-bedrock-server@sha256:42004bb6...; needs ONLINE_MODE=false, ALLOW_LIST=false, docker -t (else stdout block-buffered); modules @minecraft/server 2.11.0-beta + @minecraft/server-gametest 1.0.0-beta; spawnSimulatedPlayer(DimensionLocation, name, GameMode) top-level.
- Desktop: KDE Wayland; spectacle installed; no xdotool/ydotool.
## Done
- S and floating-Sneak client checks + dry-land exit (2026-10-05) — RESULT: new checks s_brakes_and_reverses (7.8 blocks back) and sneak_exits_afloat; the latter found the roof set-down drops players into the liquid (run 91df1cec, dy -1.94). Fix per user decision: findDryLanding (nearest dry footing within 4 blocks; lava with none keeps the rider seated, water lets them swim). Client 8/8 aa87fc61, Scenario Run 8b308eb6 22/22, node 63, pytest 221.
- #40 Jump lock (2026-10-04, closed) — RESULT: main.js lockJump/JUMP_LOCK turns a seated player's Jump input permission off and back on (exit, truck gone, rejoin; never for a Jump someone else turned off); re-seat stays. Evidence: Client run 8565956a with re-seat disabled 2/2 (space_keeps_rider seated every tick, 0.00 creep; sneak_dismounts); query shows Jump disabled seated, enabled after Sneak; full Client 5/5 (5754e3a2), Scenario Run fcbe4d4d 22/22.
- Space + Shift exit (2026-10-04) — RESULT: truck_tick.js jumpedRecently ignores Jump while the rider's Jump input is locked (#40: Space cannot dismount then), so Sneak with the handbrake held exits. New client check space_sneak_exits: FAILED without the fix ('still in seat 1', 7b56de4c), full Client 6/6 with it (dfcb6d33), Scenario Run 5e1deef9 22/22, node 61, pytest 219.
- Empty rider slot crash (2026-10-04) — RESULT: getRiders() holes (riders another script runtime spawned) no longer throw at truck_tick.js state.riders, landing.js restoreProtectedRiders, or contact.js rider check; the slot still counts as a seat, so no passenger is promoted to driver. Node tests red->green (3), Scenario Run 5fd93264 22/22.
- One-tick pitch lag (2026-10-04) — RESULT: truck_tick.js computes pitch after stepLanding, so takeoff and landing pick the branch on their own tick; node test red->green ('pitch follows a drop from the tick the drop is first seen'), Scenario Run 7f37c28d 22/22 (incline_pitch 1:2 24.4/-24.8, 1:3 18.5/-21.9, 1:1 35.0/-34.7).
- Client Input Run + Sneak-exit fix (2026-10-04, bb96bde) — RESULT: Client Input Run 701ce9d0 5/5 (W 19.7 blocks, A -67.0, D +69.0, Space 0.00 creep and seated every probe tick, Sneak exits and stays out), Scenario Run 1b703a2d 22/22, pytest 215, node 51. Cause: a riding player never reads isSneaking, so landing.js re-seated every Sneak exit; now re-seats only in drop windows or within 3 ticks of Jump.
- Human-ticket automation (2026-10-04, 655a5c4) — RESULT: crush_stomp/trample spare tamed wolf, bystander player, parked truck; retrieval by real punches, zombie and lightning kills; seat_swap; ACCEPTANCE_COVERAGE rows 6/19/20/23 Automated.
- Open-tickets pass (2026-10-03) — RESULT: closed #26 #38 #39 #25 #33; qualifying run 89a23a43 @ 9413ce1 (Static + 21/21 + Linux Client Smoke Run); CI green.
- ADR-0017 driving + architecture deepening (2026-10-03) — RESULT: run f40f40bf 15/15; deepening commits 39719cd..65478d0, Scenario Runs 15/15 per step.
- Linux tooling #34-#37 (2026-10-01..03) — RESULT: install_addon.py Linux + --servers; Client Smoke Run 137bd73e; Scenario Run container 5a61248a; Simulated Driver seats and drives (1ec3980a).
## Open items
## Failed attempts
- Sneak exit ATTEMPT 1 [L1]: deliberate exit = isSneaking OR inputInfo Sneak button Pressed (landing.js isLeavingDeliberately; node tests red->green) -> real client still re-seats (run 1983fae1). L3 instrumentation (runs b7fb9026, d7c31eb5): while riding, Sneak button reads Released and isSneaking 0; with re-seat disabled the engine dismounts, and for the 5 ticks after, isSneaking 0 and button 0 even with the key held -> no player-side signal of a Sneak exit exists.
- Lava 2-block bank ATTEMPT 1-4 [L1]: single Step-Up impulse tuned 0.85/0.78/0.765/0.75 -> lava clips most lifts to +0.5-0.8 (occasional +3.26 launch); 0.765 never climbed in 160 ticks, 0.75 passed by 0.06. ATTEMPT 5 [L3, measured]: velocity moves before drag; lava retention after the move 0.04-0.32 (water ~0.81) -> held per-tick lift (amphibious.js SHORELINE_LIFT, 6c61353): flush/1/2-above banks in 2/9/14 ticks, peak <=+0.14, 3x identical, full run bf5e9fd8 21/21.
- #32 ATTEMPT 1 [L1]: requestDriverJump stops re-adding an already-seated rider (1.0.4, commit 8609e23) -> user 2026-10-01: 'The player is still clipping out of the vehicle when the truck jumps.' Server-side driver stays listed/linked, 0.00 seat drift every tick (run d0db7b5c...).
