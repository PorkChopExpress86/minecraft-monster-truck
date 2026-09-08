# Automated Windows testing

## Capture diagnostics and stage results

Validation on 2026-09-07: final offline suite passed 70 tests. Full Windows PowerShell 5.1 run `3237dd26326048b9ad4d1ecfd538687d` passed static validation/packaging and all four game stages with exit code 0, five scheduled captures plus a final image, and no content errors or warnings. Its static stage contained 68 tests; the two final focus/fallback regression cases were added afterward and passed in the 70-test offline run. The installed renderer returned uniform HWND frames, so successful captures used the guarded viewport fallback. Frame 001 showed loading; frame 005 was visually inspected and showed the six-color scene. Capture count is evidence collection, not automatic scene recognition. The original intermittent 20-second timeout was not reproduced during the successful instrumented run, so its root cause remains unproven.

The game report has separate `stages.gameplay`, `stages.content_logs`, `stages.screenshots`, and `stages.shutdown` results. A required showcase capture failure or shutdown failure fails the overall run while retaining the actual gameplay checks. Without showcase mode, a missing diagnostic screenshot is recorded but does not fail otherwise successful gameplay/log checks.

The runner first captures the Minecraft HWND without changing focus. Uniform frames are rejected; hardware-accelerated clients can use a fallback viewport capture only with Minecraft foreground before and after capture. That fallback requests foreground once, without attaching input queues. Keep Minecraft restored on an unlocked desktop and avoid competing desktop automation during showcases. Images still require human visual inspection.

Each attempt has a unique directory, a `capture-trace.log` recording the helper's last stage, and an entry with elapsed time and outcome in `capture-attempts.json`. The helper remains bounded to 20 seconds; retries are spaced 15 seconds after an attempt completes. Inspect these files to distinguish helper startup, window lookup, foreground fallback, pixel capture, and PNG saving failures. Shutdown evidence is also saved separately in `shutdown.json`.

The report's `coverage` fields leave visual appearance, audio playback, player input, multiplayer, and other devices marked `not_verified`. Add-on-specific automated assertions do not automatically satisfy those separate acceptance checks. Record their actual evidence in the repository's manual acceptance documentation.

Run `powershell.exe -NoProfile -File .\Test-Addon.ps1` from this repository. Default `All` mode prepares the isolated Python environment, runs static checks, automatically creates and configures a dedicated world when needed, launches it, and checks the runtime harness and fresh content logs. It captures the foreground game window when available and requests normal client shutdown.

Prerequisites are Python 3.11 or later, a licensed and initialized Minecraft Bedrock for Windows client, an unlocked desktop, and Minecraft closed at the start. Finish first-launch/sign-in dialogs before running. Initial preparation downloads dependencies and a pinned world starter. Manual world creation and content-log configuration are handled by the runner.

## Automatic setup

The default command handles setup and testing. To prepare the environment and world without running tests:

```powershell
powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Setup
```

`Setup` creates `.venv-testing`, installs `requirements-testing.txt`, and runs `Bootstrap`. `-Python` selects the Python executable used to create the environment; global Python packages remain unchanged.

Bootstrap discovers the initialized account and creates a new world from Mojang's flat Creative starter. It patches the copied world's NBT name and settings: Creative, Peaceful, commands enabled, multiplayer/LAN broadcasting disabled, and experimental flags cleared. It attaches the add-on packs plus the separate runtime harness and records local paths in ignored `testing/bedrock.local.json`.

While Minecraft is closed, bootstrap enables `content_log_file` if disabled. It backs up the original `options.txt` under `dist/bedrock-tests/setup/<id>/`, changes only that setting's value, and preserves other preferences. A missing or unrecognized setting blocks setup instead of guessing.

Existing configured worlds are reused without replacing terrain or world settings. Generated worlds carry source and ownership markers. Conflicting destinations, ownership, and unrelated active packs are rejected. Deployment refreshes only the runner's three pack directories and activation lists.

