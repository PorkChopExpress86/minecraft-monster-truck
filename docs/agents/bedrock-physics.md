# Bedrock engine physics: measured facts

Facts about the Bedrock 1.26.52.3 engine that the driving model and Scenario Runs depend on. No config or API doc states them; each was measured in a Scenario Run, or in a Client Input Run where a section says so. Re-measure (see the end) before changing a value.

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

A mob hit again within its immunity window (about 10 ticks) takes, and reports in `entityHurt`, only the excess over the earlier hit. A scenario that checks a damage amount must make that hit the first one, as `crush_stomp` does by spawning the mob just before touchdown. Distinguish hit sources by `damageSource.cause` (Crush Stomp `contact`, Tire Trample `entityAttack`), not by amount; armor changes the amount as well. Only the first hit is comparable: `trample` uses a fresh pig per speed and compares those first hits only.

## Knockback shows on the next move

An impulse applied to a mob (Tire Trample knockback) is not visible in `getVelocity()` from the same tick's `entityHurt` after-event, which reads zero. Measure knockback as the mob's displacement over the following ticks, as `trample` does.

## Vertical lifts: the move uses the set velocity, then drag

Unlike horizontal motion, a vertical velocity set by an impulse is moved in full on the next tick. In water an impulse of 0.4 raised the truck 0.419; in lava a 0.75 lift against a bank raised it 0.80. Drag then acts on what is left for the following tick:

Share kept is the next tick's vertical velocity over this tick's, gravity included.

| Medium at the start of the lift | Vertical velocity kept after the first move | Evidence |
|---|---|---|
| Water | 0.71 (0.769 -> 0.544) | Free lift of 0.75 from the surface |
| Lava | 0.04 to 0.32 on 4 of 5 lifts (0.76 -> 0.027 starting 0.96 deep, 0.80 -> 0.255 starting 0.41 deep); 0.79 on the other (0.70 -> 0.556) | Driven truck against a bank 2 above the surface, one lift every 13 ticks |

So a single lift out of lava either stalls (peaks +0.66 to +0.78) or launches (+3.26 from a 0.9 lift). Shoreline Step-Up instead sets the vertical velocity every tick until the truck is over the bank (`SHORELINE_LIFT` in `amphibious.js`). Because each tick's move uses the velocity just set, the climb is the same in both liquids: `shoreline_step` measured a bank 2 above the surface climbed 14 ticks after reaching it, peaking +0.08 over the top, in water and in lava.

## Liquid motion per tick is noisy

A driven truck's distance per tick in a liquid wobbles even while its commanded speed falls every tick. While coasting in lava, one tick covered 0.14 blocks more than the one before (0.418 then 0.555), with the truck inside the lava block on every tick. Judge acceleration or decay in a liquid on multi-tick means (`liquid_start_*` use 5-tick means).

## Script runtimes

A GameTest simulated player exists as a player object only in the script runtime that spawned it; other packs see `undefined` (ADR-0016). It never reports `inputInfo` movement or button state. Setting `isSneaking` on a seated simulated player does not dismount it; `two_seat_drop` ejects the sneaking rider with `ejectRider`, so the add-on still sees a Sneak exit. Its item uses (`useItemOnBlock`) are rate-limited: a use right after a registered one returns false for up to 8 ticks, so `spawn_sources` retries every tick.

## The real client (Client Input Run)

Measured in the Linux client 1.26.52.3 (flatpak mcpelauncher) through `./test-addon.sh Client` (ADR-0019). The dedicated server shows none of these.

- **Riding and Sneak.** A riding player never reads `isSneaking`, and the Sneak button reads Released while riding and for the ticks after a Sneak dismount. The only sign of a Sneak exit is the rider leaving the seat. `landing.js` therefore treats any exit on steady ground, without Jump, as Sneak.
- **Riding and Space.** Minecraft dismounts a rider of a plain `minecraft:rideable` who presses Space. The Jump button reads Pressed on the tick before that exit and for 4 or more ticks after it (`SPACE_EXIT_GRACE_TICKS` in `truck_tick.js`). Research on stopping it at the source: #40.
- **Virtual keys.** A uinput Shift (left or right) never registers as Sneak, though it works as a modifier and a real Shift sneaks; the run binds Sneak to K. Virtual mouse motion turns the view only while the pointer is over the game window. Keys meant to be held together must go down together: a focus check between presses holds the first key alone for its latency.
- **Chat.** `/` opens chat with "/" prefilled but the box unfocused; Enter focuses it, typed text then lands, and Enter sends. Enter before the chat screen shows closes it.
- **Commands over `/connect`.** `summon <entity> x y z <yaw> <pitch>` is a syntax error in the client (it works on the dedicated server): summon, then `tp` to set facing. `fill` that changes nothing, and `kill` with no targets, return a non-zero status. Commands need the add-on's packs deployed in the world, or add-on entity names fail to parse.

## Measuring

- Rerun one scenario: `./test-addon.sh Scenarios --only <name>`.
- Real-client input: `./test-addon.sh Client --trace --only <check>` records the harness probe's scores (`riding`, `lost`, `sneaking`, `sneak_button`, `jump`) about 1.5 times a second during every key hold (each sample is one WebSocket query per score; `lost` counts every tick in between), under each check's `trace` in `report.json`. To measure something new, publish it as a score in `testing/harness/client_probe.js` and add it to `TRACE_SCORES` in `scripts/client_checks.py`.
- Tag temporary instrumentation in code with `TEMP-DIAGNOSTIC`; the pre-commit hook refuses any staged file that contains it.
- Put a per-tick trace in the failure message rather than logging it: any non-marker WARN/ERROR line fails a run. `liquid_crossing` in `testing/scenarios/scenarios.js` records `[tick, z, y, vy]` past z=35.
- Retention = distance moved in a tick ÷ the horizontal velocity set just before it. A driven truck that crawls far below its target speed suggests a missing retention factor, because the "blocked by a wall" speed reset fires every tick.
