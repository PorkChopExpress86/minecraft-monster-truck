# Heavy-duty tuning and moving contact damage

This supersedes the 250 HP tuning in ADR-0003; its drop behavior and ADR-0004 recipe remain unchanged.

The user requested substantially stronger durability, mob run-over damage, and terrain traversal. Retain the data-only production architecture. Increase health to 1,000, reduce melee/projectile/explosion damage to 25%, ignore fall damage, set movement to 0.55, and raise base/controlled auto-step to two blocks. Other environmental damage remains unchanged.

Use `minecraft:area_attack` for 40 damage with a 0.5-second cooldown and 0.35 contact range. Filter on the truck moving and the other entity belonging to the mob family, excluding players, vehicles, and tamed entities. This is an engine contact approximation; it does not calculate individual tire geometry or damage proportional to speed. Untamed animals can be hit, and armored or high-health mobs can survive.

The dedicated harness applies real damage and horizontal impulses to production entities. It must prove armor, fall immunity, parked non-damage, moving mob kills, and a temporary two-block ledge traversed with horizontal impulses. Static checks protect tuning and exclusions; driver-input terrain traversal still needs explicit evidence.

References: [Area attack](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/entityreference/examples/entitycomponents/minecraftcomponent_area_attack?view=minecraft-bedrock-stable), [damage sensor](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/entityreference/examples/entitycomponents/minecraftcomponent_damage_sensor?view=minecraft-bedrock-stable), [auto-step](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/entityreference/examples/entitycomponents/minecraftcomponent_variable_max_auto_step?view=minecraft-bedrock-stable).
