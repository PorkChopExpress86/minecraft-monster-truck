import { system, world, EntityDamageCause } from "@minecraft/server";
import { isFoliage, isDestructibleWoodOrGlass } from "./demolition.js";
import {
  calculateTrampleDamage,
  isInContactPerimeter,
  calculateKnockbackImpulse,
  isProtectedTarget,
  isHeavyEntity,
  resolveHeavyCollision
} from "./trample.js";

// Track state of each truck across ticks
const truckStates = new Map();
const entityHitCooldowns = new Map();
let currentTick = 0;
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

      currentTick++;

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

      // Tire trample check (within 1.6 blocks contact perimeter)
      if (effectiveSpeed > 0.08) {
        try {
          const nearbyEntities = dimension.getEntities({
            location: loc,
            maxDistance: 4.5,
          });

          for (const target of nearbyEntities) {
            if (isProtectedTarget(target, truck)) continue;

            if (
              isInContactPerimeter(
                target.location,
                loc,
                { x: dirX, z: dirZ },
                2.25,
                3.6,
                1.6
              )
            ) {
              const lastHit = entityHitCooldowns.get(target.id) || 0;
              if (currentTick - lastHit < 6) continue;
              entityHitCooldowns.set(target.id, currentTick);

              if (isHeavyEntity(target)) {
                const heavyRes = resolveHeavyCollision(effectiveSpeed, { x: dirX, z: dirZ });
                if (heavyRes.truckHalted) {
                  try {
                    truck.clearVelocity();
                    truck.applyImpulse(heavyRes.truckPenaltyImpulse);
                  } catch {}
                  state.prevX = loc.x;
                  state.prevY = loc.y;
                  state.prevZ = loc.z;
                } else if (heavyRes.targetShoved) {
                  try {
                    target.applyImpulse(heavyRes.targetImpulse);
                    truck.applyImpulse(heavyRes.truckPenaltyImpulse);
                  } catch {}
                }

                const damage = heavyRes.damage;
                if (damage > 0) {
                  const damageOptions = {};
                  if (typeof EntityDamageCause !== "undefined" && EntityDamageCause?.entityAttack) {
                    damageOptions.cause = EntityDamageCause.entityAttack;
                  }
                  damageOptions.damagingEntity = truck;
                  try {
                    target.applyDamage(damage, damageOptions);
                  } catch {
                    try { target.applyDamage(damage); } catch {}
                  }
                }
              } else {
                // Regular trample knockback and damage without halting the truck
                const damage = calculateTrampleDamage(effectiveSpeed);
                if (damage > 0) {
                  const impulse = calculateKnockbackImpulse(
                    target.location,
                    loc,
                    effectiveSpeed
                  );
                  try {
                    target.applyImpulse(impulse);
                  } catch {}

                  const damageOptions = {};
                  if (
                    typeof EntityDamageCause !== "undefined" &&
                    EntityDamageCause?.entityAttack
                  ) {
                    damageOptions.cause = EntityDamageCause.entityAttack;
                  }
                  damageOptions.damagingEntity = truck;

                  try {
                    target.applyDamage(damage, damageOptions);
                  } catch {
                    try {
                      target.applyDamage(damage);
                    } catch {}
                  }
                }
              }
            }
          }
        } catch {}
      }

      // Momentum threshold for wood demolition: > 0.25 blocks/tick
      if (effectiveSpeed <= 0.25) {
        continue;
      }

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
