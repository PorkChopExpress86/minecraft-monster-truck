# Monster Truck Proving Ground & Verification Checklist

This guide documents the verification protocol for testing the Monster Truck Add-on in Minecraft Bedrock Edition.

## 1. Installation & World Setup

### Manual Setup
1. Run the packaging build:
   ```powershell
   python scripts/package_addon.py
   ```
2. Double-click `dist/MonsterTruck.mcaddon` to launch Minecraft and import both packs.
3. Open Minecraft Settings → Creator:
   - Enable **Enable Content Log GUI**
   - Enable **Enable Content Log Files**
4. Create a new test world in **Creative Mode**.
5. In World Settings:
   - Go to **Behavior Packs** → Activate **Monster Truck Behavior**.
   - Confirm that **Monster Truck Resources** is automatically activated under Resource Packs (linked via dependency UUID).

### Automated In-Game Test Runner
Follow [Windows testing setup](WINDOWS_TESTING.md) once, then run the configured static checks and verified runtime smoke test:
```powershell
# Static checks, packaging, and the dedicated test world:
.\Test-Addon.ps1

# Read-only installation/world discovery:
.\Test-Addon.ps1 -Mode Doctor
```
Reports, fresh content logs, and available game-window screenshots are saved to `dist/bedrock-tests/<run-id>/`. The separate test-only script pack verifies `/summon blake:monster_truck`'s equivalent spawn operation and required components; screenshots do not establish visual correctness. Continue the manual checks below for driving, appearance, and audio.


## 2. In-Game Proving Ground Obstacle Course

Construct a small proving track with the following obstacles:
- **Flat Pavement**: 20-block smooth stone straightaway.
- **Single-Block Terraces**: 1-block stone steps leading up an incline.
- **Two-Block Ledge and Three-Block Wall**: A climbable ledge followed by a taller barrier.
- **Slopes & Ramps**: Stairs and slabs.
- **Passage**: A 3-block wide gateway.
- **Water Trench**: 1-block deep water channel.

---

## 3. Verification Checklist

