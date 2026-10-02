// Amphibious propulsion and shoreline step-up physics for Monster Truck

// Full overland cruising speed in blocks/tick. The 0.55 movement attribute is an engine
// value, not a speed: a driven truck covers 1.06-1.12 blocks/tick on flat ground (Scenario Runs, #38).
export const CRUISING_AQUATIC_SPEED = 1.1;
export const MAX_AQUATIC_ACCELERATION = 0.5; // blocks/tick gained per tick
// Share of velocity a floating truck keeps after the engine's liquid drag, measured by
// Scenario Runs (#38): a 1.1 velocity moved it 0.95 blocks/tick in water, 0.79 in lava.
export const LIQUID_DRAG_RETENTION = { water: 0.86, lava: 0.72 };

// Velocity to restore each tick so that, after drag, the truck covers cruising distance.
export function aquaticVelocityTarget(inLava = false, throttle = 1) {
  const retention = inLava ? LIQUID_DRAG_RETENTION.lava : LIQUID_DRAG_RETENTION.water;
  return CRUISING_AQUATIC_SPEED * throttle / retention;
}

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
  // Restore the whole deficit each tick, so liquid drag cannot hold the truck below
  // cruising speed; the cap keeps acceleration from rest gradual.
  const boost = Math.min(deficit, MAX_AQUATIC_ACCELERATION);

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

// Thermal shielding: riders seated in the truck take no heat damage while it crosses lava
// or climbs out of it, including the moment the seat dips into the lava surface.
const HEAT_DAMAGE_CAUSES = new Set(["fire", "fireTick", "lava"]);

export function shouldShieldRiderFromHeat(damageCause, isSeatedRider = false) {
  return Boolean(isSeatedRider) && HEAT_DAMAGE_CAUSES.has(damageCause);
}
