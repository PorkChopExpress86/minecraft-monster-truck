# Canopy Clearance and Amphibious Flotation Architecture

This supersedes the foliage momentum requirement in ADR-0009 and expands the passive buoyancy model in ADR-0010.

We decided to reduce the entity collision box height from 2.15 to 1.95 blocks and decouple Foliage Shearing from the momentum threshold, while upgrading Amphibious Flotation from passive buoyancy to active high-traction propulsion across water and lava.

### Context & Trade-offs
1. **Canopy Clearance vs Visual Height**:
   - The Blockbench visual model represents a massive high-clearance truck, but a 2.15-block collision box wedges under Minecraft's standard 2.0-block tree canopies and low overhangs. Once stopped, momentum dropped below the 0.25 blocks/tick demolition threshold, leaving the vehicle permanently trapped.
   - Reducing collision height to 1.95 blocks allows standard 2-block canopy navigation without altering the visual model.
   - Decoupling Foliage Shearing from the momentum threshold allows leaves, vines, and canopy overhangs to be vaporized immediately on contact at zero speed, while structural wood (logs, planks, fences) preserves the 0.25 speed requirement to prevent accidental demolition of player structures when parking.

2. **Amphibious Flotation & Shoreline Step-Up**:
   - Native Bedrock buoyant physics with `movement_type: "none"` disables horizontal player input when floating. Setting `movement_type: "player_controlled"` in component data and injecting active directional propulsion in `main.js` delivers full overland cruising speed (0.55 blocks/tick) and steering authority across both water and lava.
   - Shoreline transitions previously failed because auto-step requires existing ground contact velocity. The automated Shoreline Step-Up detects shoreline banks (up to 2 blocks above liquid level) and applies an upward-forward transition impulse, enabling seamless egress back onto dry land without requiring manual jump inputs.
