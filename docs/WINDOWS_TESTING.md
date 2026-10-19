# Automated Windows testing

## Capture diagnostics and stage results

Validation on 2026-09-07: final offline suite passed 70 tests. Full Windows PowerShell 5.1 run `3237dd26326048b9ad4d1ecfd538687d` passed static validation/packaging and all four game stages with exit code 0, five scheduled captures plus a final image, and no content errors or warnings. Its static stage contained 68 tests; the two final focus/fallback regression cases were added afterward and passed in the 70-test offline run. The installed renderer returned uniform HWND frames, so successful captures used the guarded viewport fallback. Frame 001 showed loading; frame 005 was visually inspected and showed the six-color scene. Capture count is evidence collection, not automatic scene recognition. The intermittent 20-second timeout was traced on 2026-10-19 (below).

The game report has separate `stages.gameplay`, `stages.content_logs`, `stages.screenshots`, and `stages.shutdown` results. A required showcase capture failure or shutdown failure fails the overall run while retaining the actual gameplay checks. Without showcase mode, a missing diagnostic screenshot is recorded but does not fail otherwise successful gameplay/log checks.

The runner first captures the Minecraft HWND without changing focus. Uniform frames are rejected; hardware-accelerated clients can use a fallback viewport capture only with Minecraft foreground before and after capture. That fallback requests foreground once, without attaching input queues. Keep Minecraft restored on an unlocked desktop and avoid competing desktop automation during showcases. Images still require human visual inspection.

Each attempt has a unique directory, a `capture-trace.log` listing every stage reached with the seconds since the capture began (`capture stage: grab_pixels +0.15s`), and an entry with elapsed time and outcome in `capture-attempts.json`. Captures are spaced 15 seconds after an attempt completes. Shutdown evidence, including how long the close took, is saved separately in `shutdown.json`.

### Why captures timed out (measured 2026-10-19)

