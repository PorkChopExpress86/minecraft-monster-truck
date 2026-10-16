// The drop lifecycle of one truck: free-fall tracking, keeping riders seated and protected
// through a drop and its landing window, Pneumatic Shock Absorption on landing, and Crush
// Stomp (ADR-0017). truck_tick.js calls stepLanding once per tick with this module's slice of
// truck state; main.js's entityHurt handler asks absorbsFallDamage. Must not import
// @minecraft/server, so node can load it.
import { findDryLanding, isLiquidBlock } from "./amphibious.js";
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
 * Find a standing position beside the vehicle door for a dismounting rider.
 * Driver door is out to the left side (+perp direction, 1.8 blocks from centerline).
 * Passenger door is out to the right side (-perp direction, -1.8 blocks from centerline).
 * @param {import("./truck_tick.js").WorldDimension} dimension
 * @param {import("./truck_tick.js").Vector3} loc
 * @param {{ x: number, z: number }} heading
 * @param {boolean} [isPassenger=false]
 * @returns {import("./truck_tick.js").Vector3}
 */
export function findDoorLanding(dimension, loc, heading, isPassenger = false) {
  const dirX = heading.x;
  const dirZ = heading.z;
  const primarySide = isPassenger ? -1 : 1;
  const forwardOffset = 0.15;
  const sideDistances = [1.8, 1.5, 2.2];

  for (const sideSign of [primarySide, -primarySide]) {
    for (const dist of sideDistances) {
      const targetX = loc.x + dirZ * (dist * sideSign) + dirX * forwardOffset;
      const targetZ = loc.z - dirX * (dist * sideSign) + dirZ * forwardOffset;
      const bx = Math.floor(targetX);
      const bz = Math.floor(targetZ);
      const cy = Math.floor(loc.y);

      if (!dimension || typeof dimension.getBlock !== "function") {
        return { x: targetX, y: loc.y, z: targetZ };
      }

      for (const y of [cy, cy + 1, cy - 1, cy - 2]) {
        try {
          const below = dimension.getBlock({ x: bx, y: y - 1, z: bz });
          const feet = dimension.getBlock({ x: bx, y: y, z: bz });
          const head = dimension.getBlock({ x: bx, y: y + 1, z: bz });
          if (below && !below.isAir && !isLiquidBlock(below.typeId) && (!feet || feet.isAir) && (!head || head.isAir)) {
            return { x: targetX, y, z: targetZ };
          }
        } catch {}
      }
    }
  }

  const fallbackX = loc.x + dirZ * (1.8 * primarySide) + dirX * forwardOffset;
  const fallbackZ = loc.z - dirX * (1.8 * primarySide) + dirZ * forwardOffset;
  return { x: fallbackX, y: loc.y, z: fallbackZ };
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
  const seated = new Set((rideable.getRiders?.() || []).map((rider) => rider?.id));
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
 *   inLava?: boolean,
 *   tick: number,
 *   getEntity(id: string): import("./truck_tick.js").WorldEntity | undefined,
 *   protectedRiders: Map<string, string>,
 *   jumpedRecently?(player: import("./truck_tick.js").WorldEntity): boolean,
 * }} frame dy: height change since last tick; heading: unit direction of travel;
 *   riderIds / prevRiderIds: seated rider ids this tick and last tick;
 *   jumpedRecently: the player holds Jump (Space) or did within the last few ticks, while Space can still
 *   dismount them (their Jump input is not locked).
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
    inLava,
    tick: tickNumber,
    getEntity,
    protectedRiders,
    jumpedRecently
  } = frame;
  const dirX = heading.x;
  const dirZ = heading.z;
  const perpX = -dirZ;
  const perpZ = dirX;
  const falling = isFalling(dy, verticalVelocity);

  // Rider dismount management. Minecraft dismounts a rider who presses Space, the add-on's handbrake, and
  // detaches riders around drops (#32): both are undone unless the rider is sneaking. Any other exit on
  // steady ground is Sneak: in the real client a Sneak exit never reads as sneaking on the riding player.
  const inDropWindow = falling || landing.isFalling ||
    Boolean(landing.riderRetentionUntil && tickNumber <= landing.riderRetentionUntil);
  if (prevRiderIds.length > riderIds.length) {
    const currentRiderIds = new Set(riderIds);
    const dismountedIds = prevRiderIds.filter((id) => !currentRiderIds.has(id));
    for (const playerId of dismountedIds) {
      try {
        const player = getEntity(playerId);
        if (player && player.isValid && player.typeId === "minecraft:player") {
          const spaceExit = Boolean(jumpedRecently?.(player));
          if (spaceExit && !inDropWindow && !player.isSneaking && rideable && rideable.addRider) {
            // The handbrake's Space dismount: reseat without opening a drop window, so Sneak works right after.
            rideable.addRider(player);
          } else if (inDropWindow && !player.isSneaking && rideable && rideable.addRider) {
            // An engine detachment around a drop: reseat, tied to a bounded vehicle lifecycle.
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
            // Sneak over liquid: set down on the nearest dry land. With none in reach, lava keeps the rider
            // seated and water lets them swim.
            const dryLand = findDryLanding(dimension, loc);
            if (dryLand) {
              player.teleport(dryLand, { dimension });
            } else if (inLava && rideable && rideable.addRider) {
              rideable.addRider(player);
              continue;
            }
            protectedRiders.delete(playerId);
            landing.protectedRiderIds?.delete(playerId);
          } else {
            const isPassenger = prevRiderIds.indexOf(playerId) === 1;
            const doorLanding = findDoorLanding(dimension, loc, heading, isPassenger);
            if (doorLanding && player.teleport) {
              player.teleport(doorLanding, { dimension });
            }
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
        let nearby = [];
        try {
          nearby = dimension.getEntities({ location: loc, maxDistance: CRUSH_STOMP_RADIUS });
        } catch {}
        // Each target gets its own try: one that throws (say, it became invalid) spares no others.
        for (const target of nearby) {
          try {
            if (isProtectedTarget(target, truck)) continue;

            const shockImpulse = calculateShockwaveImpulse(target.location, loc, 1.5);
            try { target.applyImpulse(shockImpulse); } catch {}

            damageEntity(target, crushDamage, CONTACT_DAMAGE, truck);
          } catch {}
        }

        try {
          dimension.playSound("random.explode", loc, { volume: 0.8, pitch: 1.4 });
        } catch {}
        try {
          dimension.spawnParticle("minecraft:large_explosion", { x: loc.x, y: loc.y + 0.3, z: loc.z });
        } catch {}
      }
    }
  }
}
