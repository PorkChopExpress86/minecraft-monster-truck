# Monster Truck model and texture source

Run `python scripts/make_truck_geometry.py` to rebuild the lifted pickup geometry. Run `python scripts/make_placeholder_textures.py` to rebuild its six 256 x 256 atlases and existing icons.

The model uses explicit per-face 1 x 1 UV swatches, avoiding box-UV spill into unrelated atlas regions. Coordinates are Minecraft model units (16 per block).

| Material | Atlas sample |
|---|---|
| Paint | 20, 20 |
| Dark paint / graphics / hubs | 110, 80 |
| Glass | 20, 80 |
| Tire / bed / seats | 10, 155 |
| Raised tread | 0, 144 |
| Silver metal | 20, 205 |
| Headlights | 40, 220 |

The four wheel bones retain their animation names and rotate around axle centers at height 12. Intersecting rotated cubes form octagonal tires with separate radial tread blocks and outer hubs. The raised body floor starts at height 24; the roof reaches 45. Cab side windows and the pickup bed remain open. Existing two-seat positions are retained above the cab floor.

The visual overhaul includes:
- **Exposed V8 Engine & Supercharger**: High-detail engine block in the front engine bay, dual valve covers, polished metal supercharger blower rising through the hood, triple-butterfly scoop air intake, and dual 4-pipe side exhaust zoomie headers.
- **Roll Cage**: Structural roll cage inside the cab and diagonal support bars extending into the rear pickup bed under the `roll_cage` bone.
- **Realistic 4-Link Suspension**: Heavy-duty live axles, center chassis crossmembers, lower and upper triangulated 4-link trailing control arms, steering tie-rod links, and dual-reservoir nitrogen coilover shocks at every corner.

Red is the default atlas; blue, green, yellow, black and white use the same swatches and mesh. Color variants alter only the two paint regions. Metal and lamp swatches are shared across every color.

