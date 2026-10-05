# Monster Truck Proving Ground & Verification Checklist

This guide is the manual half of acceptance for the Monster Truck Add-on in Minecraft Bedrock Edition. It lists only what a person has to see, hear, or feel in the real client. Everything a Scenario Run already asserts is named beside each item so the tester checks the residue, not the whole mechanic again. The full automated/manual mapping is in [ACCEPTANCE_COVERAGE.md](ACCEPTANCE_COVERAGE.md).

## 1. Installation & World Setup

### Manual Setup
1. Run the packaging build:
   ```bash
   python scripts/package_addon.py
   ```
   or install straight into the local client with `python scripts/install_addon.py`.
2. On Windows, double-click `dist/MonsterTruck.mcaddon` to launch Minecraft and import both packs.
3. Open Minecraft Settings → Creator:
   - Enable **Enable Content Log GUI**
   - Enable **Enable Content Log Files**
4. Create a new test world in **Creative Mode**.
5. In World Settings:
   - Go to **Behavior Packs** → Activate **Monster Truck Behavior**.
   - Confirm that **Monster Truck Resources** is automatically activated under Resource Packs (linked via dependency UUID).

### Automated Acceptance Run
The qualifying automated result (ADR-0018) is a Static run, a full Scenario Run, and a Linux Client Smoke Run on one revision. One command runs all three under one run identifier:
```bash
./test-addon.sh All
```
Reports, logs, and screenshots are saved to `dist/bedrock-tests/<run-id>/`. Scenario Runs drive the truck with a Simulated Driver through the add-on's input seam and assert gameplay (ADR-0016, ADR-0017); the Client Smoke Run only proves the packs load and captures screenshots, and screenshots do not establish visual correctness. On Windows, `.\Test-Addon.ps1` still runs the Windows Client Smoke Run (see [Windows testing setup](WINDOWS_TESTING.md)), which also checks the `/summon blake:monster_truck` equivalent spawn, all sixteen color spawn events, and destruction outcomes, but it is not required for acceptance. See [Linux testing](LINUX_TESTING.md) for what a green Scenario Run cannot see.

## 2. In-Game Proving Ground Obstacle Course

Construct a small proving track with the following obstacles:
- **Flat Pavement**: 20-block smooth stone straightaway.
- **Single-Block Terraces**: 1-block stone steps leading up an incline.
- **Two-Block Ledge and Three-Block Wall**: A climbable ledge followed by a taller barrier.
- **Drops**: A 2-block ledge, a 4-block ledge, and a 30+ block cliff onto stone.
- **Slopes & Ramps**: Stairs, slabs, and a natural hill.
- **Passage**: A 3-block wide gateway.
- **Water and Lava Pools**: Deep enough to float, with 1-, 2-, and 3-block banks.

---

## 3. Verification Checklist

Record the run header once, then mark each item Pass or Fail and note where its evidence (screenshot, clip, or note) is kept.

| Evidence field | Value |
|---|---|
| Repository revision and working-tree state | |
| Packaged add-on version | |
| Installed Minecraft version | |
| Tester, date, and world | |
| Automated run identifier this checklist accompanies | |

"Automated" names the Scenario Run (`testing/scenarios/scenarios.js`) or test that already asserts part of the item; "—" means nothing automated covers it.

