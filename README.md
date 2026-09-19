# Monster Truck for Minecraft Bedrock

A lifted, two-seat monster pickup with oversized octagonal tires, chunky tread, exposed axles and suspension, an open cargo bed, and sixteen paint colors. Includes authentic engine audio, survival crafting, controlled two-block auto-step, dynamic incline pitch, coordinated four-wheel steering, wood demolition, foliage shearing, suspension jumping, and amphibious liquid traversal.

![Six monster truck paint colors in the automated test world](docs/images/monster-truck-colors.png)

## Choose a color

Vehicles spawn in a randomized color when placed using the Creative spawn egg, or default to **red** when crafted in Survival or summoned via `/summon blake:monster_truck`. To repaint one, hold any of the 16 vanilla Minecraft dyes, **sneak**, and **interact with the truck** (Shift + right-click on Windows). Dye is reusable and is not consumed. Interact normally without sneaking to mount the truck.

| Paint | Item | Paint | Item |
|---|---|---|---|
| Red | Red dye | Light Blue | Light Blue dye |
| Blue | Blue dye | Lime | Lime dye |
| Green | Green dye | Pink | Pink dye |
| Yellow | Yellow dye | Gray | Gray dye |
| Black | Black dye | Light Gray | Light Gray dye |
| White | White dye | Cyan | Cyan dye |
| Orange | Orange dye | Purple | Purple dye |
| Magenta | Magenta dye | Brown | Brown dye |

![Monster truck close-up captured in Minecraft](docs/images/monster-truck-closeup.png)

Colors change the body, hood, roof, and wheel-hub accents. Tires stay dark, with silver metalwork and pale headlights.

## Heavy-duty stats & abilities

| Stat | Value |
|---|---|
| Health | 1,000 HP (500 hearts) |
| Damage received (melee, projectile, explosion) | 25% of normal |
| Fall damage | None (100% Pneumatic Shock Absorption) |
| Movement attribute | 0.55 |
| Controlled Auto-step height | 2 blocks |
| Suspension Jump clearance | 3 blocks (Spacebar, 1.2s cooldown) |
| Tire Trample damage | Speed-scaled (up to lethal impact) with outward knockback |

The Monster Truck is built for extreme demolition and all-terrain traversal:
- **Controlled Auto-Step**: Climbs 2-block vertical ledges smoothly without requiring jump input.
- **Wood Demolition & Foliage Shearing**: Smashes through wooden logs, planks, fences, and glass windows at momentum (dropping materials), while shearing leaves and vines on contact without drops to prevent entity lag.
- **Suspension Jump & Crush Stomp**: Tap Spacebar to launch 3 blocks upward to clear walls and chasms, delivering a 60+ damage radial Crush Stomp when landing onto hostile mobs.
- **Amphibious Flotation & Shoreline Step-Up**: Oversized tires cruise across water and lava lakes at overland speeds, shielding seated riders from heat, and climbing back onto dry land automatically.
- **Molten Tire Trample**: Traversing lava superheats the wheels for 10 seconds, setting impacted mobs ablaze upon collision.
- **Dynamic Incline Pitch & Coordinated Four-Wheel Steering**: Dual-axle ground contour probing tilts the chassis up to $\pm 35^\circ$ on hills, while front wheels steer and rear wheels counter-steer up to $\pm 18^\circ$ with hydraulic centering.

## Install and play

1. Build the add-on with `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Static`.
2. Open `dist/MonsterTruck.mcaddon` to import it into Minecraft Bedrock for Windows.
3. Activate **Monster Truck Behavior** in a world's Behavior Packs; its resource pack is linked automatically.
4. Use the Creative spawn egg, the [survival recipe](docs/RECIPE_GUIDE.md), or `/summon blake:monster_truck ~ ~ ~`.

The truck has a driver seat (Seat 0, left door) and a passenger seat (Seat 1, right door). Use standard WASD controls while driving, Spacebar to trigger a Suspension Jump, and sneak (Shift) to dismount. See the [proving-ground guide](docs/PROVING_GROUND.md) for the controls and obstacle checklist.

## Automated tests and screenshots

With Python 3.11+ installed and Minecraft initialized and closed, run:

```powershell
powershell.exe -NoProfile -File .\Test-Addon.ps1
```

The command prepares its Python environment, creates a dedicated flat test world, enables content logging with a settings backup, deploys the test packs, and launches Minecraft. It checks all 16 color events, the required components, both seats, armor, fall protection, parked contact safety, moving run-over damage, and a two-block ledge crossed using horizontal impulses; collects screenshots from multiple camera angles; checks the final content log; and closes the client normally.

Reports and original screenshots are under `dist/bedrock-tests/<run-id>/`. The images above are actual Minecraft captures from that workflow. Showcase trucks stay in the dedicated test world for inspection and are replaced on the next run. Other worlds are not used for testing.

Screenshots document appearance; automated color-event checks do not simulate a player's dye click or driving controls. Those interactions remain in the [manual proving-ground checklist](docs/PROVING_GROUND.md).

See [Windows testing](docs/WINDOWS_TESTING.md) for configuration and the reusable `minecraft-addon-testing` skill. Production vehicle physics, demolition, kinematics, and amphibious traversal are powered by the Bedrock Script API (`@minecraft/server`).