| Test Item | Verification Procedure | Expected Outcome | Status |
|---|---|---|:---:|
| **1. Spawn Egg Item** | Open Creative inventory → Nature / Spawn Eggs. | Custom 16x16 monster truck silhouette egg appears named "Spawn Monster Truck". | [ ] |
| **2. Egg Placement** | Right-click / use the spawn egg on a flat surface. | The monster truck entity spawns cleanly with randomized paint color and correct geometry. | [ ] |
| **3. Slash Command** | Run `/summon blake:monster_truck` in chat. | Entity spawns at command coordinates in default red paint without errors. | [ ] |
| **4. Driver Mounting** | Approach truck left door and interact (Right-click / "Drive" prompt). | Player mounts into the Driver Seat position [0.45, 1.15, 0.15] per ADR-0006 and ADR-0012. | [ ] |
| **5. Third-Person View** | Switch camera to third-person back view (F5). | Camera is positioned at radius 7.5, providing an elevated chase camera over the roof and tailgate. | [ ] |
| **6. Cab Interior View** | Switch camera to first-person view while seated in the driver seat. | Eye line is cleanly centered in the transparent windshield aperture ($Y \approx 40.8$) with clear forward sightline over the hood and $>5$ units of vertical roof headroom without roof clipping per ADR-0012. | [ ] |
| **7. WASD Driving** | Press `W` (forward), `S` (reverse), `A` (steer left), `D` (steer right). | Vehicle moves smoothly with responsive ground control authority at 0.55 cruising speed. | [ ] |
| **8. 1-Block Auto-Step** | Drive directly forward into a 1-block high stone ledge without jumping. | Vehicle smoothly drives up the ledge via controlled auto-step. | [ ] |
| **9. 2-Block Ledge / 3-Block Wall** | Drive into two-block and then three-block obstacles. | Vehicle climbs the two-block ledge and stops at the three-block wall. | [ ] |
| **10. Wheel Rotation & Dynamics**| Observe wheels while moving vs. stationary. | Wheels spin continuously during motion; wheels stop rotating at idle; chassis bobs subtly. | [ ] |
| **11. Dynamic Incline Pitch** | Drive up and down natural hills, stairs, and 2-block terraces. | Chassis pitches up and down up to $\pm 35^\circ$ conforming to terrain slope gradients smoothly per ADR-0014. | [ ] |
| **12. Coordinated 4WS** | Steer sharply left and right while moving forward and reversing. | Front steering knuckles deflect up to $\pm 26^\circ$ into turn; rear wheels counter-steer up to $\mp 18^\circ$ with hydraulic spring return per ADR-0014. | [ ] |
| **13. Dismount** | Press Sneak / Left Shift to dismount. | Player exits cleanly onto adjacent solid ground or vehicle roof/flatbed without suffocating. | [ ] |
| **14. Content Log** | Open Content Log history in Creator settings. | Zero schema errors, unresolved texture warnings, or missing animation errors. | [ ] |
| **15. 16 Paint Colors** | Sneak and interact holding any of the 16 vanilla Minecraft dyes. | Body, hood, and wheel-hub accents switch to the matching color swatch; dye is reusable per ADR-0013. | [ ] |
| **16. Mount After Painting** | Stop sneaking and interact normally after repainting. | Driver mounting and driving continue to function seamlessly. | [ ] |
| **17. Suspension Jump** | While driving or stationary, tap Spacebar. | Truck executes an instant vertical launch clearing 3 blocks with pneumatic hiss audio (`random.fizz`) and dust particles; 1.2s cooldown gates re-triggering per ADR-0010. | [ ] |
| **18. Crush Stomp Landing** | Land a high Suspension Jump directly onto hostile mobs. | Inflicts 60+ kinetic crush damage and outward radial knockback on surrounding entities per ADR-0010. | [ ] |
| **19. Shock Absorption** | Drive off a 30+ block cliff onto solid stone. | Truck and seated riders take 0 fall damage (100% pneumatic immunity) with puff of smoke particles per ADR-0013. | [ ] |
| **20. Amphibious Flotation** | Drive into deep ocean water or Nether lava lakes. | Truck floats stably at ~0.8-block waterline, cruises at overland speed with loose drift steering, and protects riders from heat per ADR-0010 & ADR-0011. | [ ] |
| **21. Shoreline Step-Up** | Drive forward from water or lava into a 1- or 2-block shoreline bank. | Truck smoothly climbs up onto dry land without stalling or requiring manual jump inputs per ADR-0011. | [ ] |
| **22. Molten Tire Trample** | Traverse lava, then ram hostile mobs on land within 10 seconds. | Wheels ignite impacted mobs with fire ticks in addition to collision impact damage per ADR-0010. | [ ] |
| **23. Wood Demolition** | Drive forward into logs, planks, fences, or glass at speed ($\ge 0.25$). | Blocks shatter with standard breaking sounds and drop collectable survival items per ADR-0009. | [ ] |
| **24. Foliage Shearing** | Drive into tree leaves or hanging vines at resting or low speed. | Foliage clears instantly on contact without item drops to prevent lag per ADR-0011. | [ ] |
| **25. Input Release in Liquid** | From rest in water and lava, hold then release each movement direction. | The truck starts under input, follows the intended direction, and stops adding propulsion when controls are released. | [ ] |
| **26. Three-Block Shoreline Boundary** | Drive from liquid directly into a continuous three-block stone bank without Spacebar. | Shoreline Step-Up does not lift the truck; an intentional Suspension Jump is required. | [ ] |
| **27. Two-Seat High Drop** | With a Driver and Passenger seated, drive off a 30+ block drop, then deliberately exit and perform an unrelated fall. | Both seated occupants are protected for the vehicle event; protection does not persist after deliberate exit. | [ ] |
| **28. Retrieval** | Reduce a truck to its final hit with a direct player attack. | The truck returns exactly one Monster Truck Vehicle Item and no Scrap. | [ ] |
| **29. Catastrophic Destruction** | Separately destroy trucks through mob combat, explosion, fire/lava, and another environmental cause. | Each destruction produces Scrap and never a complete Vehicle Item or duplicate drop. | [ ] |
| **30. Tire Trample Scaling** | Contact the same mob type while parked and at low, medium, and high speeds. | Parked contact is safe; damage rises monotonically with speed; knockback is outward; protected targets remain unharmed; damage is not doubled. | [ ] |

## Acceptance evidence

Record the repository revision, packaged add-on version, installed Minecraft version, automated run identifier, and the completed checklist with the retained report, content log, and screenshots. A static-only result, an older packaged build, or an incomplete manual checklist does not qualify the current release.

## Heavy-duty driving checks

Drive forward and backward through mobs; verify a stopped truck does not attack. Check that players and tamed pets are unaffected. Drive up one- and two-block ledges with sufficient overhead clearance, then verify three-block walls stop the truck. Test slopes, uneven ground, and descent with both seats occupied. Auto-step configuration and impulse-driven contact tests do not substitute for these player-control checks.
