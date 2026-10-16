# Sixteen-Color Customization and Vehicle Retrieval

The monster truck supports full aesthetic customization across vanilla Minecraft's 16-dye palette (`red`, `blue`, `green`, `yellow`, `black`, `white`, `orange`, `magenta`, `light_blue`, `lime`, `pink`, `gray`, `light_gray`, `cyan`, `purple`, `brown`), updating body panels, hood, and wheel-hub accent plates. In Survival, players repaint vehicles non-destructively by sneak-interacting with any dye without expending the item. Creative spawn eggs randomize color upon placement, while crafted vehicle items deploy in deterministic classic red. When dismantled by deliberate player strikes, the truck drops exactly one portable Vehicle Item; catastrophic environmental destruction drops raw Scrap (iron ingots).

## Sub-features

- `palette-sixteen`: 16 discrete, pre-baked textures with matched wheel-hub accent plates for each vanilla dye color.
- `sneak-dye-repaint`: Sneak-interacting with a truck while holding any vanilla dye instantaneously repaints the vehicle without consuming the dye item.
- `spawn-egg-random`: Placing a Creative mode spawn egg randomly picks from the 16 colors with equal probability.
- `vehicle-item-red`: Placing a crafted Survival Vehicle Item (`blake:monster_truck_vehicle`) deterministically spawns a red truck.
- `retrieval-item`: A player's deliberate fatal blow (attack) on a monster truck returns exactly one Vehicle Item and zero Scrap.
- `destruction-scrap`: Destruction caused by environmental hazards (fire, lava, lightning, explosion) or hostile mob attacks drops raw Scrap (iron ingots) and no Vehicle Item.

## How to get to it (user POV)

- In Creative mode, place a Monster Truck Spawn Egg to spawn a randomly colored monster truck.
- In Survival mode, craft the Monster Truck Vehicle Item at a crafting table and place it on the ground to deploy a red monster truck.
- Hold any vanilla dye in hand, hold Sneak (`Shift`), and interact (right-click / tap) with the monster truck to instantly repaint it.
- Attack and dismantle a truck with a weapon to collect it back into your inventory as a Vehicle Item.
- Destroy a truck with TNT or lure it into fire/lava to break it down into iron ingots (Scrap).

## Driving it with Test-Addon.ps1

Preconditions:

- Docker Desktop is active with Bedrock Dedicated Server image.
- Dedicated Test World is configured.

- **Spawn sources verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only spawn_sources`. The scenario asserts that 200 Creative egg placements spawn all 16 colors, crafted Vehicle Item placement always spawns red, bare summon spawns red, and each of the 16 `blake:spawn_<color>` events sets its matching color.
- **Dye repaint verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only dye_repaint`. The scenario asserts that sneak-interacting with each of the 16 dyes sets the vehicle color property, retains the dye item count without consumption, and does not mount the player.
- **Vehicle retrieval verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only retrieval`. The scenario asserts that a player's fatal blow drops exactly one `blake:monster_truck_vehicle` and no iron, whereas explosion, fire, lava, mob attack, and lightning each drop iron ingots and no Vehicle Item.
- **Visual showcase verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Game`. The smoke runner arranges a showcase of all 16 colors side by side in the Dedicated Test World, validates components and seats, and captures viewport screenshots into `dist/bedrock-tests/<run_id>/screenshots/`.

## Gotchas

- Sneaking is mandatory for repainting; interacting while standing upright mounts the player into the Driver Seat instead of dyeing.
- Dye items are never consumed or expended when repainting; one dye can repaint an entire fleet of trucks.
- A player fatal blow must land the killing strike to retrieve the Vehicle Item; if a skeleton or creeper deals the final damage, only iron Scrap will drop.
