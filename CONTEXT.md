# Monster Truck Domain

This domain encompasses the vehicle entities, player driving mechanics, audio systems, and survival integration for the Minecraft Bedrock Monster Truck Add-on.

## Language

**Monster Truck**:
A high-clearance, two-seat ground vehicle entity (`blake:monster_truck`) capable of traversing 2-block stepped terrain with direct WASD player control.
_Avoid_: Car, mob, mount, horse

**Driver Seat**:
The primary controlling seat (seat index 0) positioned on the front-left of the cab, providing steering and acceleration control to the seated player.
_Avoid_: Cockpit, pilot, helm

**Passenger Seat**:
The secondary non-controlling seat (seat index 1) positioned alongside the driver, allowing a second player to ride without steering authority.
_Avoid_: Back seat, rumble seat

**Vehicle Item**:
The portable inventory form of the Monster Truck returned by deliberate player retrieval and crafted for deterministic red deployment. It is distinct from the randomized Creative spawn egg.
_Avoid_: Car block, generic spawn egg

**Scrap**:
The raw metallic materials (such as iron ingots) dropped when a Monster Truck is fatally destroyed by environmental hazards or combat rather than retrieved.
_Avoid_: Junk, debris, trash

**Controlled Auto-Step**:
The vehicle's mechanical ability to climb full 2-block vertical obstacles while actively driven, without requiring player jump input.
_Avoid_: Jumping, vaulting, flying

**Cab Interior View**:
The in-cabin seated perspective positioning the rider's eye-line directly level with the transparent windshield, providing an unobstructed forward sightline over the sloped hood.
_Avoid_: Roof view, top view, external cam

**Wood Demolition**:
The vehicle's capability to fracture and clear wooden blocks, structural furniture, and glass when driven forward at momentum.
_Avoid_: Mining, digging, block breaking

**Foliage Shearing**:
The vehicle's continuous contact clearing of leaves, vines, and canopy overhangs, active even at low or resting speeds to prevent vehicle entanglement under trees.
_Avoid_: Tree cutting, trimming, defoliation

**Tire Trample**:
The speed-scaled impact damage and directional knockback exerted on non-allied entities by the vehicle's rolling wheels.
_Avoid_: Roadkill, run-over, melee attack

**Dedicated Test World**:
A disposable Minecraft Bedrock world reserved for repeatable verification of the Monster Truck add-on, separate from personal gameplay worlds.
_Avoid_: Personal world, production world

**Suspension Jump**:
The active, driver-triggered vertical launch that propels the vehicle upward to clear 3-block obstacles or ravines.
_Avoid_: Jumping, hop, rocket jump, bounce

**Amphibious Flotation**:
The vehicle's continuous buoyancy and high-traction liquid propulsion enabling it to navigate and maneuver across water and lava surfaces at full overland cruising speed using giant tire displacement.
_Avoid_: Boat mode, swimming, hydroplaning

**Shoreline Step-Up**:
The vehicle's automated liquid-to-land climbing transition that elevates the vehicle up onto shoreline banks from water or lava without halting or requiring manual jumps.
_Avoid_: Hopping, beaching, docking

**Molten Tire Trample**:
The superheated offensive state triggered by traversing lava, causing the truck's wheels to ignite impacted mobs with fire tick damage alongside standard collision impact.
_Avoid_: Fire ram, flaming wheels, burn attack

**Crush Stomp**:
The high-impact downward kinetic force and radial knockback inflicted on entities beneath the vehicle when landing from a Suspension Jump.
_Avoid_: Ground pound, butt slam, crash landing

**Pneumatic Shock Absorption**:
The complete kinetic dampening provided by the vehicle's massive tires and heavy-duty suspension, providing 100% fall damage immunity to both the vehicle and its seated riders upon high drops and jumps, accompanied by pneumatic venting audio and impact dust particles.
_Avoid_: Fall damage negation, soft landing, cushioned fall

**Dynamic Incline Pitch**:
The dual-axle terrain-contour visual pitch tilt of the vehicle chassis and wheels conforming to hill climbs and descents with damped transitions and airborne trajectory alignment.
_Avoid_: Tilt, lean, slope lock, pitch glitch

**Coordinated Four-Wheel Steering**:
The counter-phase lateral angular deflection of front and rear wheel assemblies driven by turning rate with dynamic hydraulic spring-return centering.
_Avoid_: Wheel turning, car turn, crab steering

**Sixteen-Color Palette**:
The complete spectrum of 16 vanilla Minecraft dye colors (`red`, `blue`, `green`, `yellow`, `black`, `white`, `orange`, `magenta`, `light_blue`, `lime`, `pink`, `gray`, `light_gray`, `cyan`, `purple`, `brown`) supported for vehicle chassis and wheel-hub accent customization.
_Avoid_: 6-color palette, dye list, partial colors

**Textured Color Swatches**:
The high-contrast, pre-baked body and hood textures generated with matching wheel-hub accent plates for each of the 16 supported palette colors.
_Avoid_: Skin, wrap, paint job

**Sneak-Dye Repainting**:
The non-destructive player interaction mechanic where sneaking (holding Shift / Sneak) while interacting with a monster truck holding any vanilla dye instantaneously repaints the vehicle without consuming or expending the dye item.
_Avoid_: Painting, consuming dye, wash

**Randomized Spawn Egg Placement**:
The Creative mode spawn sequence (`blake:random_color_on_spawn`) that automatically evaluates a weighted uniform randomization branch upon spawn egg placement, assigning a random color from the Sixteen-Color Palette to newly placed vehicles.
_Avoid_: Fixed red spawn, egg color lock


