// Amphibious propulsion and shoreline step-up physics for Monster Truck

export const CRUISING_AQUATIC_SPEED = 0.55;

export function calculateAquaticImpulse(
  currentVelocity = { x: 0, z: 0 },
  heading = { x: 1, z: 0 },
  targetSpeed = CRUISING_AQUATIC_SPEED
) {
  const hDist = Math.hypot(heading.x, heading.z) || 1;
  const dirX = heading.x / hDist;
  const dirZ = heading.z / hDist;

  // Current forward velocity along heading
  const currentForwardSpeed = (currentVelocity.x || 0) * dirX + (currentVelocity.z || 0) * dirZ;

  if (currentForwardSpeed >= targetSpeed) {
    return { x: 0, y: 0, z: 0 };
  }

  const deficit = targetSpeed - currentForwardSpeed;
  // Apply proportional acceleration impulse
  const boost = Math.min(Math.max(deficit * 0.45, 0.15), targetSpeed);

  return {
    x: dirX * boost,
    y: 0,
    z: dirZ * boost,
  };
}

export function detectShorelineBank(
  inLiquid = false,
  frontBlockAtWaterIsSolid = false,
  frontBlockAboveIsSolid = false
) {
  if (!inLiquid || !frontBlockAtWaterIsSolid) {
    return { isShoreline: false, stepHeight: 0 };
  }

  const stepHeight = frontBlockAboveIsSolid ? 2 : 1;
  return {
    isShoreline: true,
    stepHeight,
  };
}

export function calculateShorelineStepImpulse(heading = { x: 1, z: 0 }, stepHeight = 1) {
  const hDist = Math.hypot(heading.x, heading.z) || 1;
  const dirX = heading.x / hDist;
  const dirZ = heading.z / hDist;

  if (stepHeight >= 2) {
    return {
      x: dirX * 0.40,
      y: 0.62, // Elevates cleanly over 2-block shoreline rise
      z: dirZ * 0.40,
    };
  }

  return {
    x: dirX * 0.35,
    y: 0.42, // Elevates cleanly over 1-block shoreline rise
    z: dirZ * 0.35,
  };
}
