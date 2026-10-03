// What the truck's tires and bumper do to the entities they touch: Tire Trample, Molten Tire
// Trample, heavy collisions (ADR-0008), and the per-truck, per-entity hit cooldown.
// truck_tick.js calls stepContact once per tick; landing.js reuses isProtectedTarget and
// damageEntity for Crush Stomp. Must not import @minecraft/server, so node can load it.

import { CONTACT_PERIMETER, TRUCK_LENGTH, TRUCK_WIDTH } from "./geometry.js";

// EntityDamageCause value (@minecraft/server), spelled out so node can load this module.
/** @type {import("./truck_tick.js").DamageCause} */
const ENTITY_ATTACK_DAMAGE = "entityAttack";
// Entities near enough to the truck to be checked against the contact perimeter.
const CONTACT_SEARCH_RADIUS = 4.5;
// Ticks before the same entity can be trampled again.
export const HIT_COOLDOWN_TICKS = 6;
// Ticks after leaving lava during which the tires ignite what they trample (10 s).
export const MOLTEN_TIRE_TICKS = 200;
const MOLTEN_BURN_SECONDS = 6;

/**
 * Damage an entity as the truck, falling back to a plain hit if the engine rejects the options.
 * @param {Pick<import("./truck_tick.js").WorldEntity, "applyDamage">} target
 * @param {number} amount
 * @param {import("./truck_tick.js").DamageCause} cause
 * @param {import("./truck_tick.js").TruckEntity} truck
 */
export function damageEntity(target, amount, cause, truck) {
  /** @type {import("./truck_tick.js").DamageOptions} */
  const damageOptions = { cause, damagingEntity: truck };
  try {
    target.applyDamage(amount, damageOptions);
  } catch {
    try { target.applyDamage(amount); } catch {}
  }
}

function igniteIfMolten(target, moltenUntil, tick) {
  if (moltenUntil && tick < moltenUntil) {
    try {
      target.setOnFire(MOLTEN_BURN_SECONDS, true);
    } catch {}
  }
}

/**
 * Trample or ram every unprotected entity inside the contact perimeter this tick.
 * @param {import("./truck_tick.js").TruckEntity} truck
 * @param {import("./truck_tick.js").WorldDimension} dimension
 * @param {{
 *   location: import("./truck_tick.js").Vector3,
 *   heading: { x: number, z: number },
 *   speed: number,
 *   moltenUntil?: number,
 *   hitCooldowns: Map<string, number>,
 *   tick: number,
 * }} contact heading is the unit direction of travel; speed is blocks/tick; moltenUntil is
 *   the tick Molten Tire Trample ends; hitCooldowns is this truck's own map of entity id -> tick
 *   it last trampled that entity (expired entries are pruned here).
 */
export function stepContact(truck, dimension, { location, heading, speed, moltenUntil, hitCooldowns, tick }) {
  for (const [targetId, lastHit] of hitCooldowns) {
    if (tick - lastHit >= HIT_COOLDOWN_TICKS) hitCooldowns.delete(targetId);
  }
  if (!canApplyTireTrample(speed, false)) return;
  try {
    const nearbyEntities = dimension.getEntities({
      location,
      maxDistance: CONTACT_SEARCH_RADIUS,
    });

    for (const target of nearbyEntities) {
      if (isProtectedTarget(target, truck)) continue;
      if (!isInContactPerimeter(target.location, location, heading, TRUCK_WIDTH, TRUCK_LENGTH, CONTACT_PERIMETER)) {
        continue;
      }

      const lastHit = hitCooldowns.get(target.id) || 0;
      if (tick - lastHit < HIT_COOLDOWN_TICKS) continue;
      hitCooldowns.set(target.id, tick);

      if (isHeavyEntity(target)) {
        const heavyRes = resolveHeavyCollision(speed, heading);
        if (heavyRes.truckHalted) {
          try {
            truck.clearVelocity();
            truck.applyImpulse(heavyRes.truckPenaltyImpulse);
          } catch {}
        } else if (heavyRes.targetShoved) {
          try {
            target.applyImpulse(heavyRes.targetImpulse);
            truck.applyImpulse(heavyRes.truckPenaltyImpulse);
          } catch {}
        }

        if (heavyRes.damage > 0) {
          damageEntity(target, heavyRes.damage, ENTITY_ATTACK_DAMAGE, truck);
          igniteIfMolten(target, moltenUntil, tick);
        }
      } else {
        // Regular trample knockback and damage without halting the truck
        const damage = calculateTrampleDamage(speed);
        if (damage > 0) {
          const impulse = calculateKnockbackImpulse(target.location, location, speed);
          try {
            target.applyImpulse(impulse);
          } catch {}
          damageEntity(target, damage, ENTITY_ATTACK_DAMAGE, truck);
          igniteIfMolten(target, moltenUntil, tick);
        }
      }
    }
  } catch {}
}

export function calculateTrampleDamage(speed) {
  // Parked, idling, or crawling (<0.08 blocks/tick) inflicts no damage
  if (!speed || speed <= 0.08) {
    return 0;
  }
  // Dynamic scaling with velocity:
  // 0.15 blocks/tick -> ~18 damage
  // 0.35 blocks/tick -> ~42 crushing damage
  // 0.50 blocks/tick -> ~60 lethal crushing damage
  return Math.round(speed * 120);
}

