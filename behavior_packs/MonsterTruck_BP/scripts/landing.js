// The drop lifecycle of one truck: free-fall tracking, keeping riders seated and protected
// through a drop and its landing window, Pneumatic Shock Absorption on landing, and Crush
// Stomp (ADR-0017). truck_tick.js calls stepLanding once per tick with this module's slice of
// truck state; main.js's entityHurt handler asks absorbsFallDamage. Must not import
// @minecraft/server, so node can load it.
import { getSafeDismountLocation } from "./amphibious.js";
import { damageEntity, isProtectedTarget } from "./contact.js";

export const PNEUMATIC_VENT_SOUND = "random.fizz";
export const PNEUMATIC_DUST_PARTICLE = "minecraft:campfire_smoke_particle";
// Landings from at least this many blocks of drop crush the entities beneath (ADR-0017).
export const CRUSH_STOMP_MIN_DROP = 3;
// Ticks after a landing or an engine detachment during which riders are reseated and protected.
const RIDER_RETENTION_TICKS = 8;
const CRUSH_STOMP_RADIUS = 3.5;
// EntityDamageCause value (@minecraft/server), spelled out so node can load this module.
/** @type {import("./truck_tick.js").DamageCause} */
const CONTACT_DAMAGE = "contact";

/**
 * This module's slice of truck state.
 * isFalling: a drop is in progress. fallStartY: where it began.
 * riderRetentionUntil: last tick of the reseat/protection window.
 * protectedRiderIds: riders this truck has put in protectedRiders.
 * @typedef {{
 *   isFalling: boolean,
 *   fallStartY?: number,
 *   riderRetentionUntil?: number,
 *   protectedRiderIds: Set<string>,
 * }} LandingState
 */

/** @returns {LandingState} */
export function createLandingState() {
  return { isFalling: false, fallStartY: undefined, riderRetentionUntil: undefined, protectedRiderIds: new Set() };
}

export function isCrushStompLanding(dropHeight = 0) {
  return dropHeight >= CRUSH_STOMP_MIN_DROP;
}

export function calculateCrushStompDamage() {
  // At least 60 crush damage (lethal to standard hostiles)
  return 75;
}

export function calculateShockwaveImpulse(targetLoc, truckLoc, baseStrength = 1.5) {
  const sx = targetLoc.x - truckLoc.x;
  const sz = targetLoc.z - truckLoc.z;
  const dist = Math.hypot(sx, sz) || 1;

  return {
    x: (sx / dist) * baseStrength,
    y: 0.4, // Upward lift shockwave
    z: (sz / dist) * baseStrength,
  };
}

export function isFalling(deltaY = 0, verticalVelocity = 0) {
  return deltaY < -0.25 || verticalVelocity < -0.25;
}

export function calculateWheelContactOffsets(
  dir = { x: 1, z: 0 },
  perp = { x: 0, z: 1 },
  forwardDist = 1.3,
  lateralDist = 0.9
) {
  return [
    { x: dir.x * forwardDist + perp.x * lateralDist, z: dir.z * forwardDist + perp.z * lateralDist },
    { x: dir.x * forwardDist - perp.x * lateralDist, z: dir.z * forwardDist - perp.z * lateralDist },
    { x: -dir.x * forwardDist + perp.x * lateralDist, z: -dir.z * forwardDist + perp.z * lateralDist },
    { x: -dir.x * forwardDist - perp.x * lateralDist, z: -dir.z * forwardDist - perp.z * lateralDist },
  ];
}

/**
 * Pneumatic Shock Absorption: whether fall damage to this entity is cancelled. The truck never
 * takes fall damage; a rider only while protected by a drop (protectedRiders, rider id -> truck id).
 * @param {string | undefined} damageCause EntityDamageCause value
 * @param {{ id: string, typeId: string } | undefined} hurtEntity
 * @param {Map<string, string>} protectedRiders
 */
export function absorbsFallDamage(damageCause, hurtEntity, protectedRiders) {
  if (!hurtEntity) return false;
  const isTruck = hurtEntity.typeId === "blake:monster_truck";
  const isRider = protectedRiders.has(hurtEntity.id);
  if (!(isTruck || isRider)) return false;
  return damageCause === "fall" || damageCause === "damage.fall";
}

function protectRidersForLifecycle(protectedRiders, landing, truckId, riderIds) {
  landing.protectedRiderIds = new Set(riderIds);
  for (const riderId of landing.protectedRiderIds) {
    protectedRiders.set(riderId, truckId);
  }
}

function clearProtectedRiders(protectedRiders, landing) {
  for (const riderId of landing.protectedRiderIds || []) {
    protectedRiders.delete(riderId);
  }
  landing.protectedRiderIds = new Set();
}

/**
 * The truck is gone: end the fall protection it still holds for its riders.
 * @param {LandingState} landing
 * @param {string} truckId
 * @param {Map<string, string>} protectedRiders
 */
export function releaseLanding(landing, truckId, protectedRiders) {
  for (const riderId of landing.protectedRiderIds) {
    if (protectedRiders.get(riderId) === truckId) protectedRiders.delete(riderId);
  }
  landing.protectedRiderIds = new Set();
}

function restoreProtectedRiders(getEntity, landing, rideable) {
  if (!rideable?.addRider || !landing.protectedRiderIds?.size) return;
  const seated = new Set((rideable.getRiders?.() || []).map((rider) => rider.id));
  for (const riderId of landing.protectedRiderIds) {
    if (seated.has(riderId)) continue;
    try {
      const rider = getEntity(riderId);
      if (rider?.isValid && rider.typeId === "minecraft:player" && !rider.isSneaking) {
        rideable.addRider(rider);
      }
    } catch {}
  }
}