Captures used to run in a fresh Python helper process with a 20 second limit. On this 4-core laptop, with the CPU at 100% (another project's test pools, a Scenario Run in Docker), the helper spent most of that limit before touching the game: its first stage printed 1.9 to 19.3 s after it was started, importing Pillow took another 0.4 to 7.3 s, and 6 attempts printed nothing in 20 s. Once a helper reached `find_window`, the rest took 1.4 to 4.2 s; `grab_pixels` itself took 0.02 to 0.6 s. So the stage a timed-out trace ended on (`grab_pixels` in run `43a2463f`, `import_imagegrab` in `08e233d6`) was only where the clock ran out. In 5 baseline runs (`9dafc68d`, `d3bb8e31`, `eea78c71`, `3a5e0c74`, `1a8021e8`) 16 of 26 attempts timed out and 4 runs failed the screenshot stage.

The runner now captures in its own process, as the Client Input Run already did, so no capture pays for interpreter start-up or the Pillow import. Under the same load, 5 runs (`298c7df7`, `fc94fdcf`, `81a13a58`, `af2d0197`, `be8f2564`) all passed: 36 of 37 attempts saved an image, each in 0.5 to 7.0 s. A capture can still fail when another window holds the foreground: this renderer returns a uniform frame for the window itself, so every saved image comes from the foreground fallback, and Windows refuses a background process's request to bring Minecraft forward. That refusal was the one failure in those 37 attempts, and 3 of the 26 baseline ones. Keep the desktop untouched during a run.

Close times in those 10 runs were 5.7 to 13.2 s. The over-30 s close of run `43a2463f` did not recur, so its cause is not established. It came right after that run's final capture was killed at the 20 s limit, on the same loaded PC. The limit stays at 30 s, and `shutdown.json` now records each close's duration.

The report's `coverage` fields leave visual appearance, audio playback, player-input behavior and feel, multiplayer, and other devices marked `not_verified`. The smoke run never generates keyboard input; the Client Input Run below does. Record those observations with the manual Proving Ground checklist.

Run `powershell.exe -NoProfile -File .\Test-Addon.ps1` from this repository. Default `All` mode prepares the isolated Python environment, runs static checks, automatically creates and configures a dedicated world when needed, launches it, and checks the runtime harness and fresh content logs. It captures the foreground game window when available and requests normal client shutdown.

Prerequisites are Python 3.11 or later, a licensed and initialized Minecraft Bedrock for Windows client, an unlocked desktop, and Minecraft closed at the start. Finish first-launch/sign-in dialogs before running. Initial preparation downloads dependencies and a pinned world starter. Manual world creation and content-log configuration are handled by the runner.

## Automatic setup

The default command handles setup and testing. To prepare the environment and world without running tests:

```powershell
powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Setup
```

`Setup` creates `.venv-testing`, installs `requirements-testing.txt`, and runs `Bootstrap`. `-Python` selects the Python executable used to create the environment; global Python packages remain unchanged.

Bootstrap discovers the initialized account and creates a new world from Mojang's flat Creative starter. It patches the copied world's NBT name and settings: Creative, Peaceful, commands enabled, multiplayer/LAN broadcasting disabled, and experimental flags cleared. It attaches the add-on packs plus the separate runtime harness and records local paths in ignored `testing/bedrock.local.json`.

While Minecraft is closed, bootstrap enables `content_log_file`. It backs up the original `options.txt` under `dist/bedrock-tests/setup/<id>/`, changes only that setting's value, and preserves other preferences. Bedrock 1.26.51 can omit a disabled key, so the runner adds the known setting after backup when absent; an existing malformed value still blocks setup.

Existing configured worlds are reused without replacing terrain or world settings. Generated worlds carry source and ownership markers naming the main checkout, so every git worktree of the repository runs in the same world and writes its own `testing/bedrock.local.json` on first run. Conflicting destinations, ownership, and unrelated active packs are rejected. Deployment refreshes only the runner's three pack directories and activation lists. The dedicated-world copies receive deterministic test-only pack UUIDs so an older globally installed development pack with the release UUID cannot shadow current repository content; distributable manifests are not changed.

The world starter is pinned to Mojang commit `3edc61769233fc6f7c4bb1028c03f465a379523c`, path `app/public/data/content/flatcreativegt.mcworld`, and SHA-256 `b8f1fc6423b88a7010f2ab851b0386d4bef34bc36a80489e9c13870c12f6c328`. Downloads are cached and verified before extraction. The [MIT license](https://github.com/Mojang/minecraft-creator-tools/blob/3edc61769233fc6f7c4bb1028c03f465a379523c/LICENSE.md) is retained in `testing/world-template.LICENSE.txt` and copied into the generated world. See the [pinned artifact](https://github.com/Mojang/minecraft-creator-tools/blob/3edc61769233fc6f7c4bb1028c03f465a379523c/app/public/data/content/flatcreativegt.mcworld).

For diagnosis or an optional existing-world override:

```powershell
.\Test-Addon.ps1 -Mode Doctor
.\Test-Addon.ps1 -Mode Configure -World 'FULL DEDICATED WORLD DIRECTORY' -LogDirectory 'FULL LOG DIRECTORY'
```

Doctor lists GDK and legacy world paths. If several initialized accounts exist, automatic setup refuses an ambiguous selection; Configure selects the intended dedicated world explicitly. Configure preserves `level.dat` and the database, backs up existing empty activation lists, and refuses unrelated active add-ons. A configured world is then reused by normal runs.

## Commands and results

```powershell
.\Test-Addon.ps1                 # Automatic setup, static checks, Scenario Runs, and live smoke test
.\Test-Addon.ps1 -Mode Setup     # Environment setup followed by Bootstrap
.\Test-Addon.ps1 -Mode Bootstrap # Prepare the dedicated world without running tests
.\Test-Addon.ps1 -Mode Static    # Script API type check, pytest, validation, packaging; no Minecraft launch
.\Test-Addon.ps1 -Mode Scenarios # Headless Scenario Runs only (Docker Desktop)
.\Test-Addon.ps1 -Mode Scenarios -Only flotation_water,handbrake
.\Test-Addon.ps1 -Mode Game      # Live smoke only; static checks not implied
.\Test-Addon.ps1 -Mode Client    # Client Input Run: real key presses in the real client (local only, not in All)
.\Test-Addon.ps1 -Mode Client -Only sneak_dismounts -Trace
.\Test-Addon.ps1 -Mode Doctor    # Read-only installation/world discovery
```

Bootstrap, Static, and All also install the dev tooling in `package.json` (Node.js and npm required) and enable the pre-commit hook in `.githooks/`, which Git for Windows runs through its bundled bash. Run pytest directly with `$env:REQUIRE_NODE='1'; .\.venv-testing\Scripts\python.exe -m pytest -q`. Tests that need Linux (`/proc`, the uinput event layout) skip with a reason.

### Scenario Runs

Scenario Runs work as described in [Linux testing](LINUX_TESTING.md#scenario-runs), through Docker Desktop with the Linux engine; the dedicated server container bind-mounts the run directory from this drive. `docker run` has a 120-second limit, so pull the pinned image named by `scenario_server.image` in `testing/bedrock.json` once with `docker pull` before the first run. Full run `8daa081332dc45e19282ba8de88ab671` passed 22/22 on this machine.

### Client Input Run

The checks, probe, and run options are shared with Linux and described in [Linux testing](LINUX_TESTING.md#client-input-run). On Windows:

- Keys go in through `SendInput` as hardware scan codes (`scripts/windows_input.py`). Before every key the focus guard checks that the foreground window belongs to `Minecraft.Windows.exe`; any other window ends the run with every key released. An injected Shift never registers as Sneak here either, so the run binds Sneak to K, as on Linux.
- The client signs in and loads the world for about a minute after its window appears. Nothing reports when the world is ready, so the runner retries opening chat with `/` until the Chat and Commands screen appears (`/` does nothing on the menus).
- `/` opens chat with the text box already focused. Pressing Enter there would send a lone `/`, so the runner types `connect` straight away.
- Screenshots are taken in the runner process, the same `WindowsClient.capture` the smoke run uses (see "Why captures timed out" above).

Full run `b6ac98092dcc41b99fa26e6aaf171759` passed all 11 checks. Leave the keyboard and mouse alone while it runs, and run it in the foreground with nothing else running.

Every invocation writes `dist/bedrock-tests/<run-id>/report.json` and updates `dist/bedrock-tests/latest.json`. Static runs retain command output and pytest JUnit XML; live runs retain fresh content-log evidence and screenshots of the game viewport. Capturing brings Minecraft to the foreground. Mode and per-stage results distinguish a static-only pass from a full pass.

This project's `showcase` mode creates one truck for every color in the Sixteen-Color Palette, verifies explicit color precedence, properties, components, and seats, then checks bare/default and randomized spawn semantics. It then seats the player in the red truck and cycles the rider's own view with the HUD on (what a seated player sees, mount hearts included) for 40 seconds, then four camera angles with the HUD hidden, 20 seconds each. The runner captures frames every 15 seconds into `screenshots/<frame>/minecraft.png`, observes for at least `observe_seconds`, and requires two successful captures. Showcase trucks remain in the dedicated world and are removed by their test-only tag before the next display is created. With `showcase` disabled, the ordinary smoke entity is cleaned up before PASS. Inspect captured frames before selecting images for the README; a saved frame alone is not a visual assertion.

Exit codes: `0` successful requested operation, `1` failed checks/runtime error/timeout, `2` setup blocked, `130` interrupted. Doctor, Configure, and Bootstrap report their operation separately and do not claim test success. Missing content logs or a missing matching result cannot pass. All fresh errors and warnings fail the smoke test except its own valid structured result emitted at warning level. When PASS is visible during execution, the runner waits the configured settling period. This Windows client can buffer logs until shutdown, so the runner also collects final flushed output after normal close; a real matching result and clean final logs are required even if the streaming wait expired. A buffered run may therefore use the entire configured runtime window.

An existing running Minecraft client blocks deployment. The runner closes only a client it launched, using a normal window-close request; inability to close it blocks successful completion. It never silently terminates a personal game session. Avoid using Minecraft during a test run.

The compatibility command `python scripts/test_in_game.py` runs the verified game test. Its former `--dry-run` is now read-only Doctor discovery; it does not deploy packs or claim a game pass.

## Adapting another add-on

The personal `minecraft-addon-testing` skill scaffolds repository-owned code. Its files are ordinary source: they run without Codex and can be versioned and changed in each repository. Skill updates do not overwrite existing repository copies.

- `testing/bedrock.json`: pack paths, entity identifier, unique harness UUIDs, stable Script API version, expected components/seats, command arrays, and time limits. `{python}` selects the isolated interpreter and `{report_dir}` selects the current evidence directory. Commands execute directly without a shell; list each argument separately.
- `testing/harness/assertions.js`: add-on-specific runtime assertions. Return `{ checks, cleanup }` (a Promise is also supported), with at least one meaningful check; throw on failure. Ordinary smoke runs clean up before PASS. A showcase implementation must position its camera and remove its previously tagged scene on the next run, since cleanup is deferred for photography. Do not put this harness into the distributed behavior pack.
- `scripts/bedrock_test.py` and `Test-Addon.ps1`: editable orchestration and Windows entrypoint.
- `scripts/bedrock_client.py`: the game client behind one interface: `WindowsClient` (process check, `minecraft://` launch, content-log verdict, screenshots, normal close) and `LauncherClient` for Linux.
- `scripts/bedrock_world.py`: pinned world download, safe extraction, copied-world NBT customization, the backed-up content-log setting change, and claiming (configure/bootstrap) and deploying into the Dedicated Test World.
- `requirements-testing.txt`: dependencies for that repository's actual static commands. Keep its pins aligned with verified tooling.

For this repository, static checks run pytest, `scripts/validate_project.py`, and `scripts/package_addon.py`. Runtime assertions check spawning `blake:monster_truck`, health/rideable components, and two seats. Driving, steering, and obstacle behavior are asserted by Scenario Runs and, with real key presses, by the Client Input Run below; rendering quality, audio, and driving feel remain in [the proving-ground checklist](PROVING_GROUND.md).

## Compatibility evidence

The current production and harness packs request stable `@minecraft/server` 2.10.0 so cancellable before-hurt and cross-device player-button events are mandatory. See Microsoft's [Script API versioning contract](https://learn.microsoft.com/en-us/minecraft/creator/documents/scripting/versioning?view=minecraft-bedrock-stable) and the [2.10.0 versioned type definitions](https://registry.npmjs.org/@minecraft/server/-/server-2.10.0.tgz). The historical 2026-09-07 pass used 2.0.0 and therefore does not qualify the current mechanics. Other client installations require their own live validation.

Microsoft documents [GDK data/log locations](https://learn.microsoft.com/en-us/minecraft/creator/documents/gdkpcprojectfolder?view=minecraft-bedrock-stable), [content-log output](https://learn.microsoft.com/en-us/minecraft/creator/documents/scripting/debugging-scripts?view=minecraft-bedrock-stable), and [the local-world load URI](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/deep-links?view=minecraft-bedrock-stable). The runner percent-encodes the world directory name as the URI query value and verifies the result independently because handlers can fail silently.

## Heavy-duty behavior coverage

The add-on harness tests 1,000 maximum health, a real melee hit reduced from 40 to 10 damage, ignored fall damage, fire/lava hazard damage, no damage to a nearby pig while parked, and a mob killed through the scripted Speed-Scaled Tire Trample path. Static checks guard the script-driven driving model (throttle, A/D steering, Handbrake Drift), the 3-block-drop Crush Stomp threshold, protected-target exclusions, damage scaling, spawn sources, retrieval/Scrap ownership, and projectile/explosion reduction settings. Driver Seat Spacebar input and rider retention are automated: the Client Input Run's `space_keeps_rider` holds the real Space key and requires the player in the Driver Seat on every tick the probe sees, and the `handbrake` scenario checks the seat on every tick of a drift. Visible clearance and subjective driving feel remain manual Proving Ground checks.

### The parked-pig check (run `1ac43d79`)

"parked truck leaves mob unharmed" failed once, in run `1ac43d79`, with only "Parked truck damaged a mob": the check did not say whether the pig was gone or hurt. It now says which, with the pig's health and every hurt to it while the truck is parked (cause, damage, damaging entity, the pig's position, the truck's position and velocity). Its pass line reports the parked truck's peak speed, read as `truck_tick.js` reads it, and the pig's nearest approach.

Measured on 2026-10-19, it did not fail again. It passed 18 real-client runs in a row, all with the CPU at 93 to 100%. The 8 runs that measured it (`0f48866d`, `46ac05de`, `1ca31353`, `2f91fc37`, `abc2f621`, `b322bf26`, `c6065c1f`, `8a40aa2f`) read a peak truck speed of 0.000 blocks/tick and the pig at 1.50 blocks every tick. The add-on harms a mob only through Tire Trample (above 0.08 blocks/tick) or a Crush Stomp landing. Neither can fire on a truck that never moves, so the add-on is not the likely cause. That is inferred: the failing run's own state was not recorded. The pig spawns with 0.075 blocks of its box inside the truck's (2.25 wide, 1.5 from its middle), but that never moved either of them. One difference is visible in that run's screenshots: the player was seated in a truck left in the world. A passing run (`4c3e577a`) shows the player seated too, so that alone does not explain it. Whether this is a product or a harness defect stays open until the check fails again; the next failure will name the cause.

The heavy-duty All run `12393dfe1fdd487fb4bdebe991aae73c` passed 59 static tests, packaging, and all runtime checks with zero content errors/warnings. A temporary two-block stone ledge was also traversed using horizontal impulses and its original blocks restored. This verifies engine stepping independently of keyboard input.
