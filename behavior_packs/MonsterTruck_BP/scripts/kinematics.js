import { MAX_PITCH_DEGREES, PITCH_AXLE_SPAN } from "./geometry.js";

/**
 * Calculates vehicle pitch angle conforming to terrain incline, jump trajectory, or flotation.
 */
export function calculateDynamicPitch({
  frontHeight,
  rearHeight,
  wheelbase = PITCH_AXLE_SPAN,
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
  } else if (frontHeight === null || rearHeight === null) {
    // An axle found no ground within reach: hold the current pitch rather than read it as level.
    targetPitch = currentPitch;
  } else {
    // Ground contour pitch: deltaY between front and rear axle
    const deltaY = frontHeight - rearHeight;
    const rawPitch = Math.atan2(deltaY, wheelbase) * (180.0 / Math.PI);
    targetPitch = Math.max(-MAX_PITCH_DEGREES, Math.min(MAX_PITCH_DEGREES, rawPitch));
  }

  const factor = Math.max(0.0, Math.min(1.0, smoothingFactor));
  const smoothed = currentPitch + (targetPitch - currentPitch) * factor;

  // Whole-degree rounding of a smoothed step stalls up to ~2 degrees short of the target,
  // so always advance at least one degree until the target is reached.
  const target = Math.round(targetPitch);
  let next = Math.round(smoothed);
  if (factor > 0 && next === Math.round(currentPitch) && next !== target) {
    next += Math.sign(target - next);
  }
  return next || 0;
}

/**
 * Helper to sample ground elevation at a given 2D horizontal position.
 */
export function sampleGroundHeight(dimension, x, yStart, z) {
  const startY = Math.floor(yStart);
  const blockX = Math.floor(x);
  const blockZ = Math.floor(z);

  // Scan downward from startY + 2 to startY - 6: on steep stairs the engine lifts the
  // truck two blocks at a time, leaving the rear axle's ground well below the body.
  for (let dy = 2; dy >= -6; dy--) {
    try {
      const block = dimension.getBlock({ x: blockX, y: startY + dy, z: blockZ });
      if (block && !block.isAir && block.typeId !== "minecraft:air") {
        return startY + dy + 1.0;
      }
    } catch {
      break;
    }
  }
  return null;
}
