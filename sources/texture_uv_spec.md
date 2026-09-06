# Monster Truck Texture UV Specification

## Texture Dimensions
- Resolution: 256x256 RGBA PNG
- Target Path: `resource_packs/MonsterTruck_RP/textures/entity/monster_truck.png`

## Atlas Regions & UV Coordinates

| Region | UV Origin [U, V] | Dimensions (Pixels) | Target Bones / Cubes | Description |
|---|---|---|---|---|
| Lower Chassis / Base | `[0, 0]` | 120 x 60 | `body` (lower cube) | Main chassis body and side panels |
| Cab & Windows | `[0, 64]` | 90 x 56 | `body` (cab cube) | Driver cabin, windshield, side windows |
| Hood & Front Grille | `[96, 64]` | 64 x 56 | `body` (hood cube) | Elevated hood, front grille, headlights |
| Front Left Wheel | `[0, 144]` | 38 x 36 | `wheel_fl` | Tire tread, sidewall, yellow/gold hub |
| Front Right Wheel | `[40, 144]` | 38 x 36 | `wheel_fr` | Tire tread, sidewall, yellow/gold hub |
| Rear Left Wheel | `[80, 144]` | 38 x 36 | `wheel_rl` | Tire tread, sidewall, yellow/gold hub |
| Rear Right Wheel | `[120, 144]` | 38 x 36 | `wheel_rr` | Tire tread, sidewall, yellow/gold hub |
| Roll Cage & Metal Accents | `[0, 190]` | 60 x 50 | `roll_cage` | Tubular roll cage and roof bars |

## Guidelines for Pixel Artists
1. Maintain sharp pixel edges with nearest-neighbor scaling (no antialiasing or bilinear blur).
2. Transparent alpha is permitted on exterior decorative areas and roll cage gaps.
3. Keep wheel hubs centered on the outer tire faces for authentic wheel spinning visuals.
