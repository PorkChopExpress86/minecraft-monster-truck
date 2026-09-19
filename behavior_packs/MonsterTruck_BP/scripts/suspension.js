// Suspension Jump, Pneumatic Shock Absorption, and Crush Stomp physics

export const JUMP_COOLDOWN_TICKS = 24; // 1.2 seconds at 20 ticks/sec
export const JUMP_VERTICAL_IMPULSE = 1.25;
export const PNEUMATIC_VENT_SOUND = "random.fizz";
export const PNEUMATIC_DUST_PARTICLE = "minecraft:campfire_smoke_particle";

export function canTriggerJump(lastJumpTick, currentTick) {
  if (lastJumpTick === undefined || lastJumpTick === null) return true;
  return currentTick - lastJumpTick >= JUMP_COOLDOWN_TICKS;
}

export function calculateJumpImpulse(
  effectiveSpeed = 0,
  heading = { x: 1, z: 0 },
  verticalBoost = JUMP_VERTICAL_IMPULSE
) {
  const hDist = Math.hypot(heading.x, heading.z) || 1;
  const dirX = heading.x / hDist;
  const dirZ = heading.z / hDist;

  // Preserve forward driving speed into airborne flight
  const forwardBoost = effectiveSpeed > 0.05 ? effectiveSpeed * 0.4 : 0;

  return {
    x: dirX * forwardBoost,
    y: verticalBoost, // Clears >= 3 vertical blocks
    z: dirZ * forwardBoost,
  };
}

export function advanceJumpPhase(
  phase = "grounded",
  { verticalVelocity = 0, deltaY = 0, grounded = false } = {}
) {
  if (phase === "launch") {
    if (!grounded || verticalVelocity > 0.05 || deltaY > 0.05) {
      return { phase: "ascending", didLand: false };
    }
    return { phase, didLand: false };
  }

  if (phase === "ascending") {
    if (verticalVelocity <= 0 && deltaY <= 0) {
      return { phase: "descending", didLand: false };
    }
    return { phase, didLand: false };
  }

  if (phase === "descending" && grounded) {
    return { phase: "grounded", didLand: true };
  }

  return { phase, didLand: false };
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

export function isFallingOrAirborne(isAirborne = false, deltaY = 0, verticalVelocity = 0) {
  if (isAirborne) return true;
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
