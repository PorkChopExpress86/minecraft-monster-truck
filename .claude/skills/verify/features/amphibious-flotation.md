# Amphibious Flotation and Shoreline Step-Up

The monster truck features buoyant amphibious flotation, enabling continuous travel across water and lava at full overland cruising speed using giant tire displacement. Seated riders are thermally shielded from heat and burning damage while afloat in lava, and the vehicle executes automatic Shoreline Step-Up transitions over 1- and 2-block shoreline banks from liquid to dry land without stalling or requiring manual jumps.

## Sub-features

- `amphibious-buoyancy`: Truck floats continuously on the surface of water and lava without sinking or stalling.
- `amphibious-propulsion`: Driven by W forward throttle and A/D steering at full overland cruising speed (1.1 blocks/tick).
- `thermal-shielding`: Seated driver and passenger take zero fire or lava damage while traversing or resting in molten lava.
- `shoreline-step-up`: Automatically climbs shoreline banks level with, 1 block above, or 2 blocks above the liquid surface without player jump inputs.
- `shoreline-wall-stop`: A 3-block vertical shoreline wall halts the vehicle, keeping it safely afloat in the liquid without climbing.
- `liquid-sneak-safety`: Sneaking while floating over water or lava dismounts the player onto adjacent dry land; if no dry land is reachable over lava, the player remains seated to prevent fatal burns.

## How to get to it (user POV)

- Drive directly into a body of water or pool of lava: the truck floats and maintains forward speed.
- Steer across the liquid surface using standard `W`, `A`, `S`, `D` controls.
- Steer toward the shore: the truck automatically climbs onto 1- or 2-block dry banks.
- Press Sneak (`Shift` / `K`) near a shoreline while floating to dismount safely onto the bank.

## Driving it with Test-Addon.ps1

Preconditions:

- Docker Desktop is active with Bedrock Dedicated Server image.
- Dedicated Test World is configured.

- **Water flotation verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only flotation_water`. The scenario asserts that the truck floats, achieves overland cruising speed across water, steers, and successfully climbs a 1-block shoreline bank.
- **Lava flotation & thermal shielding.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only flotation_lava`. The scenario asserts that the truck traverses lava, riders take zero heat or burn damage, and Molten Tire Trample ignites impacted targets.
- **Liquid start from rest.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only liquid_start_water,liquid_start_lava`. The scenario asserts <= 0.10 block drift over 20 idle ticks, immediate forward propulsion on W, steering deflection on A/D, and deceleration to rest on throttle release in both liquids.
- **Shoreline Step-Up verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only shoreline_step`. The scenario asserts climbing flush, 1-block, and 2-block banks in water and lava within 20 ticks without jumping, with rider unhurt.
- **Shoreline 3-block wall refusal.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only shoreline_wall`. The scenario asserts that driving against a 3-block vertical wall above liquid stops the truck for 20+ ticks without climbing past the face.
- **Client safe liquid dismount.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Client -Only sneak_exits_afloat,sneak_stays_seated_over_lava -Trace`. The runner asserts that sneaking near land places the player on dry ground, while sneaking over lava with no land in reach keeps the player safely in the cab.

## Gotchas

- Bank height is measured from the liquid surface: banks 1 or 2 blocks above the water/lava surface are climbed, but walls 3 or more blocks above the liquid surface stop the vehicle.
- If a player deliberately exits over deep lava with no land within 4 blocks, the vehicle re-seats the player to prevent lava deaths.
- Once a player dismounts onto land, personal fire protection from the vehicle ceases; entering lava on foot will burn the player normally.
