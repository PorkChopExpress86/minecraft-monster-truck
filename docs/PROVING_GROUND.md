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
| **2. Egg Placement** | Right-click / use the spawn egg on a flat surface. | The monster truck entity spawns cleanly with correct geometry and textures. | [ ] |
| **3. Slash Command** | Run `/summon blake:monster_truck` in chat. | Entity spawns at command coordinates without errors. | [ ] |
| **4. Driver Mounting** | Approach truck and interact (Right-click / "Drive" prompt). | Player mounts into the Driver Seat position [-0.55, 1.75, 0.20] per ADR-0006. | [ ] |
| **5. Third-Person View** | Switch camera to third-person back view (F5). | Camera is positioned at radius 6.0, showing the complete vehicle clearly. | [ ] |
| **6. WASD Driving** | Press `W` (forward), `S` (reverse), `A` (steer left), `D` (steer right). | Vehicle moves smoothly with responsive turning capped at 18 deg/tick. | [ ] |
| **7. 1-Block Auto-Step** | Drive directly forward into a 1-block high stone ledge without jumping. | Vehicle smoothly drives up the ledge via controlled auto-step. | [ ] |
| **8. 2-Block Ledge / 3-Block Wall** | Drive into two-block and then three-block obstacles. | Vehicle climbs the two-block ledge and stops at the three-block wall. | [ ] |
| **9. Wheel Rotation** | Observe wheels while moving vs. stationary. | Wheels spin continuously during motion; wheels stop rotating at idle. | [ ] |
| **10. Chassis Dynamics** | Drive at full speed across flat terrain. | Chassis subtly bobs while driving without visual jitter. | [ ] |
| **11. Dismount** | Press Sneak / Shift to dismount. | Player exits cleanly onto adjacent solid ground without suffocating. | [ ] |
| **12. Content Log** | Open Content Log history in Creator settings. | Zero schema errors, unresolved texture warnings, or missing animation errors. | [ ] |
| **13. Paint Colors** | Sneak and interact with a truck while holding red, blue, green, yellow, black, or white dye. | Body and hood switch to the matching color; dye remains reusable. | [ ] |
| **14. Mount After Painting** | Stop sneaking and interact normally after repainting. | Driver mounting and driving still work. | [ ] |

## Heavy-duty driving checks

Drive forward and backward through mobs; verify a stopped truck does not attack. Check that players and tamed pets are unaffected. Drive up one- and two-block ledges with sufficient overhead clearance, then verify three-block walls stop the truck. Test slopes, uneven ground, and descent with both seats occupied. Auto-step configuration and impulse-driven contact tests do not substitute for these player-control checks.
