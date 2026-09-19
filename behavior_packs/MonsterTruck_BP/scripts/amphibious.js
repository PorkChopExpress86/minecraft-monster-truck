// Amphibious propulsion and shoreline step-up physics for Monster Truck

export const CRUISING_AQUATIC_SPEED = 0.55;

export function calculateAquaticIntent(
  movement = { x: 0, y: 0 },
  vehicleHeading = { x: 1, z: 0 }
) {
  const inputX = movement.x || 0;
  const inputForward = movement.y || 0;
  const magnitude = Math.hypot(inputX, inputForward);
  if (magnitude <= 0.05) {
    return { active: false, heading: { x: 0, z: 0 }, throttle: 0 };
  }

  const headingLength = Math.hypot(vehicleHeading.x, vehicleHeading.z) || 1;
  const forwardX = vehicleHeading.x / headingLength;
  const forwardZ = vehicleHeading.z / headingLength;
  const rightX = -forwardZ;
  const rightZ = forwardX;
  const worldX = forwardX * inputForward + rightX * inputX;
  const worldZ = forwardZ * inputForward + rightZ * inputX;
  const worldLength = Math.hypot(worldX, worldZ) || 1;

  return {
    active: true,
    heading: { x: worldX / worldLength, z: worldZ / worldLength },
    throttle: Math.min(1, magnitude)
  };
}

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

export function classifyShorelineColumn(solidColumn = []) {
  let stepHeight = 0;
  for (const solid of solidColumn) {
    if (!solid) break;
    stepHeight += 1;
  }

  return {
    isShoreline: stepHeight === 1 || stepHeight === 2,
    stepHeight
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
