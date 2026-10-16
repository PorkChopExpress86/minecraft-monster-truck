# Tire Trample and Wood Demolition

The monster truck exerts devastating kinetic force against terrain and hostile entities. Moving wheels inflict Speed-Scaled Tire Trample damage and directional outward knockback upon non-allied mobs, scaling directly with velocity while inflicting zero damage when parked. Traversing lava superheats the wheels into Molten Tire Trample that sets targets on fire. When driving forward with momentum exceeding 0.25 blocks/tick, the vehicle fractures wood, glass, and furniture, while continuously shearing tree leaves and vines at any speed to prevent entanglement.

## Sub-features

- `trample-speed-scaling`: Moving tires inflict kinetic damage and knockback that strictly increases with vehicle velocity.
- `trample-parked-safe`: A stationary or parked truck exerts zero contact damage to touching mobs or players.
- `trample-exclusions`: Seated passengers, allied players, tamed wolves, and other monster trucks are completely immune to trample damage.
- `trample-molten`: Traversing lava superheats the tires, applying fire ticks and burning damage alongside standard collision impact.
- `demolition-wood`: Driving forward with momentum over 0.25 blocks/tick fractures and destroys wooden blocks, structural furniture, and glass, dropping survival resources.
- `shearing-foliage`: Contact with tree leaves, vines, and canopy overhangs continuously shears them at any speed whenever a driver is seated.

## How to get to it (user POV)

- Accelerate the monster truck forward into hostile mobs to inflict heavy collision damage and send them flying outward.
- Drive through a lava pool, then collide with a mob to trample and ignite them simultaneously.
- Drive at speed into wooden barricades, fences, logs, or glass windows to smash through them.
- Drive under low-hanging tree branches and vines: the foliage shears away smoothly, keeping the path clear.

## Driving it with Test-Addon.ps1

Preconditions:

- Docker Desktop is active with Bedrock Dedicated Server image.
- Dedicated Test World is configured.

- **Speed-scaled trample verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only trample`. The scenario asserts that at low (0.3), medium (0.6), and full throttle, impact damage strictly increases (dealing ~42, 84, and 139 damage), knockback displaces targets upward and outward, parked trucks deal 0 damage over 30 ticks, and tamed wolves, allied players, and trucks take 0 hits.
- **Molten trample verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only flotation_lava`. The scenario asserts that after traversing lava, hitting an iron golem sets it on fire.
- **Wood demolition verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only demolition`. The scenario asserts that driving with momentum > 0.25 blocks/tick breaks logs and wooden planks with survival drops (`air destroy`), while slow contact below 0.25 blocks/tick does not break blocks.
- **Foliage shearing verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only foliage_shearing`. The scenario asserts that leaves and vines in the vehicle's bounding box are sheared even at resting speeds when a driver is seated.

## Gotchas

- Wood demolition requires genuine forward momentum (> 0.25 blocks/tick); inching into a wooden wall at crawl speed will not destroy blocks.
- Only wood, glass, and furniture are breakable by wood demolition; stone, metal, and bedrock cannot be demolished.
- Tire trample enforces a 6-tick cooldown per truck to prevent duplicate damage frames within a single collision contact.