export function canApplyTireTrample(speed, isAirborne) {
  return !isAirborne && calculateTrampleDamage(speed) > 0;
}

export function isInContactPerimeter(
  targetLoc,
  truckLoc,
  heading = { x: 1, z: 0 },
  width = TRUCK_WIDTH,
  length = TRUCK_LENGTH,
  perimeter = CONTACT_PERIMETER
) {
  if (!targetLoc || !truckLoc) return false;

  const dx = targetLoc.x - truckLoc.x;
  const dz = targetLoc.z - truckLoc.z;
  const dy = (targetLoc.y !== undefined ? targetLoc.y : truckLoc.y) - truckLoc.y;

  // Must be in vertical range of truck chassis and wheels
  if (Math.abs(dy) > 2.5) {
    return false;
  }

  // Heading normalization
  const hDist = Math.hypot(heading.x, heading.z) || 1;
  const dirX = heading.x / hDist;
  const dirZ = heading.z / hDist;
  const perpX = -dirZ;
  const perpZ = dirX;

  // Project onto truck-relative coordinates
  const localForward = dx * dirX + dz * dirZ;
  const localLateral = dx * perpX + dz * perpZ;

  const halfLength = length / 2;
  const halfWidth = width / 2;

  const distForward = Math.max(0, Math.abs(localForward) - halfLength);
  const distLateral = Math.max(0, Math.abs(localLateral) - halfWidth);
  const distanceOutside = Math.hypot(distForward, distLateral);

  return distanceOutside <= perimeter;
}

export function calculateKnockbackImpulse(targetLoc, truckLoc, speed = 0.3) {
  const kx = targetLoc.x - truckLoc.x;
  const kz = targetLoc.z - truckLoc.z;
  const dist = Math.hypot(kx, kz) || 1;

  const normX = kx / dist;
  const normZ = kz / dist;

  const effectiveSpeed = Math.max(0.1, speed);
  const strength = Math.min(1.8, Math.max(0.6, effectiveSpeed * 2.5));

  return {
    x: normX * strength,
    y: 0.25 + effectiveSpeed * 0.3,
    z: normZ * strength,
  };
}

export function isProtectedTarget(target, truck) {
  if (!target) return true;
  if (truck && target.id === truck.id) return true;

  const typeId = target.typeId || "";

  // Vehicles, projectiles, dropped items, xp orbs
  if (
    typeId === "blake:monster_truck" ||
    typeId.includes("projectile") ||
    typeId.includes("arrow") ||
    typeId === "minecraft:item" ||
    typeId === "minecraft:xp_orb" ||
    typeId.includes("boat") ||
    typeId.includes("minecart")
  ) {
    return true;
  }

  // Players are protected (multiplayer friendly fire protection)
  if (typeId === "minecraft:player") {
    return true;
  }

  // Check if rider of the truck
  if (truck && truck.getComponent) {
    try {
      const rideable = truck.getComponent("minecraft:rideable");
      const riders = rideable && rideable.getRiders ? rideable.getRiders() : [];
      if (riders.some((r) => r.id === target.id)) {
        return true;
      }
    } catch {}
  }

  // Tamed companions (wolves, cats, parrots, horses, etc.)
  if (target.isTamed === true) return true;
  if (target.hasTag) {
    if (target.hasTag("tamed") || target.hasTag("minecraft:is_tamed")) {
      return true;
    }
  }
  if (target.getComponent) {
    try {
      const tameable = target.getComponent("minecraft:tameable");
      if (tameable && tameable.isTamed) return true;
      const isTamed = target.getComponent("minecraft:is_tamed");
      if (isTamed) return true;
    } catch {}
  }

  return false;
}

export function isHeavyEntity(target) {
  if (!target) return false;
  const typeId = target.typeId || "";
  if (typeId === "minecraft:iron_golem" || typeId === "minecraft:warden") {
    return true;
  }
  if (target.getComponent) {
    try {
      const kb = target.getComponent("minecraft:knockback_resistance");
      if (kb && kb.value >= 1.0) return true;
    } catch {}
  }
  return false;
}

export function resolveHeavyCollision(speed, heading = { x: 1, z: 0 }) {
  const hDist = Math.hypot(heading.x, heading.z) || 1;
  const dirX = heading.x / hDist;
  const dirZ = heading.z / hDist;

  // Top speed threshold: > 0.32 blocks/tick
  if (speed > 0.32) {
    return {
      truckHalted: false,
      targetShoved: true,
      truckDecelerated: true,
      damage: Math.max(50, Math.round(speed * 160)),
      targetImpulse: { x: dirX * 0.7, y: 0.2, z: dirZ * 0.7 },
      truckPenaltyImpulse: { x: -dirX * 0.18, y: 0, z: -dirZ * 0.18 },
    };
  }

  // Low-to-medium speed: truck halted dead on impact
  return {
    truckHalted: true,
    targetShoved: false,
    truckDecelerated: false,
    damage: calculateTrampleDamage(speed),
    targetImpulse: { x: 0, y: 0, z: 0 },
    truckPenaltyImpulse: { x: -dirX * 0.05, y: 0, z: -dirZ * 0.05 },
  };
}
