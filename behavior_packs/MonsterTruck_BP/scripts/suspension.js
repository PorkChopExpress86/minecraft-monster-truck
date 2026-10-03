// Pneumatic Shock Absorption and Crush Stomp physics

export const PNEUMATIC_VENT_SOUND = "random.fizz";
export const PNEUMATIC_DUST_PARTICLE = "minecraft:campfire_smoke_particle";
// Landings from at least this many blocks of drop crush the entities beneath (ADR-0017).
export const CRUSH_STOMP_MIN_DROP = 3;

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

export function shouldAbsorbFallDamage(damageCause, isTruckOrRider = false) {
  if (!isTruckOrRider) return false;
  return damageCause === "fall" || damageCause === "damage.fall";
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
