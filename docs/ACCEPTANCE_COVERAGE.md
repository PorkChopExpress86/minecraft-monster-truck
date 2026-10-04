# Acceptance Coverage Matrix (#24)

This matrix maps every user story and testing decision of spec #24 to the check that covers it today: an automated **Scenario Run** on the production path, a supporting node behaviour or static test, a manual [Proving Ground](PROVING_GROUND.md) observation, a supersession by an approved ADR, or an explicit unresolved gap. It reflects the repository as of ADR-0017 (script-driven driving) and ADR-0018 (Linux qualifying run). A row that names only node or static tests is **not** production-path evidence; those tests run the add-on's own scripts against a fake world, not the Bedrock engine.

## Acceptance boundary decisions

The original spec required an automated real-driver/Spacebar Suspension Jump test, one uninterrupted Windows run, and a 0.55 cruising-speed ceiling. The maintainer approved the following changes to that boundary. Anything not covered by these decisions stays an open gap below.

| Decision | What changed | Rationale |
|---|---|---|
| [ADR-0016](adr/0016-headless-scenario-runs-with-simulated-driver.md) | Gameplay is verified by headless **Scenario Runs**: a GameTest **Simulated Driver** boards the **Driver Seat** of the packaged add-on in a **Scenario World** on a disposable dedicated server and drives it through the add-on's real input path (the `driverInput` seam, amended by ADR-0017). The real-client **Client Smoke Run** never generates input; it proves the packs load and captures screenshots for human review. | Keyboard injection into the real client needs a privileged Wayland daemon and is not repeatable; scripted impulses would bypass the input path. This resolves #26's "automated real-driver/Spacebar requirement vs manual input" question: automation drives through the production input seam, and only the physical key mapping (which key produces which input) is left to manual observation. |
| [ADR-0017](adr/0017-script-driven-steering-and-handbrake.md) | The add-on drives the truck itself. W/S throttle, brake, reverse; A/D steer (**Coordinated Four-Wheel Steering**); the mouse only looks. The **Suspension Jump is retired**; holding Space is the **Handbrake Drift**. **Crush Stomp** fires on landing from a drop of 3 or more blocks. Top speed is 1.1 blocks/tick (about 22 blocks/s) on land, water, and lava. | Engine ground control steered by look direction and dismounted on Space (#32). Scripts can read only Jump and Sneak, so the jump could not be rebound. Stories 1-5 and the jump testing decision are superseded, and the 0.55 cruising-speed ceiling no longer governs speed. |
| [ADR-0018](adr/0018-linux-qualifying-acceptance-run.md) | A qualifying automated result is three verdicts on one revision and packaged add-on version: Static, a full Scenario Run, and a Linux Client Smoke Run (`./test-addon.sh All` runs all three under one run identifier). The Windows runner is no longer required. | Development moved to Linux, where the client never surfaces script output, so the Scenario Run is the gameplay authority. Manual Proving Ground observations remain required. |

## Legend

| Status | Meaning |
|---|---|
| **Automated** | A Scenario Run asserts the story's core outcome on the production path. |
| **Automated (partial)** | A Scenario Run asserts part of the story; the remainder is only node/static-tested or manual (named in the row). |
| **Supporting only** | Covered by node behaviour tests (`tests/js/*.test.mjs`, production scripts against a fake world) or static pytest checks, with no production-path assertion. |
| **Manual** | Only a human Proving Ground observation can verify it. |
| **Superseded** | Replaced by an approved ADR; the row names the replacement. |
| **Gap** | No adequate check exists; left open. |

Scenario names refer to `testing/scenarios/scenarios.js` (configured in `testing/bedrock.json` `scenario_server.scenarios`). "PG n" is item n of the [Proving Ground checklist](PROVING_GROUND.md). "Windows harness" is `testing/harness/assertions.js`, which asserts only in a Windows Client Smoke Run and is not part of the ADR-0018 qualifying run.

## User stories

| # | Story (short) | Status | Production-path automated check | Supporting checks | Manual | Residue / gap |
|---|---|---|---|---|---|---|
| 1 | Space triggers one immediate Suspension Jump | Superseded (ADR-0017) | Replacement: `handbrake` asserts held Space (handbrake) stops the truck within 30 ticks without turning, holds a parked truck against W, drifts (slip >= 10 degrees) while steering, and regains grip (slip <= 3 degrees) within 12 ticks of release. | `main.test.mjs` "Jump launches nothing"; `truck_tick.test.mjs` "holding Jump is the handbrake and never launches the truck"; `test_suspension.py` asserts jump helpers are removed. | PG 17 | Handbrake Drift feel. |
| 2 | Jump preserves forward momentum across ravines | Superseded (ADR-0017) | None; there is no jump to cross ravines with. | — | — | — |
| 3 | 1.2 s pneumatic recharge enforced | Superseded (ADR-0017) | None; no launch impulse exists to rate-limit. | `truck_tick.test.mjs`: held Jump produces no vertical impulse. | — | — |
| 4 | Space never ejects the driver | Superseded (ADR-0017); replacement is manual | Server-side only: `handbrake` retention tracker asserts the driver stays listed, linked, and within 1 block of the seat on every tick of a drift. | — | PG 17 | Whether Space dismounts on the real client (#32) can only be seen in the client (`docs/LINUX_TESTING.md` blind spots). |
| 5 | Crush Stomp only on a genuine landing, not takeoff | Superseded (ADR-0017) | Replacement: `crush_stomp` drives off a 4-block ledge and asserts a contact-damage hit of >= 60 on the zombie beneath; off a 2-block ledge asserts no Crush Stomp. | `truck_tick.test.mjs` ">= 3 blocks Crush Stomps", "under 3 blocks land softly", "landing waits for engine ground contact"; `test_suspension.py` `CRUSH_STOMP_MIN_DROP == 3`. | PG 18 | Radial knockback is node/static-only. |
| 6 | Crush Stomp spares players, riders, vehicles, tamed companions | Automated (partial) | `crush_stomp` asserts the seated driver is at full health after each landing. | `truck_tick.test.mjs` "spares players"; `test_airborne_crush.py` / `test_trample.py` `isProtectedTarget` for player, tamed wolf, the truck itself. | PG 18 | No production-path check for tamed companions, bystander players, or other trucks. |
| 7 | Truck immune to fall damage | Automated | `shock_absorption`: after a 16-block drop the truck is at 1000/1000 health. | `main.test.mjs` "the truck itself never takes fall damage"; `test_fall_damage_immunity.py`. | PG 19 | — |
| 8 | Seated riders' fall damage canceled (both seats) | Automated (partial) | `shock_absorption`: the Driver Seat occupant is at full health and still seated after the 16-block drop. | `main.test.mjs` / `truck_tick.test.mjs` protect all seated riders through the landing window; reseat of detached riders. | PG 19, PG 27 | **Gap:** Passenger Seat occupant is never dropped in a Scenario Run. |
| 9 | Protection does not leak after deliberate exit | Supporting only | — | `truck_tick.test.mjs` "Sneak is the only deliberate exit" (protection removed); `main.test.mjs` "protection ends" 8 ticks after landing. | PG 27 | **Gap:** no production-path deliberate-exit fall. |
| 10 | Forward control starts flotation from rest | Automated (partial) | `flotation_water` / `flotation_lava` cross a 35-block pool at >= 90% of overland speed, but enter the liquid already rolling. | `truck_tick.test.mjs` "liquid propulsion follows the driver's W input": first tick of W pushes a floating truck from rest. | PG 25 | **Gap:** start from rest in liquid is not asserted on the production path. |
| 11 | Liquid propulsion follows intended direction | Gap | None. | None (node liquid test covers W only). | PG 25 | Steering in water/lava is unasserted; manual observation only. |
| 12 | Released controls stop propulsion | Supporting only | — | `truck_tick.test.mjs`: no throttle or no driver means no push. | PG 25 | **Gap:** input release in liquid not asserted on the production path. |
| 13 | Shoreline Step-Up over 1- and 2-block banks | Automated (partial) | `flotation_water` / `flotation_lava` assert the truck reaches +0.9 on a 1-block bank without a jump and continues on land. | `test_amphibious.py` `classifyShorelineColumn` (1 and 2 qualify), step impulse; `truck_tick.test.mjs` 1-block bank. | PG 21 | **Gap:** 2-block bank not driven in a Scenario Run. |
| 14 | 3-block shoreline wall stops the truck | Supporting only | — | `test_amphibious.py`: `classifyShorelineColumn` 3 and 4 high is not a shoreline. | PG 26 | **Gap:** no negative scenario. "Unless I use Suspension Jump" is superseded by ADR-0017. |
| 15 | Creative spawn egg randomizes across 16 colors | Supporting only | — | `test_colors.py` `test_randomized_spawn_egg_event`; Windows harness samples 32 eggs (Windows only). | PG 2 | **Gap:** not part of the qualifying run. |
| 16 | Crafted Vehicle Item deploys red | Supporting only | — | `test_spawn_egg_and_icons.py` (item spawns `blake:spawn_red`); Windows harness. | — | **Gap:** not part of the qualifying run. Placing a crafted Vehicle Item in Survival is not on the manual checklist either. |
| 17 | Bare summon is red | Automated | `dye_repaint` asserts a bare `spawnEntity` truck has `blake:color` 0 (red). | Windows harness. | PG 3 | — |
| 18 | `blake:spawn_<color>` wins over generic spawn | Supporting only | — | `test_colors.py` (all 16 events defined); Windows harness triggers all 16. | — | **Gap:** not part of the qualifying run. |
| 19 | Deliberate dismantling returns one Vehicle Item | Automated | `retrieval`: a player-sourced fatal `entityAttack` drops exactly one `blake:monster_truck_vehicle` and no iron. | `main.test.mjs` "a player's fatal blow returns exactly one Vehicle Item". | PG 28 | Damage is applied with `applyDamage` from the driver, not a real swing. |
| 20 | Non-retrieval destruction drops Scrap | Automated (partial) | `retrieval`: explosion, lava, and fire deaths drop iron (Scrap) and no Vehicle Item. | `main.test.mjs`: a zombie kill gives no Vehicle Item; `test_survival_and_audio.py` loot; Windows harness adds mob combat and lightning. | PG 29 | **Gap:** mob combat and a further environmental cause are not in the qualifying run. |
| 21 | Trample damage and knockback scale with speed | Automated (partial) | `trample`: first hit at full input deals more damage than at 0.3 input. | `test_trample.py` damage curve and outward knockback; `truck_tick.test.mjs` speed scaling and 6-tick cooldown. | PG 30 | Knockback is not asserted on the production path. Open item in `docs/STATE.md`: the speed contrast is weak (0.3 input still reaches about 1 block/tick; 122 vs 130 damage). |
| 22 | Parked truck causes no contact damage | Automated | `trample`: a pig touching a parked truck for 30 ticks takes no truck-sourced hit. | `test_trample.py` damage at 0 speed is 0. | PG 30 | — |
| 23 | One authoritative Tire Trample damage path | Supporting only | — | `test_heavy_duty.py` asserts no `minecraft:area_attack`; `contact.test.mjs` cooldown is shared and pruned. | PG 30 | No scenario asserts absence of duplicate hits per contact. |
| 24 | All 16 dyes repaint body, hood, wheel-hub accents without consuming dye | Automated (partial) | `dye_repaint`: sneak-interact with blue dye sets color 1, leaves 3 dye, mounts nobody. | `test_colors.py` 16 paint events, textures, sneak requirement. | PG 15, PG 16 | The other 15 dyes and the visible textures are manual. |
| 25 | Harness exercises the same production paths as players | Automated | Every gameplay scenario drives through the `driverInput` seam that production reads (ADR-0016, ADR-0017); `seats` asserts Passenger Seat input does not drive. | `main.test.mjs` "driverInput reads the driver's movement vector and the held Jump button". | PG 7, PG 17 | Physical key mapping (A = left, Space = handbrake) is outside the seam. |
| 26 | All 16 color events checked in the dedicated world | Gap | None in the qualifying run. | Windows harness spawns all 16 `blake:spawn_<color>` events; `test_colors.py`. | PG 15 | Needs a Scenario Run color check, or an approved decision that static + manual coverage suffices. |
| 27 | Fresh nonce-matched PASS and clean content log | Automated (partial) | ADR-0018 run: markers from other runs are ignored (`test_scenario_runner.py`, `test_in_game_runner.py`); server warnings fail a Scenario Run. | `test_end_to_end_packaging.py`, `test_harness.py`. | — | The Linux client content log file stays empty (`docs/STATE.md` Facts), so its clean result proves little. `report.json` does not record revision or versions (see Evidence record). |
| 28 | Manual checks kept separate from automation | Manual | — | — | PG 6, 7, 11, 12, 17, 19, 20, 31, 32 | This document and `PROVING_GROUND.md` keep them separate. |
| 29 | Docs describe only demonstrated behavior | Supporting only | — | `test_documentation_sync.py`. | — | `docs/RECIPE_GUIDE.md` "Max Speed: 0.55" and README "Movement attribute 0.55" predate ADR-0017's 1.1 blocks/tick (both pinned by `test_documentation_sync.py`). |
| 30 | Failures retain reports, logs, screenshots | Automated | Every run writes `dist/bedrock-tests/<run-id>/report.json`; the Scenario Run container mounts that directory. | `test_in_game_runner.py` capture/shutdown failure tests; `test_scenario_runner.py` container removal on log failure. | — | — |

**Counts:** Automated 6 (7, 17, 19, 22, 25, 30); Automated (partial) 8 (6, 8, 10, 13, 20, 21, 24, 27); Supporting only 8 (9, 12, 14, 15, 16, 18, 23, 29); Manual 1 (28); Superseded 5 (1-5); Gap 2 (11, 26).

## Testing decisions

| Spec testing decision | Status | Coverage |
|---|---|---|
| Primary seam is the dedicated Bedrock test world against the packaged add-on | Superseded (ADR-0016, ADR-0018) | Gameplay seam is the Scenario World on a disposable dedicated server running the packaged add-on; the Dedicated Test World is used by the Client Smoke Run. |
| Automation invokes production behavior; jump test uses the real driver/Spacebar trigger | Resolved (ADR-0016, ADR-0017) | Scenarios drive through `driverInput`; no scripted impulses. Spacebar now means Handbrake Drift (`handbrake`). Physical key mapping is manual (PG 7, PG 17). |
| Production-path Suspension Jump scenario | Superseded (ADR-0017) | Replaced by `crush_stomp` (>= 3-block landing crushes, 2-block does not) and `handbrake`. |
| Two-seat high-drop scenario plus deliberate-exit check | Automated (partial) | `shock_absorption` covers the truck and Driver Seat. **Gap:** Passenger Seat and deliberate exit (node only; PG 27). |
| Amphibious scenarios: start from rest, steering, input release, water, lava, thermal shielding, 1- and 2-block exits | Automated (partial) | `flotation_water` / `flotation_lava`: water, lava, overland speed, thermal shielding, 1-block exit. **Gap:** from rest, steering, input release, 2-block exit (PG 21, PG 25). |
| Negative three-block shoreline scenario | Gap | Node classification only (PG 26). |
| Spawn-source scenarios (egg randomization, crafted red, bare summon red, every color event) | Automated (partial) | Bare summon red in `dye_repaint`. **Gap:** the rest exist only in the Windows harness and static tests. |
| Destruction scenarios (retrieval, mob combat, explosion, fire/lava, another environmental cause; exact outcome, no duplicates) | Automated (partial) | `retrieval`: player retrieval, explosion, lava, fire. **Gap:** mob combat and lightning are Windows-harness only. |
| Tire Trample at parked, low, medium, high speed; monotonic; outward knockback; exclusions; heavy entities; no duplicate fixed damage | Automated (partial) | `trample`: parked plus two input levels. `flotation_lava`: Molten Tire Trample ignites an iron golem. Node/static: knockback, exclusions, heavy-entity stop/shove (`contact.test.mjs`), no `area_attack`. **Gap:** medium speed, knockback, exclusions on the production path. |
| Expand color showcase to all sixteen colors | Gap | Windows harness only; not in the qualifying run. |
| Retain helper-level unit tests | Done | `test_kinematics.py`, `test_driving.py`, `test_amphibious.py`, `test_trample.py`, `test_suspension.py`, `test_airborne_crush.py`, `tests/js/*.test.mjs`. |
| Retain structural, packaging, schema, doc, content-log, nonce, screenshot, shutdown checks | Done, with caveat | Static run plus Linux Client Smoke Run stages (world load, content logs, screenshots, shutdown). Caveat: the Linux content log stays empty. |
| One uninterrupted current-revision run qualifies | Superseded (ADR-0018) | Static + full Scenario Run + Linux Client Smoke Run on one revision and add-on version. |
| Manual Proving Ground for feel, input, view, textures, dye, audio, pitch, steering, particles, multiplayer | Manual | [PROVING_GROUND.md](PROVING_GROUND.md). |
| Record revision, add-on version, game version, run id, checklist results | Defined below; partly manual | `report.json` records `run_id`, mode, timestamps, and stage verdicts only. **Gap:** revision, working-tree state, add-on version, and game version must be recorded by hand until the report captures them. |

## Evidence record

Every acceptance result, automated or manual, is recorded with these fields. A result missing any required field does not qualify.

| Field | Automated result | Manual result |
|---|---|---|
| Repository revision | `git rev-parse HEAD` at run time | Revision the installed packs were built from |
| Working-tree state | `git status --porcelain` empty, or the dirty paths listed | Same |
| Packaged add-on version | `header.version` of `behavior_packs/MonsterTruck_BP/manifest.json` | Version shown in the world's Behavior Packs list |
| Installed game version | Client version and `scenario_server.version` from `testing/bedrock.json` | Client version on the title screen |
| Run identifier | `run_id` in `dist/bedrock-tests/<run-id>/report.json` | Date, tester, world name, and the automated `run_id` it accompanies |
| Expected vs observed outcome | Per-stage and per-scenario checks in `report.json` | The checklist's Expected Outcome and what was seen, with Pass/Fail |
| Retained evidence path | `dist/bedrock-tests/<run-id>/` (report, server/content logs, screenshots) | Screenshot or clip path, or a note of where it is kept |

A qualifying release record holds one automated run (ADR-0018) plus a completed Proving Ground checklist, both carrying the same revision and add-on version.