/**
 * Advance the drop lifecycle by one tick. Mutates landing and protectedRiders; acts on the
 * truck, its riders, and the entities it lands on.
 * @param {import("./truck_tick.js").TruckEntity} truck
 * @param {import("./truck_tick.js").WorldDimension} dimension
 * @param {LandingState} landing
 * @param {{
 *   location: import("./truck_tick.js").Vector3,
 *   dy: number,
 *   verticalVelocity: number,
 *   heading: { x: number, z: number },
 *   rideable: import("./truck_tick.js").Rideable | undefined,
 *   riderIds: string[],
 *   prevRiderIds: string[],
 *   inLiquid: boolean,
 *   tick: number,
 *   getEntity(id: string): import("./truck_tick.js").WorldEntity | undefined,
 *   protectedRiders: Map<string, string>,
 * }} frame dy: height change since last tick; heading: unit direction of travel;
 *   riderIds / prevRiderIds: seated rider ids this tick and last tick.
 */
export function stepLanding(truck, dimension, landing, frame) {
  const {
    location: loc,
    dy,
    verticalVelocity,
    heading,
    rideable,
    riderIds,
    prevRiderIds,
    inLiquid,
    tick: tickNumber,
    getEntity,
    protectedRiders
  } = frame;
  const dirX = heading.x;
  const dirZ = heading.z;
  const perpX = -dirZ;
  const perpZ = dirX;
  const falling = isFalling(dy, verticalVelocity);

  // Rider dismount management: Sneak (Shift) is the only deliberate exit
  if (prevRiderIds.length > riderIds.length) {
    const currentRiderIds = new Set(riderIds);
    const dismountedIds = prevRiderIds.filter((id) => !currentRiderIds.has(id));
    const safePos = getSafeDismountLocation(loc, { x: dirX, z: dirZ });
    for (const playerId of dismountedIds) {
      try {
        const player = getEntity(playerId);
        if (player && player.isValid && player.typeId === "minecraft:player") {
          if (!player.isSneaking && rideable && rideable.addRider) {
            // Sneak is the only deliberate exit. Keep any other engine
            // detachment tied to a bounded vehicle lifecycle.
            if (!landing.protectedRiderIds?.size) {
              protectRidersForLifecycle(protectedRiders, landing, truck.id, prevRiderIds);
            }
            landing.riderRetentionUntil = tickNumber + RIDER_RETENTION_TICKS;
            if (falling && !landing.isFalling) {
              landing.isFalling = true;
              landing.fallStartY = loc.y - dy;
            }
            rideable.addRider(player);
          } else if (inLiquid) {
            // Deliberate sneak dismount over liquid: teleport to safe shoreline
            player.teleport(safePos, { dimension });
            protectedRiders.delete(playerId);
            landing.protectedRiderIds?.delete(playerId);
          } else {
            protectedRiders.delete(playerId);
            landing.protectedRiderIds?.delete(playerId);
          }
        }
      } catch {}
    }
  }

  if (landing.isFalling ||
      (landing.riderRetentionUntil && tickNumber <= landing.riderRetentionUntil)) {
    restoreProtectedRiders(getEntity, landing, rideable);
  } else if (landing.riderRetentionUntil && tickNumber > landing.riderRetentionUntil) {
    clearProtectedRiders(protectedRiders, landing);
    delete landing.riderRetentionUntil;
  }

  // Free-fall tracking: remember where the drop began for Crush Stomp
  if (falling && !landing.isFalling) {
    landing.isFalling = true;
    landing.fallStartY = loc.y - dy;
    if (!landing.protectedRiderIds?.size) {
      protectRidersForLifecycle(protectedRiders, landing, truck.id, riderIds);
    }
  }

  // Pneumatic Shock Absorption & Landing Detection
  if (landing.isFalling) {
    const grounded = Boolean(truck.isOnGround);
    if (grounded && dy <= 0) {
      const crushes = isCrushStompLanding((landing.fallStartY ?? loc.y) - loc.y);
      landing.isFalling = false;
      landing.riderRetentionUntil = tickNumber + RIDER_RETENTION_TICKS;

      // Dissipate impact energy with pneumatic venting audio and quad wheel dust particles
      try {
        dimension.playSound(PNEUMATIC_VENT_SOUND, loc, { volume: 1.0, pitch: 0.85 });
        const wheelOffsets = calculateWheelContactOffsets({ x: dirX, z: dirZ }, { x: perpX, z: perpZ });
        for (const offset of wheelOffsets) {
          dimension.spawnParticle(PNEUMATIC_DUST_PARTICLE, {
            x: loc.x + offset.x,
            y: loc.y + 0.15,
            z: loc.z + offset.z
          });
        }
      } catch {}

      if (crushes) {
        const crushDamage = calculateCrushStompDamage();
        try {
          const nearby = dimension.getEntities({ location: loc, maxDistance: CRUSH_STOMP_RADIUS });
          for (const target of nearby) {
            if (isProtectedTarget(target, truck)) continue;

            const shockImpulse = calculateShockwaveImpulse(target.location, loc, 1.5);
            try { target.applyImpulse(shockImpulse); } catch {}

            damageEntity(target, crushDamage, CONTACT_DAMAGE, truck);
          }

          dimension.playSound("random.explode", loc, { volume: 0.8, pitch: 1.4 });
          dimension.spawnParticle("minecraft:large_explosion", { x: loc.x, y: loc.y + 0.3, z: loc.z });
        } catch {}
      }
    }
  }
}
