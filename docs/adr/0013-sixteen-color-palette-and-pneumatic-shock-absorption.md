# 16-Color Paint System, Randomized Spawn Egg, and Pneumatic Shock Absorption

We decided to:
1. Expand the vehicle color palette from 6 to the complete set of 16 vanilla Minecraft dye colors: `red` (0, default), `blue` (1), `green` (2), `yellow` (3), `black` (4), `white` (5), `orange` (6), `magenta` (7), `light_blue` (8), `lime` (9), `pink` (10), `gray` (11), `light_gray` (12), `cyan` (13), `purple` (14), and `brown` (15).
2. Support in-world sneak-interaction with all 16 dyes to repaint the truck, and generate high-contrast textured swatches and color-matched wheel hubs for every color.
3. Configure the Creative spawn egg to trigger Bedrock's `randomize` sequence on spawn (`blake:random_color_on_spawn`), assigning a random color among all 16 colors upon egg placement, while supporting explicit summoning via `/summon blake:monster_truck ~ ~ ~ blake:spawn_<color>`.
4. Enforce dual-layer Pneumatic Shock Absorption giving both the vehicle entity and its seated riders 100% fall damage immunity across all drops and Suspension Jumps, accompanied by pneumatic hiss audio (`random.fizz`) and wheel dust impact particles (`minecraft:campfire_smoke_particle`).
