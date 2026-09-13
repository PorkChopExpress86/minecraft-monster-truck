// Suspension Jump and Crush Stomp physics

export const JUMP_COOLDOWN_TICKS = 24; // 1.2 seconds at 20 ticks/sec

export function canTriggerJump(lastJumpTick, currentTick) {
  if (lastJumpTick === undefined || lastJumpTick === null) return true;
  return currentTick - lastJumpTick >= JUMP_COOLDOWN_TICKS;
}

export function calculateJumpImpulse(effectiveSpeed = 0, heading = { x: 1, z: 0 }, verticalBoost = 0.82) {
  const hDist = Math.hypot(heading.x, heading.z) || 1;
  const dirX = heading.x / hDist;
  const dirZ = heading.z / hDist;

  // Preserve and boost forward driving speed into airborne flight
  const forwardBoost = Math.max(0.1, effectiveSpeed * 0.4);

  return {
    x: dirX * forwardBoost,
    y: verticalBoost, // Clears >= 3 vertical blocks
    z: dirZ * forwardBoost,
  };
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
