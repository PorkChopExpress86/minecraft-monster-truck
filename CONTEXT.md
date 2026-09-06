# Monster Truck Domain

This domain encompasses the vehicle entities, player driving mechanics, audio systems, and survival integration for the Minecraft Bedrock Monster Truck Add-on.

## Language

**Monster Truck**:
A high-clearance, two-seat ground vehicle entity (`blake:monster_truck`) capable of traversing 1-block stepped terrain with direct WASD player control.
_Avoid_: Car, mob, mount, horse

**Driver Seat**:
The primary controlling seat (seat index 0) positioned on the front-left of the cab, providing steering and acceleration control to the seated player.
_Avoid_: Cockpit, pilot, helm

**Passenger Seat**:
The secondary non-controlling seat (seat index 1) positioned alongside the driver, allowing a second player to ride without steering authority.
_Avoid_: Back seat, rumble seat

**Vehicle Item**:
The portable inventory item form of the Monster Truck dropped when deliberately broken or retrieved by a player, ready to deploy elsewhere.
_Avoid_: Spawn egg (in survival contexts), car block

**Scrap**:
The raw metallic materials (such as iron ingots) dropped when a Monster Truck is fatally destroyed by environmental hazards or combat rather than retrieved.
_Avoid_: Junk, debris, trash

**Controlled Auto-Step**:
The vehicle's mechanical ability to climb full 1-block vertical obstacles while actively driven, without requiring player jump input.
_Avoid_: Jumping, vaulting, flying