The world starter is pinned to Mojang commit `3edc61769233fc6f7c4bb1028c03f465a379523c`, path `app/public/data/content/flatcreativegt.mcworld`, and SHA-256 `b8f1fc6423b88a7010f2ab851b0386d4bef34bc36a80489e9c13870c12f6c328`. Downloads are cached and verified before extraction. The [MIT license](https://github.com/Mojang/minecraft-creator-tools/blob/3edc61769233fc6f7c4bb1028c03f465a379523c/LICENSE.md) is retained in `testing/world-template.LICENSE.txt` and copied into the generated world. See the [pinned artifact](https://github.com/Mojang/minecraft-creator-tools/blob/3edc61769233fc6f7c4bb1028c03f465a379523c/app/public/data/content/flatcreativegt.mcworld).

For diagnosis or an optional existing-world override:

```powershell
.\Test-Addon.ps1 -Mode Doctor
.\Test-Addon.ps1 -Mode Configure -World 'FULL DEDICATED WORLD DIRECTORY' -LogDirectory 'FULL LOG DIRECTORY'
```

Doctor lists GDK and legacy world paths. If several initialized accounts exist, automatic setup refuses an ambiguous selection; Configure selects the intended dedicated world explicitly. Configure preserves `level.dat` and the database, backs up existing empty activation lists, and refuses unrelated active add-ons. A configured world is then reused by normal runs.

## Commands and results

```powershell
.\Test-Addon.ps1                 # Automatic setup, static checks, and live smoke test
.\Test-Addon.ps1 -Mode Setup     # Environment setup followed by Bootstrap
.\Test-Addon.ps1 -Mode Bootstrap # Prepare the dedicated world without running tests
.\Test-Addon.ps1 -Mode Static    # No Minecraft launch or world changes
.\Test-Addon.ps1 -Mode Game      # Live smoke only; static checks not implied
.\Test-Addon.ps1 -Mode Doctor    # Read-only installation/world discovery
```

Every invocation writes `dist/bedrock-tests/<run-id>/report.json` and updates `dist/bedrock-tests/latest.json`. Static runs retain command output and pytest JUnit XML; live runs retain fresh content-log evidence and screenshots of the game viewport. Capturing brings Minecraft to the foreground. Mode and per-stage results distinguish a static-only pass from a full pass.

This project's `showcase` mode creates one truck in each of six colors, verifies its color property/components/seats, hides the HUD, and cycles three camera angles. The runner captures frames every 15 seconds into `screenshots/<frame>/minecraft.png`, observes for at least `observe_seconds`, and requires two successful captures. Showcase trucks remain in the dedicated world and are removed by their test-only tag before the next display is created. With `showcase` disabled, the ordinary smoke entity is cleaned up before PASS. Inspect captured frames before selecting images for the README; a saved frame alone is not a visual assertion.

Exit codes: `0` successful requested operation, `1` failed checks/runtime error/timeout, `2` setup blocked, `130` interrupted. Doctor, Configure, and Bootstrap report their operation separately and do not claim test success. Missing content logs or a missing matching result cannot pass. All fresh errors and warnings fail the smoke test except its own valid structured result emitted at warning level. When PASS is visible during execution, the runner waits the configured settling period. This Windows client can buffer logs until shutdown, so the runner also collects final flushed output after normal close; a real matching result and clean final logs are required even if the streaming wait expired. A buffered run may therefore use the entire configured runtime window.

An existing running Minecraft client blocks deployment. The runner closes only a client it launched, using a normal window-close request; inability to close it blocks successful completion. It never silently terminates a personal game session. Avoid using Minecraft during a test run.

The compatibility command `python scripts/test_in_game.py` runs the verified game test. Its former `--dry-run` is now read-only Doctor discovery; it does not deploy packs or claim a game pass.

## Adapting another add-on

The personal `minecraft-addon-testing` skill scaffolds repository-owned code. Its files are ordinary source: they run without Codex and can be versioned and changed in each repository. Skill updates do not overwrite existing repository copies.

- `testing/bedrock.json`: pack paths, entity identifier, unique harness UUIDs, stable Script API version, expected components/seats, command arrays, and time limits. `{python}` selects the isolated interpreter and `{report_dir}` selects the current evidence directory. Commands execute directly without a shell; list each argument separately.
- `testing/harness/assertions.js`: add-on-specific runtime assertions. Return `{ checks, cleanup }` (a Promise is also supported), with at least one meaningful check; throw on failure. Ordinary smoke runs clean up before PASS. A showcase implementation must position its camera and remove its previously tagged scene on the next run, since cleanup is deferred for photography. Do not put this harness into the distributed behavior pack.
- `scripts/bedrock_test.py` and `Test-Addon.ps1`: editable orchestration and Windows entrypoint.
- `scripts/bedrock_world.py`: pinned world download, safe extraction, copied-world NBT customization, and the backed-up content-log setting change.
- `requirements-testing.txt`: dependencies for that repository's actual static commands. Keep its pins aligned with verified tooling.

For this repository, static checks run pytest, `scripts/validate_project.py`, and `scripts/package_addon.py`. Runtime assertions check spawning `blake:monster_truck`, health/rideable components, and two seats. Rendering quality, audio, driving, and obstacle behavior remain in [the proving-ground checklist](PROVING_GROUND.md).

## Compatibility evidence

The harness requests stable `@minecraft/server` 2.0.0, which provides the required entity and world-load APIs. See Microsoft's [Script API versioning contract](https://learn.microsoft.com/en-us/minecraft/creator/documents/scripting/versioning?view=minecraft-bedrock-stable) and the [2.0.0 versioned type definitions](https://registry.npmjs.org/@minecraft/server/-/server-2.0.0.tgz). On 2026-09-07, the default All command completed locally with exit code 0: 58 tests, validation, packaging, all six live color/component/two-seat checks, and seven screenshots passed with zero content errors or warnings. The world was created automatically and the client closed normally; other client installations still require their own live validation.

Microsoft documents [GDK data/log locations](https://learn.microsoft.com/en-us/minecraft/creator/documents/gdkpcprojectfolder?view=minecraft-bedrock-stable), [content-log output](https://learn.microsoft.com/en-us/minecraft/creator/documents/scripting/debugging-scripts?view=minecraft-bedrock-stable), and [the local-world load URI](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/deep-links?view=minecraft-bedrock-stable). The runner percent-encodes the world directory name as the URI query value and verifies the result independently because handlers can fail silently.

## Heavy-duty behavior coverage

The add-on harness tests 1,000 maximum health, a real melee hit reduced from 40 to 10 damage, ignored fall damage, no damage to a nearby pig while parked, and a mob killed when the actual truck receives horizontal movement impulses. These tests exercise production entity components; the harness does not apply damage to the target mob itself. Static checks also guard player/vehicle/tamed-pet exclusions and projectile/explosion reduction settings. Player driving remains a separate input check.

The heavy-duty All run `12393dfe1fdd487fb4bdebe991aae73c` passed 59 static tests, packaging, and all runtime checks with zero content errors/warnings. A temporary two-block stone ledge was also traversed using horizontal impulses and its original blocks restored. This verifies engine stepping independently of keyboard input.
