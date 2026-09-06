# Monster Truck Proving Ground & Verification Checklist

This guide documents the verification protocol for testing the Monster Truck Add-on in Minecraft Bedrock Edition.

## 1. Installation & World Setup

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

## 2. In-Game Proving Ground Obstacle Course

Construct a small proving track with the following obstacles:
- **Flat Pavement**: 20-block smooth stone straightaway.
- **Single-Block Terraces**: 1-block stone steps leading up an incline.
- **Two-Block Wall**: A 2-block tall barrier.
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
| **4. Driver Mounting** | Approach truck and interact (Right-click / "Drive" prompt). | Player mounts into the cabin seat position [0.0, 1.75, 0.20]. | [ ] |
| **5. Third-Person View** | Switch camera to third-person back view (F5). | Camera is positioned at radius 6.0, showing the complete vehicle clearly. | [ ] |
| **6. WASD Driving** | Press `W` (forward), `S` (reverse), `A` (steer left), `D` (steer right). | Vehicle moves smoothly with responsive turning capped at 18 deg/tick. | [ ] |
| **7. 1-Block Auto-Step** | Drive directly forward into a 1-block high stone ledge without jumping. | Vehicle smoothly drives up the ledge via controlled auto-step. | [ ] |
| **8. 2-Block Wall** | Drive directly into a 2-block high stone wall. | Vehicle is stopped by the wall and does not clip or jump over. | [ ] |
| **9. Wheel Rotation** | Observe wheels while moving vs. stationary. | Wheels spin continuously during motion; wheels stop rotating at idle. | [ ] |
| **10. Chassis Dynamics** | Drive at full speed across flat terrain. | Chassis subtly bobs while driving without visual jitter. | [ ] |
| **11. Dismount** | Press Sneak / Shift to dismount. | Player exits cleanly onto adjacent solid ground without suffocating. | [ ] |
| **12. Content Log** | Open Content Log history in Creator settings. | Zero schema errors, unresolved texture warnings, or missing animation errors. | [ ] |
