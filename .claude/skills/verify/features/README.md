# Monster Truck Verification Map

This directory is the maintained source for verifying the user-facing behavior of the Minecraft Bedrock Monster Truck Add-on (`blake:monster_truck`). Read this index before driving the add-on, then use the matching feature file as the verification recipe.

## Baseline preconditions

- Ensure Python 3.11+ virtual environment exists at `.venv-testing/` and Node.js dev dependencies are installed (`npm ci`).
- For headless Scenario Runs, Docker Desktop must be running with the pinned dedicated server image (`itzg/minecraft-bedrock-server@sha256:42004bb667915b0accce0aa74d415122ef82cece8abe5ea0085b183bc4ac2df0`).
- For real Client Smoke Runs or Client Input Runs, Minecraft Bedrock for Windows must be installed and closed prior to launch, with the desktop unlocked.
- Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Doctor` and require `"configured": true`.
- Never drive an instance or world that was not initialized or managed by this verification suite.

## Driving conventions

- Start every recipe from the baseline state unless its preconditions specify otherwise.
- In headless Scenario Runs, the Simulated Driver boards the Driver Seat and operates the truck through the production `driverInput` seam.
- In Client Input Runs, hardware keyboard scan codes are injected with an active window focus guard against `Minecraft.Windows.exe`.
- Treat all command flags and test names as literal.
- All runs generate a fresh unique run ID under `dist/bedrock-tests/<run_id>/` and update `dist/bedrock-tests/latest.json`.
- Do not remove proof artifacts during cleanup; logs, reports, and screenshots must be preserved for review.

## Proof and skip reporting

- Capture the user action and the resulting observable state, not merely intermediate setters.
- Scenario proof includes the per-scenario checks and status recorded in `report.json`.
- Client Smoke proof includes captured viewport screenshots in `screenshots/` and fresh content logs.
- Client Input proof includes probe telemetry (`--trace`), WebSocket responses, and exit code `0`.
- Record the run ID, Git revision, working tree state, and add-on version with every verification report.
- Report any unreachable path or unmet precondition immediately; do not report an unexecuted scenario as verified.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order:

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with <harness>` starts with `Preconditions:` and uses labeled bullets that pair each user action with an exact command and observable result.
4. `Gotchas` lists traps that can waste or invalidate a verification run.

Keep implementation details out of the map. Name only user paths, stable handles, required state, commands, and observable proof.

## Features

- [Controlled Auto-Step & Ground Driving](./auto-step-and-driving.md) covers W/S throttle, A/D Coordinated Four-Wheel Steering, 2-block step climbing, and cab sightlines.
- [Handbrake Drift & High-Drop Suspension](./handbrake-and-suspension.md) covers Space handbrake braking and drifting, pneumatic fall immunity, and Crush Stomp.
- [Amphibious Flotation & Shoreline Step-Up](./amphibious-flotation.md) covers water and lava buoyancy, overland cruising speed, thermal shielding, and shoreline bank climbing.
- [Tire Trample & Wood Demolition](./trample-and-demolition.md) covers speed-scaled impact trample, molten tire ignition, wood demolition, and foliage shearing.
- [Sixteen-Color Customization & Vehicle Retrieval](./customization-and-retrieval.md) covers egg randomization, crafted vehicle deployment, Sneak-Dye repainting, and retrieval vs Scrap destruction.
