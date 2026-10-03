# Bedrock engine physics: measured facts

Facts about the Bedrock 1.26.52.3 engine that the driving model and Scenario Runs depend on. No config or API doc states them; each was measured in a Scenario Run. Re-measure (see the end) before changing a value.

## Drag applies before the move

Each tick the engine scales an entity's velocity by a retention factor, then moves it. An impulse that sets horizontal velocity to `v` therefore moves the truck `v × retention`. To cover speed `s`, set velocity to `s / retention`. This is what `driving.js` does on every surface.

| Medium | Horizontal retention | Evidence |
|---|---|---|
| Ground | `0.91 × slipperiness × minecraft:friction_modifier`: 0.6 slipperiness for most blocks (0.628 with the truck's 1.15 modifier); ice and packed ice 0.98, blue ice 0.989, slime 0.8 | 3.58 blocks in 20 ticks without the factor; 7.7 with it (model 7.77). Leaving out the modifier overshot by 15% |
| Water | 0.86 | Velocity 1.1 moved the truck 0.95 blocks/tick |
| Lava | 0.72 | Velocity 1.1 moved it 0.79 blocks/tick |
| Air | 0.91 | Used while a Shoreline Step-Up lifts the truck |

The truck's `minecraft:movement` value of 0.55 is an engine attribute, not blocks/tick. Engine-driven, the truck covered 1.06–1.12 blocks/tick.

## Collisions zero the velocity into a face

Every tick an entity touches a block face, the velocity component into that face is zeroed. A vertical impulse alone lifts the truck straight up beside a ledge and drops it back. To climb a bank, keep pushing forward until the truck is above the edge: Shoreline Step-Up keeps driving active for 8 ticks after its lift.

## Damage immunity window

A mob hit again within its immunity window (about 10 ticks) takes, and reports in `entityHurt`, only the excess over the earlier hit. A scenario that checks a damage amount must make that hit the first one, as `crush_stomp` does by spawning the mob just before touchdown. Distinguish hit sources by `damageSource.cause` (Crush Stomp `contact`, Tire Trample `entityAttack`), not by amount; armor changes the amount as well.

## Script runtimes

A GameTest simulated player exists as a player object only in the script runtime that spawned it; other packs see `undefined` (ADR-0016). It never reports `inputInfo` movement or button state.

## Measuring

- Rerun one scenario: `./test-addon.sh Scenarios --only <name>`.
- Put a per-tick trace in the failure message rather than logging it: any non-marker WARN/ERROR line fails a run. `liquid_crossing` in `testing/scenarios/scenarios.js` records `[tick, z, y, vy]` past z=35.
- Retention = distance moved in a tick ÷ the horizontal velocity set just before it. A driven truck that crawls far below its target speed suggests a missing retention factor, because the "blocked by a wall" speed reset fires every tick.
