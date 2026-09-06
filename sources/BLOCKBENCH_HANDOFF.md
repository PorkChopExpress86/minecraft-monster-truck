# Blockbench Model & Art Handoff

This guide documents how 3D modelers and artists should inspect, edit, and export the Monster Truck assets using Blockbench.

## 1. Opening the Model in Blockbench
1. Launch **Blockbench** (v4.0 or newer).
2. Select **File → Open Model** (or drag and drop):
   `resource_packs/MonsterTruck_RP/models/entity/monster_truck.geo.json`
3. Ensure the project format is detected as **Bedrock Model**.
4. In the **Textures** panel on the left, load:
   `resource_packs/MonsterTruck_RP/textures/entity/monster_truck.png`

## 2. Bone Hierarchy Integrity
The simulation and animation system depends on exact bone names. Do NOT rename or flatten the following bones:
- `root` (Position: [0, 0, 0])
- `body` (Parent: `root`)
  - `roll_cage` (Parent: `body`)
- `wheel_fl` (Parent: `root`, Pivot: [16.5, 9, -18])
- `wheel_fr` (Parent: `root`, Pivot: [-16.5, 9, -18])
- `wheel_rl` (Parent: `root`, Pivot: [16.5, 9, 18])
- `wheel_rr` (Parent: `root`, Pivot: [-16.5, 9, 18])

> [!IMPORTANT]
> Wheel pivots must remain exactly at the center of each wheel cube so rotational animations spin on-center without wobbling.

## 3. Saving & Exporting
- **Editable Source**: Save your working project as `sources/monster_truck.bbmodel`. Blockbench's `.bbmodel` stores layers, guides, and project settings.
- **Game Export**: When done editing, select **File → Export → Export Bedrock Geometry** and overwrite:
  `resource_packs/MonsterTruck_RP/models/entity/monster_truck.geo.json`
- **Texture Export**: Save your revised PNG to:
  `resource_packs/MonsterTruck_RP/textures/entity/monster_truck.png`
