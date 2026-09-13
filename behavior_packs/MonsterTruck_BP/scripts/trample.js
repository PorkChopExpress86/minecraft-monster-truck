// Speed-scaled tire trample and knockback calculations

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

export function isInContactPerimeter(
  targetLoc,
  truckLoc,
  heading = { x: 1, z: 0 },
  width = 2.25,
  length = 3.6,
  perimeter = 1.6
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
