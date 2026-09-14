export const MAX_PITCH_DEGREES = 35;
export const MAX_STEER_DEGREES = 26;
export const REAR_STEER_RATIO = 18.0 / 26.0;

/**
 * Calculates vehicle pitch angle conforming to terrain incline, jump trajectory, or flotation.
 */
export function calculateDynamicPitch({
  frontHeight,
  rearHeight,
  wheelbase = 2.25,
  currentPitch = 0.0,
  isAirborne = false,
  inLiquid = false,
  verticalVelocity = 0.0,
  horizontalSpeed = 0.0,
  smoothingFactor = 0.20
}) {
  let targetPitch = 0.0;

  if (inLiquid) {
    targetPitch = 0.0;
  } else if (isAirborne) {
    if (horizontalSpeed > 0.1) {
      const trajAngle = Math.atan2(verticalVelocity, horizontalSpeed) * (180.0 / Math.PI);
      targetPitch = Math.max(-MAX_PITCH_DEGREES, Math.min(MAX_PITCH_DEGREES, trajAngle));
    } else if (verticalVelocity > 0.1) {
      targetPitch = Math.min(MAX_PITCH_DEGREES, verticalVelocity * 25.0);
    } else if (verticalVelocity < -0.1) {
      targetPitch = Math.max(-MAX_PITCH_DEGREES, verticalVelocity * 30.0);
    } else {
      targetPitch = 0.0;
    }
  } else {
    // Ground contour pitch: deltaY between front and rear axle
    const deltaY = frontHeight - rearHeight;
    const rawPitch = Math.atan2(deltaY, wheelbase) * (180.0 / Math.PI);
    targetPitch = Math.max(-MAX_PITCH_DEGREES, Math.min(MAX_PITCH_DEGREES, rawPitch));
  }

  const factor = Math.max(0.0, Math.min(1.0, smoothingFactor));
  const smoothed = currentPitch + (targetPitch - currentPitch) * factor;

  if (Math.abs(smoothed) < 0.05) {
    return 0;
  }
  return Math.round(smoothed);
}

/**
 * Calculates front wheel steering angle based on yaw angular rate and centering spring.
 */
export function calculateSteerAngle({
  deltaYaw = 0.0,
  currentSteer = 0.0,
  hasDriver = false,
  returnSpeed = 0.35,
  steerSpeed = 0.30,
  steerRate = 4.0
}) {
  if (!hasDriver || Math.abs(deltaYaw) < 0.05) {
    // Centering spring
    const centered = currentSteer * (1.0 - returnSpeed);
    if (Math.abs(centered) < 0.5) return 0;
    return Math.round(centered);
  }

  // Active turning
  const targetSteer = Math.max(-MAX_STEER_DEGREES, Math.min(MAX_STEER_DEGREES, deltaYaw * steerRate));
  const factor = Math.max(0.0, Math.min(1.0, steerSpeed));
  const smoothed = currentSteer + (targetSteer - currentSteer) * factor;
  return Math.round(smoothed);
}

/**
 * Calculates counter-phase rear wheel steering angle from front steer angle.
 */
export function calculateRearSteerAngle(frontSteer) {
  if (Math.abs(frontSteer) < 0.5) return 0;
  return Math.round(-frontSteer * REAR_STEER_RATIO);
}

/**
 * Helper to sample ground elevation at a given 2D horizontal position.
 */
export function sampleGroundHeight(dimension, x, yStart, z) {
  const startY = Math.floor(yStart);
  const blockX = Math.floor(x);
  const blockZ = Math.floor(z);

  // Scan downward from startY + 2 down to startY - 3
  for (let dy = 2; dy >= -3; dy--) {
    try {
      const block = dimension.getBlock({ x: blockX, y: startY + dy, z: blockZ });
      if (block && !block.isAir && block.typeId !== "minecraft:air") {
        return startY + dy + 1.0;
      }
    } catch {
      break;
    }
  }
  return yStart;
}
