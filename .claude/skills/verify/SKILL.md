---
name: verify
description: "Verify the Minecraft Bedrock Monster Truck add-on via static checks, headless GameTest scenarios, real-client smoke tests, and client input runs."
---

# Monster Truck Verification Skill

This skill provides the automated and repeatable verification harness for the Minecraft Bedrock Monster Truck Add-on (`blake:monster_truck`). It covers static and behavioral validation, headless GameTest Scenario Runs on a dedicated server container, live Client Smoke Runs in the real Bedrock client with screenshot capture, and local Client Input Runs using virtual keystroke injection.

## Launch

The verification environment requires Python 3.11+ and Node.js 20+. Docker Desktop is required for headless Scenario Runs.

1. **Bootstrap / Setup**:
   To initialize the testing virtual environment and register or verify the Dedicated Test World:
   ```powershell
   powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Setup
   ```
   Or on Linux:
   ```bash
   ./test-addon.sh Setup
   ```
   - Installs Python dependencies from `requirements-testing.txt` into `.venv-testing`.
   - Runs `npm ci --silent` if `node_modules` is absent to install dev dependencies for TypeScript checking.
   - Discovers or creates the Dedicated Test World (`addon-test-b06f3b8a-1a26-4f26-a3aa-76c2c480ad35`), enables `content_log_file` in client options, and records configuration in `testing/bedrock.local.json`.

2. **Readiness**:
   - The environment is ready when `testing/bedrock.local.json` exists, `.venv-testing/Scripts/python.exe` (or `.venv-testing/bin/python` on Linux) exists, and `Test-Addon.ps1 -Mode Doctor` reports `"configured": true`.

3. **Teardown**:
   - Headless scenario server containers terminate and self-remove at the end of each run.
   - For live client runs, the runner sends a graceful window-close request to the Minecraft client it launched. It never terminates unrelated game sessions.

## Doctor

Run the read-only diagnostic check before driving the add-on:

```powershell
powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Doctor
```
Or on Linux:
```bash
./test-addon.sh Doctor
```

**Doctor verifies**:
- Discovers Minecraft Bedrock user directories, world directories, and log locations.
- Confirms whether `testing/bedrock.local.json` is configured.
- Exits with status `DIAGNOSTIC` and exit code `0` on success.
- If unconfigured, run `-Mode Setup` or `-Mode Bootstrap` before attempting live client runs.

## Drive

Depending on the feature and acceptance criteria being verified, drive the add-on through one of four harnesses:

### 1. Headless Scenario Runs (Authoritative Gameplay)
Runs GameTest scenarios with a Simulated Driver operating the truck through the production input seam (`driverInput`) on a disposable Bedrock Dedicated Server container.

```powershell
# Run all 22 scenarios
powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios

# Run specific scenarios (e.g. auto_step, handbrake, flotation_water)
powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only auto_step
powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only flotation_water,flotation_lava
```
Or on Linux:
```bash
./test-addon.sh Scenarios --only auto_step
```

Available scenarios in `testing/bedrock.json`:
`smoke`, `seats`, `auto_step`, `steering`, `handbrake`, `crush_stomp`, `shock_absorption`, `flotation_water`, `flotation_lava`, `trample`, `demolition`, `foliage_shearing`, `dye_repaint`, `retrieval`, `incline_pitch`, `spawn_sources`, `two_seat_drop`, `liquid_start_water`, `liquid_start_lava`, `shoreline_wall`, `shoreline_step`, `seat_swap` (plus opt-in `retrieval_full_health`).

### 2. Static & Behavioral Suite
Runs Script API TypeScript type checking, Node.js behavior unit tests (`node --test`), the full pytest suite (242+ tests), project validator, and package bundler.

```powershell
powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Static
```
Direct pytest execution:
```powershell
$env:REQUIRE_NODE='1'; .\.venv-testing\Scripts\python.exe -m pytest -q
```

### 3. Client Smoke Run (Visual Review & Content Logs)
Deploys the add-on with deterministic test-only pack UUIDs into the Dedicated Test World, launches the real Bedrock client, runs runtime assertions in `testing/harness/assertions.js`, captures 16-color showcase screenshots into `screenshots/`, and validates clean content logs.

```powershell
powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Game
```
*Note*: Minecraft must be closed before launching, and the desktop must remain unlocked and in the foreground.

### 4. Client Input Run (Real Key Injections & Dismounts)
Injects real hardware keyboard scan codes (`scripts/windows_input.py` on Windows / `uinput` on Linux) into `Minecraft.Windows.exe` behind a foreground focus guard, asserting outcomes over a WebSocket probe.

```powershell
powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Client -Only sneak_dismounts -Trace
```
*Note*: Client Input Run takes over the physical keyboard and mouse; keep hands off input and do not lock the screen while running.

## Evidence

Every run writes structured evidence to a unique directory: `dist/bedrock-tests/<run_id>/` and updates `dist/bedrock-tests/latest.json`.

**Captured artifacts include**:
- `report.json`: Contains `run_id`, `mode`, start and finish UTC timestamps, exit code, per-stage status, and the authoritative `evidence` object:
  - `revision`: Git HEAD SHA at test time.
  - `working_tree_clean`: Boolean cleanliness status.
  - `changed_files`: List of modified files.
  - `addon_version`: Add-on version string from `MonsterTruck_BP/manifest.json`.
  - `game_versions`: Linux client and dedicated server versions.
- `static-1.log`, `static-2.log`, `static-3.log`: Full stdout/stderr from pytest, validator, and packager.
- `pytest.xml`: JUnit XML test report.
- `capture-trace.log` and `capture-attempts.json`: Screenshot timings and retry attempts.
- `screenshots/<frame>/minecraft.png`: High-resolution game viewport screenshots.
- Bedrock content logs: Collected from `AppData\Roaming\Minecraft Bedrock\logs` to verify absence of runtime script errors or content warnings.

**Proof standards**:
- A green Scenario Run verifies physics, Script API rules, and simulated player driving, but does NOT prove physical keyboard mapping or engine dismount quirks.
- For physical input, key mapping, or dismount bug verification, run `-Mode Client`.
- Evidence files in `dist/bedrock-tests/<run_id>/` are preserved and survive teardown.

## Cleanup

- **Containers**: Disposable Bedrock Dedicated Server Docker containers are automatically destroyed after each Scenario Run.
- **Client Processes**: The runner cleanly closes the Minecraft client it opened via window-close messages. It never terminates external or unmanaged instances.
- **Dedicated World**: The Dedicated Test World reuses its directory without corrupting player saves, and showcase vehicles are cleared by their test tag on each run.
- **Evidence Preservation**: Cleanup never deletes `dist/bedrock-tests/`. Proof reports, logs, and screenshots remain available indefinitely for auditing.

## Helpers

All runner scripts are executable and maintained in the repository:
- `.\Test-Addon.ps1`: Windows PowerShell wrapper supporting `-Mode (Doctor|Setup|Bootstrap|Static|Scenarios|Game|Client|All)`, `-Only`, `-Trace`, `-Diag`.
- `./test-addon.sh`: Linux Bash equivalent for CLI and CI runs.
- `scripts/bedrock_test.py`: Core cross-platform test orchestrator.
- `scripts/validate_project.py`: Project schema, manifest UUIDs, and texture consistency validator.
- `scripts/package_addon.py`: Builds `.mcpack` and `.mcaddon` packages into `dist/`.
- `scripts/release.py`: Reversioning and installation manager.
