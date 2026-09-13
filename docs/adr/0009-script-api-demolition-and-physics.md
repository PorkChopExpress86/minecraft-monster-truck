# Script API Module for Dynamic Demolition and Velocity Physics

This supersedes ADR-0001's pure data-driven constraint and expands upon ADR-0008.

We decided to introduce the Bedrock Script API (`@minecraft/server`) to the Monster Truck behavior pack. Pure Bedrock entity JSON components cannot dynamically clear wood and glass blocks while an entity is steered by player input (`minecraft:input_ground_controlled`), nor can they scale collision damage and knockback proportionally to vehicle velocity.

The script monitors active driving momentum:
1. **Wood Demolition**: When forward velocity exceeds 0.25 blocks/tick, the script samples blocks in a 2.5-block wide by 3-block high tunnel in front of the vehicle, plus overhead canopy leaves up to 5 blocks high. Tree leaves and foliage are vaporized without item drops to prevent lag, while logs, planks, wooden furniture, and glass break and drop harvestable survival items.
2. **Speed-Scaled Tire Trample & Inertia**: Targets hostile mobs and untamed animals within a 1.6-block radius, sparing players and tamed pets. Damage scales dynamically with vehicle velocity. Standard mobs receive strong outward knockback; ultra-heavy mobs with native knockback resistance (Iron Golems, Wardens) absorb kinetic energy, halting low-speed trucks while being shoved and crushed at maximum ramming velocity.
