import { system, world } from "@minecraft/server";
import { isFoliage, isDestructibleWoodOrGlass } from "./demolition.js";

// Track state of each truck across ticks
const truckStates = new Map();
const DIMENSIONS = ["overworld", "nether", "the_end"];

function onTick() {
  for (const dimName of DIMENSIONS) {
    let dimension;
    try {
      dimension = world.getDimension(dimName);
    } catch {
      continue;
    }
    if (!dimension) continue;

    let trucks;
    try {
      trucks = dimension.getEntities({ type: "blake:monster_truck" });
    } catch {
      continue;
    }

    for (const truck of trucks) {
      if (!truck || !truck.isValid) continue;

      const loc = truck.location;
      const state = truckStates.get(truck.id) || {
        prevX: loc.x,
        prevY: loc.y,
        prevZ: loc.z,
      };

      const dx = loc.x - state.prevX;
      const dy = loc.y - state.prevY;
      const dz = loc.z - state.prevZ;

      // Update state for next tick
      state.prevX = loc.x;
      state.prevY = loc.y;
      state.prevZ = loc.z;
      truckStates.set(truck.id, state);

      const horizontalDist = Math.hypot(dx, dz);
      let velSpeed = 0;
      let vel;
      try {
        vel = truck.getVelocity ? truck.getVelocity() : undefined;
        if (vel) {
          velSpeed = Math.hypot(vel.x, vel.z);
        }
      } catch {}

      const effectiveSpeed = Math.max(horizontalDist, velSpeed);

      // Momentum threshold: > 0.25 blocks/tick
      if (effectiveSpeed <= 0.25) {
        continue;
      }

      // Compute heading vector
      let dirX = 0;
      let dirZ = 0;
      if (horizontalDist > 0.01) {
        dirX = dx / horizontalDist;
        dirZ = dz / horizontalDist;
      } else if (vel && velSpeed > 0.01) {
        dirX = vel.x / velSpeed;
        dirZ = vel.z / velSpeed;
      } else {
        try {
          const rot = truck.getRotation();
          const rad = (rot.y + 90) * (Math.PI / 180);
          dirX = Math.cos(rad);
          dirZ = Math.sin(rad);
        } catch {
          dirX = 1;
          dirZ = 0;
        }
      }

      // Perpendicular vector for lateral width
      const perpX = -dirZ;
      const perpZ = dirX;

      const sampledBlocks = new Set();
      const forwardDistances = [1.2, 1.8, 2.5];
      const lateralOffsets = [-1.2, -0.6, 0.0, 0.6, 1.2];
      const baseY = Math.floor(loc.y + 0.05);

      for (const fwd of forwardDistances) {
        for (const lat of lateralOffsets) {
          const px = Math.floor(loc.x + dirX * fwd + perpX * lat);
          const pz = Math.floor(loc.z + dirZ * fwd + perpZ * lat);

          // Foliage cleared up to 5 blocks high (0..4), wood/glass up to 3 blocks high (0..2)
          for (let h = 0; h < 5; h++) {
            const py = baseY + h;
            const key = `${px},${py},${pz}`;
            if (sampledBlocks.has(key)) continue;
            sampledBlocks.add(key);

            try {
              const block = dimension.getBlock({ x: px, y: py, z: pz });
              if (!block || block.isAir || block.typeId === "minecraft:air") continue;

              const typeId = block.typeId;

              // Foliage vaporization (clean without item drops)
              if (isFoliage(typeId)) {
                block.setType("minecraft:air");
              }
              // Structural wood & glass demolition (drops survival items, plays break sound/particles)
              else if (h < 3 && isDestructibleWoodOrGlass(typeId)) {
                dimension.runCommand(`setblock ${px} ${py} ${pz} air destroy`);
              }
            } catch {
              // Ignore blocks outside active simulation
            }
          }
        }
      }
    }
  }
}

// Subscribe tick loop
system.runInterval(onTick, 1);