| Test Item | Automated | Verification Procedure | Expected Outcome (what only a person can confirm) | Pass/Fail | Evidence |
|---|---|---|---|:---:|---|
| **1. Spawn Egg Item** | — | Open Creative inventory → Nature / Spawn Eggs. | Custom 16x16 monster truck silhouette egg appears named "Spawn Monster Truck". | [ ] | |
| **2. Egg Placement** | Static only | Use the spawn egg on a flat surface several times. | Trucks spawn cleanly with correct geometry and visibly varied paint colors (Randomized Spawn Egg Placement). | [ ] | |
| **3. Slash Command** | `dye_repaint` (bare spawn is red) | Run `/summon blake:monster_truck` in chat. | The truck appears at the command coordinates, visibly red, without errors. | [ ] | |
| **4. Driver Mounting** | `seats` | Approach the truck's left door and interact (Right-click / "Drive" prompt); have a second player take the other seat. | Player sits in the Driver Seat on the front-left per ADR-0006 and ADR-0012; the second player sits in the Passenger Seat alongside. | [ ] | |
| **5. Third-Person View** | — | Switch camera to third-person back view (F5). | Elevated chase camera over the roof and tailgate. | [ ] | |
| **6. Cab Interior View** | — | Switch camera to first-person view while seated in the Driver Seat. | Eye line is level with the transparent windshield, clear forward sightline over the hood, no roof clipping per ADR-0012. | [ ] | |
| **7. WASD Driving** | `seats`, `steering` (through the input seam, not keys) | Press `W` (forward), `S` (brake, then reverse), `A` (steer left), `D` (steer right); look around with the mouse while driving. | W reaches about 22 blocks/s in about 1.5 s and coasts to a stop on release; **A steers left and D steers right**; the truck turns only while moving, in a wider arc at speed; looking around never steers; parked, A/D turn the wheels without spinning the truck per ADR-0017. Throttle and steering feel controllable. | [ ] | |
| **8. 1-Block Auto-Step** | `incline_pitch` (stairs) | Drive directly forward into a 1-block high stone ledge. | The climb looks smooth (Controlled Auto-Step), with no visible lurch or launch. | [ ] | |
| **9. 2-Block Ledge / 3-Block Wall** | `auto_step` | Drive into the two-block ledge and then the three-block wall, with both seats occupied. | The two-block climb looks smooth with no hop; the stop at the three-block wall does not eject or hurt either rider. | [ ] | |
| **10. Wheel Rotation & Dynamics**| — | Observe wheels while moving vs. stationary. | Wheels spin continuously during motion and stop at idle; chassis bobs subtly. | [ ] | |
| **11. Dynamic Incline Pitch** | `incline_pitch` (the `blake:pitch_angle` value) | Drive up and down natural hills, stairs, and 2-block terraces. | The chassis and wheels visibly tilt with the slope, transitions look damped rather than snapping, and the truck sits level on flat ground per ADR-0014. | [ ] | |
| **12. Coordinated 4WS** | `steering` (the `blake:steer_angle` value) | Hold A or D while moving forward and reversing, and while parked. | Front wheels visibly turn toward the pressed key, rear wheels counter-steer, and both spring back on release per ADR-0014 and ADR-0017. | [ ] | |
| **13. Dismount** | Node test only | Press Sneak / Left Shift to dismount, on land and while floating. | Player exits cleanly onto adjacent solid ground, or onto the roof over liquid, without suffocating. | [ ] | |
| **14. Content Log** | Static, Client Smoke Run (the Linux content log file stays empty) | Open Content Log history in Creator settings after the session. | Zero schema errors, unresolved texture warnings, or missing animation errors. | [ ] | |
| **15. 16 Paint Colors** | `dye_repaint` (blue only) | Sneak and interact holding each of the 16 vanilla Minecraft dyes in turn. | Body, hood, and wheel-hub accents visibly switch to the matching Textured Color Swatch for every dye; the dye is not consumed per ADR-0013. | [ ] | |
| **16. Mount After Painting** | `dye_repaint` (no mount while sneaking) | Stop sneaking and interact normally after repainting. | Driver mounting and driving continue to work. | [ ] | |
| **17. Handbrake Drift** | `handbrake` (stop, hold, drift, grip, rider retention through the input seam) | At speed, hold Space straight ahead; then hold Space while steering; then release. | **Space never dismounts** and the driver stays visibly seated (#32). The straight stop looks hard and straight; the drift visibly swings the rear out; grip returns within about half a second; the drift feels controllable per ADR-0017. | [ ] | |
| **18. Crush Stomp Landing** | `crush_stomp` (4-block crushes, 2-block does not, driver unhurt) | Drive off the 4-block ledge onto hostile mobs with a tamed pet and another player nearby, then off the 2-block ledge. | The landing plays the explosion sound and particles, mobs are visibly knocked outward, and the pet and the other player are unharmed. | [ ] | |
| **19. Shock Absorption** | `shock_absorption` (16-block drop, truck and driver unhurt) | Drive off the 30+ block cliff onto solid stone. | The pneumatic vent sound plays and dust puffs at all four wheels per ADR-0013; the driver stays visibly seated. | [ ] | |
| **20. Amphibious Flotation** | `flotation_water`, `flotation_lava` (floats, overland speed, rider shielded) | Drive into deep water and a lava lake. | The truck floats visibly level at the waterline; splash or lava wake particles and splash/fizz sounds play; no fire overlay on the riders per ADR-0010 & ADR-0011. | [ ] | |
| **21. Shoreline Step-Up** | `shoreline_step` (flush, 1- and 2-above banks climbed within 20 ticks in water and lava, peak at most +0.5 over the top); `flotation_water`, `flotation_lava` (1-above bank at speed) | Drive forward from water or lava into a 1-block bank and a 2-block bank. | The climb looks like a climb, not a hop or a teleport, per ADR-0011. Climbing itself is automated. | [ ] | |
| **22. Molten Tire Trample** | `flotation_lava` (iron golem ignites) | Traverse lava, then ram hostile mobs on land within 10 seconds. | Struck mobs visibly catch fire per ADR-0010. | [ ] | |
| **23. Wood Demolition** | `demolition` (planks and glass cleared at speed, stone and parked contact spared) | Drive forward into logs, planks, fences, or glass at speed. | Blocks break with standard breaking sounds and drop collectable items per ADR-0009. | [ ] | |
| **24. Foliage Shearing** | `foliage_shearing` (canopy cleared at rest) | Drive into tree leaves or hanging vines at low speed. | Foliage clears on contact with no item drops per ADR-0011. | [ ] | |
| **25. Input Release in Liquid** | `liquid_start_water`, `liquid_start_lava` (no drift at rest, W starts it, A/D turn it, speed decays to a stop on release) | From rest in water and lava, hold W, steer with A/D, then release. | Starting, steering, and coasting to a stop feel like land driving. The mechanics are automated. | [ ] | |
| **26. Three-Block Shoreline Boundary** | `shoreline_wall` (a wall 3 above the surface is refused in water and lava) | Drive from liquid directly into a continuous three-block stone bank. | Shoreline Step-Up does not lift the truck. Automated; no manual check needed. | [ ] | |
| **27. Two-Seat High Drop** | `shock_absorption` (Driver Seat only) | With a Driver and Passenger seated, drive off the 30+ block drop, then deliberately Sneak out and jump off a separate ledge. | Both occupants take no fall damage from the vehicle drop; the later on-foot fall hurts normally. | [ ] | |
| **28. Retrieval** | `retrieval` (player-sourced fatal damage) | Reduce a truck to its final hit by punching it. | Exactly one Monster Truck Vehicle Item drops and no Scrap. | [ ] | |
| **29. Catastrophic Destruction** | `retrieval` (explosion, lava, fire) | Let mobs destroy a truck, and destroy one with lightning (`/summon lightning_bolt` on a damaged truck). | Each drops Scrap and never a Vehicle Item or a duplicate drop. | [ ] | |
| **30. Tire Trample Scaling** | `trample` (parked safe, fast hits harder than slow) | Contact the same mob type while parked and at low, medium, and high speeds; drive past a tamed pet and another player. | Damage visibly rises with speed and mobs are knocked outward; the pet and the player are untouched; a stopped truck does not attack. | [ ] | |
| **31. Multiplayer** | — | Two players: one drives, one rides as passenger, then swap; a third player watches from outside. | Both riders see each other seated; the passenger cannot steer; the watcher sees the truck, wheels, steering, and paint move in sync without rubber-banding. | [ ] | |
| **32. Engine Audio** | Static only | Idle parked with a driver, then drive. | The idle sound plays when parked and the drive sound while moving, switching cleanly. | [ ] | |

## Acceptance evidence

Fill in the run header above and keep it with the automated run named there. A qualifying release record is one automated run under ADR-0018 plus this completed checklist, both on the same repository revision and packaged add-on version. A static-only result, an older packaged build, or an incomplete checklist does not qualify the current release. Field definitions are in [ACCEPTANCE_COVERAGE.md](ACCEPTANCE_COVERAGE.md#evidence-record).
