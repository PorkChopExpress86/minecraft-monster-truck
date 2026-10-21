# Monster Truck release evidence

Version 1.0.14, checked October 18, 2026, America/Chicago. This replaces the September 7 record for 1.0.13 and earlier builds.

## Build

- Version: 1.0.14, both packs, `@minecraft/server` 2.10.0
- Release commit: `f6c0899` (`Release 1.0.14`); the code under test is `30ab1b1`, and the release commit changes only the version numbers and `docs/STATE.md`
- Artifact: `dist/MonsterTruck.mcaddon`, 54,134 bytes
- SHA-256: `FFB737097ADA5BC8C4D699B8B6F716DCAE6E6FBA5CB0E2EE75C314D0ED6B38FD`
- Contents: `MonsterTruck_BP.mcpack` (16 files) and `MonsterTruck_RP.mcpack` (31 files). No file name in either pack contains `test`, `harness` or `scenario`.
- Installed by `python scripts/release.py` to the local Windows client, 10 locations verified in sync. Not installed to the Docker servers.

## Automated results

| Layer | Command | Result | Run or commit |
| --- | --- | --- | --- |
| Unit and contract tests | `REQUIRE_NODE=1 python -m pytest -q` | 244 passed, 3 skipped (Linux-only) | pre-commit hook on `f6c0899` |
| Node behaviour tests | `node --test tests/js/` | 85 of 85 | `6641908` |
| Script API types | `npx tsc -p jsconfig.json` | clean | `6641908` |
| Repository validator | `python scripts/validate_project.py` | passed | `9ce1a95` |
| Creator Tools 0.20.0 | `mct validate all --if dist/MonsterTruck.mcaddon` | 0 errors, 11 warnings, 11 recommendations | 1.0.14 package |
| Scenario Run, headless BDS 1.26.52.3 | `python scripts/bedrock_test.py scenarios` | 25 of 25 | `08ca30f0` on `06f6338`, `9392b0b5` on `6641908` |
| Opt-in scenario | `--only retrieval_full_health` | passed | `d28cf989` |

The 11 Creator Tools warnings do not stop the packs loading. Seven `UNLINK` warnings name vanilla items the recipe uses. Two `JSON 192` warnings say `item_texture.json` uses a string where the schema expects an array; the game accepts both. `COMJSON 134` asks for a `uv_anim` key the game does not require, and `FORMATVER 238` says the animation controller format is newer than the schema expects.

A Creator Tools pass carries little weight. Given a build whose behavior pack manifest was cut off mid-object, `validate all` still reported "Manifest Validation completed successfully", raised no error and exited 0 (checked October 21 against the 1.0.15 build). `scripts/validate_project.py` parses both manifests and is the check that catches a broken one.

## Real Windows client

| Run | Mode | Result |
| --- | --- | --- |
| `4736a428` on `6641908` | Client Input Run | 10 of 11. `sneak_dismounts` failed on a test bug: `querytarget` reports a player at eye height. Fixed in `30ab1b1`. |
| `5f3261ce` on `30ab1b1` | Client Input Run, `sneak_dismounts` and `sneak_exits_afloat` | 2 of 2. The driver lands 1.80 blocks out of the driver's door, on the floor. |
| `43a2463f` on `f6c0899` | Client Smoke Run | Gameplay 32 of 32, content logs clean, screenshots passed. Failed only because Minecraft took longer than 30 seconds to close. |
| `08e233d6` on `f6c0899` | Client Smoke Run | Gameplay 32 of 32, content logs clean, shutdown passed. Failed only because 1 screenshot was captured and the showcase needs 2. |

Both runs on the release commit passed every gameplay check with clean content logs. The screenshot and shutdown failures come from the capture tooling, which has timed out on this machine since September. That cause is still not established. (Measured after release: a loaded CPU stalled the per-capture helper process before it reached the game; captures now run in-process. See "Why captures timed out" in `docs/WINDOWS_TESTING.md`.)

The client screenshots show the new engine and suspension model with no missing-texture pattern.

## Defects found and fixed in this release

- **Seat order.** A rider the add-on put back in the truck landed in the last seat, so after a mid-drop detach the passenger took the controls. `reseat()` in `landing.js` now restores the previous seat order (`b37a457`). Covered by `reseat_keeps_seats` and `lava_stay_keeps_seats`, which fail on the old code (run `1d95aa46`).
- **Door side while reversing.** The door side followed the direction of travel, so a driver who left while reversing came out of the passenger's door. It now follows the truck's facing (`6641908`).
- **Teleport pull-back.** A rider who left by `/tp`, an ender pearl or a portal was pulled back to the truck's door. The door teleport now applies only within 3 blocks of the truck, in the same dimension (`6641908`).

## Known issues

- Getting out beside tall grass, flowers, snow layers or carpet can set the player one block above the ground. They drop one block and take no damage.
- Riding the truck shows its 1,000 health as a 10-row block of mount hearts on the HUD (Client Smoke Run screenshots).
- The Client Smoke Run harness check "parked truck leaves mob unharmed" failed once in four real-client runs (`1ac43d79`). The cause was not caught. The same steps on BDS left the pig unharmed (`92ff6cf3`). (After release it passed 18 more real-client runs; the check now names what hurt the pig. See "The parked-pig check" in `docs/WINDOWS_TESTING.md`.)
- Several scenarios assert the Survival driver's health. Over a full run, hunger can cost the driver 1 point, so `reseat_keeps_seats` ignores starvation damage. The cause is inferred, not measured. (Measured after release: it was not hunger. The driver suffocated in the scenario's own build after a lost teleport; see "Removing a ridden truck" in `docs/agents/bedrock-physics.md`. The test setup is fixed and the assertion is strict again.)

## Not verified

- Two real players in one world, including the one tick a passenger spends off the truck when a reseat restores the seat order.
- Controller and touch input, and any device other than this Windows PC.
- Audible engine sounds, existing-world activation, save and reload, and other add-ons in the same world.
- The manual checks in issues #27 to #32.
- Asset ownership, creator identity, key art and a gameplay trailer for Marketplace submission.
